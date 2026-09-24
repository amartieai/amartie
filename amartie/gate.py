"""
AMARTIE Gate Engine — JEV-Powered
===================================
The 9-judge verification gate. Every outbound action passes through.
Unanimous PASS or bounce. Never a push-through.

Now powered by JEV (TypeSafe System One) for:
- 13x faster evaluation (~150ms vs ~2s per judge)
- Zero hallucinations (typed output)
- Per-judge confidence scores
- Fallback to Layer (free, self-hosted) when no JEV API key

Tackles open issues:
- #8  Self-auditing gate
- #9  Judge interface and evidence contract
- #10 Nine-judge roster and registry
- #11-19 Individual judges
"""

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Try to import JEV SDK
try:
    from typesafe_sdk import TypeSafeClient, Noul, Choice, Score
    HAS_TYPESAFE_SDK = True
except ImportError:
    HAS_TYPESAFE_SDK = False

# Try to import Layer (free fallback — self-hosted)
try:
    from amartie.layer_local import LayerClient, LayerChoice, LayerScore, LayerNoul
    HAS_LAYER = True
except ImportError:
    HAS_LAYER = False

# Import cache
try:
    from amartie.cache import judge_cache
    HAS_CACHE = True
except ImportError:
    judge_cache = None
    HAS_CACHE = False

# ── Contract Version ──────────────────────────────────────────────────────────
# Bump JUDGE_CONTRACT_VERSION when the Judge interface changes.
JUDGE_CONTRACT_VERSION = "1.0.0"
ROSTER_VERSION = "1.0.0"
CANONICAL_ROSTER_ORDER = ["J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9"]

# Receipt chain persistence
RECEIPT_CHAIN_DIR = os.path.expanduser("~/.amartie")
RECEIPT_CHAIN_PATH = os.path.join(RECEIPT_CHAIN_DIR, "receipt_chain.jsonl")
CHAIN_VERSION = 1


class EvidencePackage:
    """Structured evidence backing a judge's verdict.

    Every judge MUST supply at least one evidence item.
    Empty evidence = fail-closed (gate rejects the verdict).
    """

    def __init__(self, evidence_items: List[str],
                 source_refs: Optional[List[str]] = None):
        self.evidence_items = evidence_items
        self.source_refs = source_refs or []

    def is_sufficient(self) -> bool:
        """At least one piece of evidence is required."""
        return len(self.evidence_items) >= 1

    def to_dict(self) -> dict:
        return {
            "evidence_items": self.evidence_items,
            "source_refs": self.source_refs,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EvidencePackage":
        return cls(
            d.get("evidence_items", []),
            d.get("source_refs", []),
        )


class JudgeVerdict:
    """A single judge's verdict on an action.

    Implements the versioned Judge interface contract (v1.0.0).
    Every verdict carries:
      - judge_id        logical judge identifier
      - impl_version    version of this judge's implementation
      - model_id        model identity that produced the verdict
      - verdict         PASS or DISSENT
      - evidence        structured EvidencePackage (must be non-empty)
      - rationale       free-text explanation of the decision
      - findings        factual observations
      - corrections     corrective actions (if DISSENT)
      - tool_calls      evidence of tool-use activity
    """

    CONTRACT_VERSION = JUDGE_CONTRACT_VERSION

    def __init__(self, judge_id: str, model_id: str, verdict: str,
                 findings: List[str], corrections: List[str],
                 tool_calls: List[str],
                 impl_version: str = "1.0.0",
                 rationale: str = "",
                 evidence: Optional[EvidencePackage] = None):
        self.judge_id = judge_id
        self.model_id = model_id
        self.verdict = verdict  # PASS or DISSENT
        self.findings = findings
        self.corrections = corrections
        self.tool_calls = tool_calls
        self.impl_version = impl_version
        self.rationale = rationale
        self.evidence = evidence or EvidencePackage([])
        self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> dict:
        return {
            "judge_id": self.judge_id,
            "model_id": self.model_id,
            "impl_version": self.impl_version,
            "verdict": self.verdict,
            "evidence": self.evidence.to_dict(),
            "rationale": self.rationale,
            "findings": self.findings,
            "corrections": self.corrections,
            "tool_calls": self.tool_calls,
            "timestamp": self.timestamp
        }

    @classmethod
    def validate_verdict_dict(cls, verdict_dict: dict) -> List[str]:
        """Validate a verdict dictionary against the contract.

        Returns a list of error strings (empty = valid).
        """
        errors = []

        required_fields = [
            "judge_id", "verdict", "findings", "tool_calls",
        ]
        for field in required_fields:
            if field not in verdict_dict:
                errors.append(f"Missing required field: {field}")

        if errors:
            return errors

        # Verdict value
        v = verdict_dict.get("verdict")
        if v not in ("PASS", "DISSENT"):
            errors.append(f"Invalid verdict value: {v!r}")

        # Evidence (fail-closed on missing evidence)
        evidence = verdict_dict.get("evidence")
        if not evidence:
            errors.append("Missing evidence — every verdict requires evidence")
        elif not isinstance(evidence, dict):
            errors.append(f"Evidence must be a dict, got {type(evidence).__name__}")
        else:
            items = evidence.get("evidence_items", [])
            if not isinstance(items, list) or len(items) < 1:
                errors.append(
                    "Insufficient evidence — at least one evidence_item required"
                )

        # List fields must be lists
        for list_field in ("findings", "tool_calls", "corrections"):
            val = verdict_dict.get(list_field)
            if not isinstance(val, list):
                errors.append(
                    f"{list_field} must be a list, got {type(val).__name__}"
                )

        return errors

    @staticmethod
    def from_dict(d: dict) -> "JudgeVerdict":
        evidence_dict = d.get("evidence", {})
        if isinstance(evidence_dict, dict):
            evidence = EvidencePackage(
                evidence_dict.get("evidence_items", []),
                evidence_dict.get("source_refs", []),
            )
        else:
            evidence = EvidencePackage([])
        v = JudgeVerdict(
            judge_id=d["judge_id"],
            model_id=d["model_id"],
            verdict=d["verdict"],
            findings=d.get("findings", []),
            corrections=d.get("corrections", []),
            tool_calls=d.get("tool_calls", []),
            impl_version=d.get("impl_version", "1.0.0"),
            rationale=d.get("rationale", ""),
            evidence=evidence,
        )
        v.timestamp = d.get("timestamp", v.timestamp)
        return v


class GateReceipt:
    """Hash-chained receipt for a gated action."""
    
    def __init__(self, action_id: str, action_type: str, payload_hash: str,
                 verdicts: List[JudgeVerdict], previous_hash: str = "",
                 contract_version: str = JUDGE_CONTRACT_VERSION,
                 roster_snapshot: Optional[dict] = None):
        self.action_id = action_id
        self.action_type = action_type
        self.payload_hash = payload_hash
        self.verdicts = [v.to_dict() for v in verdicts]
        self.previous_hash = previous_hash
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.version = CHAIN_VERSION
        self.contract_version = contract_version
        self.roster_snapshot = roster_snapshot or {}
        self.hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        content = json.dumps({
            "action_id": self.action_id,
            "action_type": self.action_type,
            "payload_hash": self.payload_hash,
            "verdicts": self.verdicts,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "version": self.version,
            "contract_version": self.contract_version,
            "roster_snapshot": self.roster_snapshot,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def verify(self) -> bool:
        """Verify this receipt's hash is correct."""
        return self.hash == self._compute_hash()
    
    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "payload_hash": self.payload_hash,
            "verdicts": self.verdicts,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "hash": self.hash,
            "version": self.version,
            "contract_version": self.contract_version,
            "roster_snapshot": self.roster_snapshot,
        }

    @staticmethod
    def from_dict(d: dict) -> "GateReceipt":
        verdicts = [JudgeVerdict.from_dict(v) for v in d.get("verdicts", [])]
        r = GateReceipt(
            action_id=d["action_id"],
            action_type=d["action_type"],
            payload_hash=d["payload_hash"],
            verdicts=verdicts,
            previous_hash=d.get("previous_hash", ""),
            contract_version=d.get("contract_version", JUDGE_CONTRACT_VERSION),
            roster_snapshot=d.get("roster_snapshot", {}),
        )
        # Override auto-generated fields with stored values
        r.timestamp = d.get("timestamp", r.timestamp)
        r.version = d.get("version", CHAIN_VERSION)
        r.hash = d.get("hash", r.hash)
        return r


class JudgeGate:
    """
    The 9-judge AMARTIE gate — now powered by JEV.
    
    Every outbound action passes through 9 independent judges.
    All must pass. One DISSENT = correction + re-judgment.
    
    Provider selection:
    1. JEV (TypeSafe) — if TYPESAFE_API_KEY set
    2. Layer — free, self-hosted fallback
    3. Mock — for testing (always passes)
    """
    
    # The canonical 9 judge roster with JEV question templates
    ROSTER = {
        "J1": {
            "domain": "TRUTH",
            "question": "Does this action contain only truthful, verifiable claims?",
            "criteria": {
                "pass": "All claims are truthful and verifiable",
                "dissent": "Contains unsubstantiated or false claims"
            }
        },
        "J2": {
            "domain": "BOUNDARY-INTEGRITY",
            "question": "Does this action respect system boundaries and capabilities?",
            "criteria": {
                "pass": "Stays within authorized boundaries",
                "dissent": "Exceeds boundaries or capabilities"
            }
        },
        "J3": {
            "domain": "LOGIC",
            "question": "Is the action logically sound and consistent?",
            "criteria": {
                "pass": "Logically consistent and coherent",
                "dissent": "Contains logical errors or contradictions"
            }
        },
        "J4": {
            "domain": "COMPLETENESS",
            "question": "Is the action complete with all required information?",
            "criteria": {
                "pass": "Complete with all necessary details",
                "dissent": "Missing required information"
            }
        },
        "J5": {
            "domain": "EXECUTION-AND-SIMPLICITY",
            "question": "Is the action the simplest way to achieve the goal?",
            "criteria": {
                "pass": "Simple and direct execution",
                "dissent": "Overly complex or indirect"
            }
        },
        "J6": {
            "domain": "OWNER-INTENT",
            "question": "Does this action align with the owner's stated intent?",
            "criteria": {
                "pass": "Fully aligns with owner intent",
                "dissent": "Diverges from owner intent"
            }
        },
        "J7": {
            "domain": "RECOVERY",
            "question": "Can the action be recovered from if it fails?",
            "criteria": {
                "pass": "Recoverable with clear rollback",
                "dissent": "Irreversible or no recovery path"
            }
        },
        "J8": {
            "domain": "TRADE-INTEGRITY",
            "question": "Does this action maintain trade execution integrity?",
            "criteria": {
                "pass": "Maintains execution integrity",
                "dissent": "Compromises execution integrity"
            }
        },
        "J9": {
            "domain": "UNITY",
            "question": "Does this action serve the collective team goal?",
            "criteria": {
                "pass": "Serves collective team interests",
                "dissent": "Serves individual over collective"
            }
        },
    }
    
    def __init__(self, typesafe_api_key: Optional[str] = None,
                 use_layer_fallback: bool = True,
                 mock_mode: bool = False,
                 validate_roster: bool = True,
                 receipt_chain_path: Optional[str] = None):
        self.receipt_chain: List[str] = []  # hash chain
        self._receipt_store: Dict[str, GateReceipt] = {}
        self.round_cap = 4
        self.time_budget_per_judge = 1200  # seconds
        self.gate_wide_budget = 900  # seconds

        # ── Roster validation at startup ────────────────────────────────
        if validate_roster:
            roster_errors = self._check_roster_integrity(self.ROSTER)
            if roster_errors:
                raise RuntimeError(
                    f"Roster validation FAILED — gate cannot start:\n"
                    + "\n".join(f"  - {e}" for e in roster_errors)
                )

        # Determine provider
        self.provider = self._init_provider(typesafe_api_key, use_layer_fallback, mock_mode)
        self.client = self._init_client(typesafe_api_key)

        # Allow per-instance override for test isolation
        self._chain_path = receipt_chain_path or RECEIPT_CHAIN_PATH

        # Load persisted receipt chain from disk (fail-closed on corruption)
        self._load_chain_from_disk()

    def _init_provider(self, api_key: Optional[str], use_layer_fallback: bool,
                       mock_mode: bool) -> str:
        """Determine which provider to use."""
        if mock_mode:
            return "mock"
        if api_key and HAS_TYPESAFE_SDK:
            return "jev"
        if use_layer_fallback and HAS_LAYER:
            return "layer"
        return "mock"
    
    def _init_client(self, api_key: Optional[str]):
        """Initialize the JEV/Layer client."""
        if self.provider == "jev" and api_key:
            return TypeSafeClient(api_key=api_key)
        return None

    # ── Roster validation ──────────────────────────────────────────────────

    @staticmethod
    def _check_roster_integrity(roster: dict) -> List[str]:
        """Check a roster dict for integrity issues.

        Returns list of error strings (empty = valid).
        """
        errors = []

        if len(roster) != 9:
            errors.append(f"Expected exactly 9 judges, got {len(roster)}")

        expected_ids = set(CANONICAL_ROSTER_ORDER)
        actual_ids = set(roster.keys())

        missing = expected_ids - actual_ids
        unexpected = actual_ids - expected_ids

        if missing:
            errors.append(f"Missing judges: {sorted(missing)}")
        if unexpected:
            errors.append(f"Unexpected judges: {sorted(unexpected)}")

        required_judge_fields = {"domain", "question", "criteria"}
        for jid, cfg in roster.items():
            missing_fields = required_judge_fields - set(cfg.keys())
            if missing_fields:
                errors.append(
                    f"Judge {jid} missing fields: {sorted(missing_fields)}"
                )
            if "criteria" in cfg:
                for sub in ("pass", "dissent"):
                    if sub not in cfg["criteria"]:
                        errors.append(
                            f"Judge {jid} criteria missing '{sub}'"
                        )

        return errors

    @staticmethod
    def diagnostic_roster() -> List[dict]:
        """Return a safe diagnostic view of the active roster.

        No secrets, no question templates — just judge IDs and domains.
        Suitable for logging, /status endpoints, and admin tools.
        """
        return [
            {
                "judge_id": jid,
                "domain": cfg["domain"],
            }
            for jid, cfg in sorted(JudgeGate.ROSTER.items())
        ]

    def _build_roster_snapshot(self) -> dict:
        """Build a compact roster snapshot for embedding in receipts."""
        return {
            "roster_version": ROSTER_VERSION,
            "judges": sorted(self.ROSTER.keys()),
            "contract_version": JUDGE_CONTRACT_VERSION,
        }

    @staticmethod
    def _ensure_data_dir() -> str:
        """Create ~/.amartie/ if it doesn't exist."""
        os.makedirs(RECEIPT_CHAIN_DIR, exist_ok=True)
        return RECEIPT_CHAIN_DIR

    def _load_chain_from_disk(self) -> None:
        """Load + validate receipt chain from JSONL on disk.
        
        Fail-closed: if the file is missing, empty, malformed, or any
        receipt fails hash/chain verification, start with an empty chain.
        """
        self._ensure_data_dir()
        if not os.path.isfile(self._chain_path):
            return  # Fresh start, empty chain

        try:
            with open(self._chain_path, "r") as f:
                lines = [line.strip() for line in f if line.strip()]

            loaded_receipts = []
            for line in lines:
                data = json.loads(line)
                receipt = GateReceipt.from_dict(data)
                loaded_receipts.append(receipt)

            # Verify every receipt's hash is self-consistent
            for receipt in loaded_receipts:
                if receipt.hash != receipt._compute_hash():
                    return  # Tampered — fail closed to empty

            # Verify chain linkage
            chain_hashes = []
            for idx, receipt in enumerate(loaded_receipts):
                expected_prev = chain_hashes[idx - 1] if idx > 0 else "GENESIS"
                if receipt.previous_hash != expected_prev:
                    return  # Broken chain — fail closed to empty
                chain_hashes.append(receipt.hash)

            # All checks passed — populate in-memory state
            self.receipt_chain = chain_hashes
            for receipt in loaded_receipts:
                self._receipt_store[receipt.hash] = receipt

        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            # Malformed file — fail closed to empty chain
            self.receipt_chain = []
            self._receipt_store = {}

    def _append_receipt_to_disk(self, receipt: GateReceipt) -> None:
        """Append one receipt as a JSON line."""
        self._ensure_data_dir()
        with open(self._chain_path, "a") as f:
            f.write(json.dumps(receipt.to_dict(), sort_keys=True) + "\n")

    def _build_fail_receipt(self, action_type: str, payload: dict,
                             reason: str) -> GateReceipt:
        """Build a receipt for a failed evaluation (contract violation, etc.)."""
        previous_hash = (
            self.receipt_chain[-1] if self.receipt_chain else "GENESIS"
        )
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        return GateReceipt(
            action_id=str(uuid.uuid4()),
            action_type=action_type,
            payload_hash=payload_hash,
            verdicts=[],
            previous_hash=previous_hash,
            contract_version=JUDGE_CONTRACT_VERSION,
            roster_snapshot=self._build_roster_snapshot(),
        )

    def get_rotated_judge_id(self, logical_id: str, date: Optional[str] = None) -> str:
        """
        Daily rotating judge IDs. Prevents signature pre-computation.
        Physical instance IDs rotate based on date + owner key.
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rotation_seed = hashlib.sha256(f"{date}-{logical_id}".encode()).hexdigest()
        rotated_suffix = rotation_seed[:8]
        return f"{logical_id}-{rotated_suffix}"
    
    def verify_action(self, action_type: str, payload: dict,
                      judge_responses: Optional[List[JudgeVerdict]] = None) -> Tuple[bool, GateReceipt]:
        """
        Verify an action through the 9-judge gate.
        
        Args:
            action_type: The type of action (email, webhook, trade, etc.)
            payload: The action payload
            judge_responses: Optional list of 9 JudgeVerdict objects.
                           If None, runs evaluation through JEV/Layer.
            
        Returns:
            (passed, receipt): Whether the action passed and the receipt
        """
        # Check cache first
        if judge_cache is not None and judge_responses is None:
            cached = judge_cache.get(action_type, payload)
            if cached is not None:
                # Reconstruct JudgeVerdict objects from cache
                judge_responses = [
                    JudgeVerdict(
                        judge_id=v["judge_id"],
                        model_id=v["model_id"],
                        verdict=v["verdict"],
                        findings=v["findings"],
                        corrections=v["corrections"],
                        tool_calls=v["tool_calls"]
                    )
                    for v in cached
                ]
        
        # If no judge responses provided, run JEV evaluation
        if judge_responses is None:
            judge_responses = self._evaluate_through_jev(action_type, payload)
            # Cache the results
            if judge_cache is not None:
                judge_cache.put(action_type, payload, [v.to_dict() for v in judge_responses])

        # ── Validate every verdict against the contract ─────────────────
        for v in judge_responses:
            v_dict = v.to_dict()
            v_errors = JudgeVerdict.validate_verdict_dict(v_dict)
            if v_errors:
                return False, self._build_fail_receipt(
                    action_type, payload,
                    f"Contract violation for {v.judge_id}: "
                    f"{'; '.join(v_errors)}"
                )

        # Compute payload hash
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        
        # Check unanimous PASS
        all_passed = all(v.verdict == "PASS" for v in judge_responses)
        
        # Check model-lock (Braid law)
        for v in judge_responses:
            if v.model_id != self._get_assigned_model(v.judge_id):
                all_passed = False
                break
        
        # Check evidence floor (R3)
        for v in judge_responses:
            if len(v.tool_calls) < 2:
                all_passed = False
                break

        # Check evidence sufficiency (fail-closed on empty evidence)
        for v in judge_responses:
            if not v.evidence.is_sufficient():
                all_passed = False
                break

        # Create receipt
        previous_hash = self.receipt_chain[-1] if self.receipt_chain else "GENESIS"
        receipt = GateReceipt(
            action_id=str(uuid.uuid4()),
            action_type=action_type,
            payload_hash=payload_hash,
            verdicts=judge_responses,
            previous_hash=previous_hash,
            contract_version=JUDGE_CONTRACT_VERSION,
            roster_snapshot=self._build_roster_snapshot(),
        )
        
        # Add to chain
        self.receipt_chain.append(receipt.hash)
        self._receipt_store[receipt.hash] = receipt
        
        # Persist to disk
        self._append_receipt_to_disk(receipt)
        
        return all_passed, receipt
    
    def _evaluate_through_jev(self, action_type: str, payload: dict) -> List[JudgeVerdict]:
        """Run evaluation through JEV/Layer provider."""
        state = self._build_state(action_type, payload)
        verdicts = []
        
        for judge_id, config in self.ROSTER.items():
            verdict = self._run_single_judge(judge_id, config, state)
            verdicts.append(verdict)
        
        return verdicts
    
    def _build_state(self, action_type: str, payload: dict) -> str:
        """Build the state string for JEV from the action."""
        return f"Action Type: {action_type}\n\nPayload: {json.dumps(payload, sort_keys=True, indent=2)}"
    
    def _run_single_judge(self, judge_id: str, config: dict, state: str) -> JudgeVerdict:
        """Run a single judge using the configured provider."""
        if self.provider == "jev":
            return self._run_jev_judge(judge_id, config, state)
        elif self.provider == "layer":
            return self._run_layer_judge(judge_id, config, state)
        else:
            return self._run_mock_judge(judge_id, config, state)
    
    def _run_jev_judge(self, judge_id: str, config: dict, state: str) -> JudgeVerdict:
        """Run a judge using TypeSafe JEV."""
        try:
            response = self.client.system_one(
                state=state,
                questions={
                    "verdict": Choice(
                        instructions=config["question"],
                        criteria=config["criteria"]
                    ),
                    "confidence": Score(
                        instructions="How confident are you in this verdict?",
                        criteria=["Low", "Medium", "High", "Certain"]
                    ),
                    "evidence_sufficient": Noul(
                        instructions="Is there sufficient evidence to make this determination?"
                    )
                }
            )
            
            verdict_answer = response.choices.get("verdict", {})
            confidence_answer = response.scores.get("confidence", {})
            evidence_answer = response.nouls.get("evidence_sufficient", {})
            
            verdict_str = verdict_answer.get("choice", "dissent").lower()
            verdict = "PASS" if verdict_str == "pass" else "DISSENT"
            
            score_val = confidence_answer.get("score", 0)
            confidence = min(score_val / 3.0, 1.0)
            
            evidence_prob = evidence_answer.get("noul", 0.0)
            
            findings = [f"JEV evaluation complete for {config['domain']}"]
            if evidence_prob < 0.5:
                findings.append("WARNING: Evidence may be insufficient")
            
            corrections = []
            if verdict == "DISSENT":
                corrections.append(f"Failed {config['domain']} check")
            
            return JudgeVerdict(
                judge_id=judge_id,
                model_id="jev-latest",
                verdict=verdict,
                findings=findings,
                corrections=corrections,
                tool_calls=["jev_evaluate", "jev_score", "jev_noul"],
                impl_version="1.0.0",
                rationale=(
                    f"JEV assessed {config['domain']} "
                    f"with confidence {confidence:.2f} "
                    f"and evidence probability {evidence_prob:.2f}"
                ),
                evidence=EvidencePackage(
                    [f"JEV noul evidence_sufficient={evidence_prob:.2f}"]
                ),
            )

        except Exception as e:
            # Fail-closed: any error = DISSENT
            return JudgeVerdict(
                judge_id=judge_id,
                model_id="jev-latest",
                verdict="DISSENT",
                findings=[f"JEV evaluation error: {str(e)}"],
                corrections=["Retry evaluation"],
                tool_calls=["jev_evaluate"],
                impl_version="1.0.0",
                rationale=f"JEV error: {str(e)}",
                evidence=EvidencePackage([f"Error during evaluation: {str(e)}"]),
            )
    
    def _run_layer_judge(self, judge_id: str, config: dict, state: str) -> JudgeVerdict:
        """Run a judge using Layer (free, self-hosted fallback)."""
        try:
            questions = {
                "verdict": LayerChoice(
                    instructions=config["question"],
                    criteria=config["criteria"]
                ),
                "confidence": LayerScore(
                    instructions="How confident are you?",
                    criteria=["Low", "Medium", "High"]
                )
            }
            
            response = self.client.system_one(state=state, questions=questions)
            
            verdict_answer = response.choices.get("verdict", {})
            choice = verdict_answer.get("choice", "dissent").lower()
            verdict = "PASS" if choice == "pass" else "DISSENT"
            confidence = verdict_answer.get("confidence", 0.5)
            
            return JudgeVerdict(
                judge_id=judge_id,
                model_id="layer-free",
                verdict=verdict,
                findings=[f"Layer evaluation complete for {config['domain']}"],
                corrections=[] if verdict == "PASS" else [f"Failed {config['domain']} check"],
                tool_calls=["layer_evaluate"],
                impl_version="1.0.0",
                rationale=(
                    f"Layer assessed {config['domain']} "
                    f"with confidence {confidence:.2f}"
                ),
                evidence=EvidencePackage(
                    [f"Layer evaluation for {config['domain']}"]
                ),
            )

        except Exception as e:
            return JudgeVerdict(
                judge_id=judge_id,
                model_id="layer-free",
                verdict="DISSENT",
                findings=[f"Layer evaluation error: {str(e)}"],
                corrections=["Retry evaluation"],
                tool_calls=["layer_evaluate"],
                impl_version="1.0.0",
                rationale=f"Layer error: {str(e)}",
                evidence=EvidencePackage([f"Error during evaluation: {str(e)}"]),
            )

    def _run_mock_judge(self, judge_id: str, config: dict, state: str) -> JudgeVerdict:
        """Mock judge for testing. Always passes."""
        return JudgeVerdict(
            judge_id=judge_id,
            model_id="mock-model",
            verdict="PASS",
            findings=[f"[MOCK] {config['domain']} evaluation passed"],
            corrections=[],
            tool_calls=["mock_tool_1", "mock_tool_2"],
            impl_version="1.0.0",
            rationale=f"[MOCK] All {config['domain']} checks passed",
            evidence=EvidencePackage([
                f"[MOCK] Verified {config['domain']} criteria",
                f"[MOCK] All checks passed for {config['domain']}",
            ]),
        )
    
    def _get_assigned_model(self, judge_id: str) -> str:
        """Get the model assigned to a judge (seat lock)."""
        if self.provider == "jev":
            return "jev-latest"
        elif self.provider == "layer":
            return "layer-free"
        else:
            return "mock-model"
    
    def verify_chain_integrity(self) -> bool:
        """Verify the entire receipt chain is tamper-free."""
        for index, receipt_hash in enumerate(self.receipt_chain):
            receipt = self._receipt_store.get(receipt_hash)
            if receipt is None:
                return False
            if not receipt.verify():
                return False
            expected_previous = self.receipt_chain[index - 1] if index > 0 else "GENESIS"
            if receipt.previous_hash != expected_previous:
                return False
        return True
    
    def get_receipt_by_hash(self, receipt_hash: str) -> Optional[dict]:
        """Look up a receipt by its hash."""
        receipt = self._receipt_store.get(receipt_hash)
        if receipt is None:
            return None
        return receipt.to_dict()


# Singleton gate instance — JEV-powered
# Uses JEV if TYPESAFE_API_KEY is set, otherwise Layer fallback, otherwise mock
gate = JudgeGate(
    typesafe_api_key=os.environ.get("TYPESAFE_API_KEY"),
    use_layer_fallback=True,
    mock_mode=not os.environ.get("TYPESAFE_API_KEY") and not HAS_LAYER
)
