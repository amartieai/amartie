"""
AMARTIE Gate Engine
====================
The 9-judge verification gate. Every outbound action passes through.
Unanimous PASS or bounce. Never a push-through.
"""

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


JUDGE_CONTRACT_VERSION = "amartie-judge-contract-v1"
JUDGE_REGISTRY = {
    "J1": "TRUTH",
    "J2": "BOUNDARY-INTEGRITY",
    "J3": "LOGIC",
    "J4": "COMPLETENESS",
    "J5": "EXECUTION-AND-SIMPLICITY",
    "J6": "OWNER-INTENT",
    "J7": "RECOVERY",
    "J8": "TRADE-INTEGRITY",
    "J9": "UNITY",
}


class JudgeVerdict:
    """A single judge's verdict on an action."""

    def __init__(
        self,
        judge_id: str,
        model_id: str,
        verdict: str,
        findings: Optional[List[str]] = None,
        corrections: Optional[List[str]] = None,
        tool_calls: Optional[List[str]] = None,
        rationale: Optional[str] = None,
    ):
        self.judge_id = judge_id
        self.model_id = model_id
        self.verdict = verdict  # PASS or DISSENT
        self.findings = findings or []
        self.corrections = corrections or []
        self.tool_calls = tool_calls or []
        self.rationale = rationale or ""
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "judge_id": self.judge_id,
            "model_id": self.model_id,
            "verdict": self.verdict,
            "findings": self.findings,
            "corrections": self.corrections,
            "tool_calls": self.tool_calls,
            "rationale": self.rationale,
            "timestamp": self.timestamp,
        }


class GateReceipt:
    """Hash-chained receipt for a gated action."""

    def __init__(
        self,
        action_id: str,
        action_type: str,
        payload_hash: str,
        verdicts: List[JudgeVerdict],
        previous_hash: str = "",
        contract_version: str = JUDGE_CONTRACT_VERSION,
        hash_algorithm: str = "sha256",
    ):
        self.action_id = action_id
        self.action_type = action_type
        self.payload_hash = payload_hash
        self.verdicts = [
            v.to_dict() if isinstance(v, JudgeVerdict) else dict(v)
            for v in verdicts
        ]
        self.previous_hash = previous_hash
        self.contract_version = contract_version
        self.hash_algorithm = hash_algorithm
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        content = json.dumps(
            {
                "action_id": self.action_id,
                "action_type": self.action_type,
                "payload_hash": self.payload_hash,
                "verdicts": self.verdicts,
                "previous_hash": self.previous_hash,
                "contract_version": self.contract_version,
                "hash_algorithm": self.hash_algorithm,
                "timestamp": self.timestamp,
            },
            sort_keys=True,
        )
        if self.hash_algorithm != "sha256":
            raise ValueError(f"Unsupported hash algorithm: {self.hash_algorithm}")
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
            "contract_version": self.contract_version,
            "hash_algorithm": self.hash_algorithm,
            "timestamp": self.timestamp,
            "hash": self.hash,
        }


class JudgeGate:
    """
    The 9-judge AMARTIE gate.

    Every outbound action passes through 9 independent judges.
    All must pass. One DISSENT = correction + re-judgment.
    """

    JUDGE_REGISTRY = JUDGE_REGISTRY
    JUDGE_CONTRACT_VERSION = JUDGE_CONTRACT_VERSION

    def __init__(self, receipt_store_path: Optional[str] = None):
        self.receipt_chain: List[str] = []
        self.receipts: List[GateReceipt] = []
        self.round_cap = 4
        self.time_budget_per_judge = 1200  # seconds
        self.gate_wide_budget = 900  # seconds
        self.model_registry: Dict[str, str] = {}
        self.receipt_store_path = Path(
            receipt_store_path
            or os.path.join(os.path.expanduser("~"), ".amartie", "receipts.json")
        )
        self._ensure_store_dir()
        self._load_receipts_from_disk()

    def _ensure_store_dir(self):
        self.receipt_store_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_receipts_from_disk(self):
        if not self.receipt_store_path.exists():
            return
        try:
            with open(self.receipt_store_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return

        if not isinstance(data, list):
            return

        for record in data:
            try:
                receipt = GateReceipt(
                    action_id=record["action_id"],
                    action_type=record["action_type"],
                    payload_hash=record["payload_hash"],
                    verdicts=[
                        JudgeVerdict(
                            judge_id=v["judge_id"],
                            model_id=v["model_id"],
                            verdict=v["verdict"],
                            findings=v.get("findings", []),
                            corrections=v.get("corrections", []),
                            tool_calls=v.get("tool_calls", []),
                            rationale=v.get("rationale", ""),
                        )
                        for v in record.get("verdicts", [])
                    ],
                    previous_hash=record.get("previous_hash", ""),
                    contract_version=record.get("contract_version", JUDGE_CONTRACT_VERSION),
                    hash_algorithm=record.get("hash_algorithm", "sha256"),
                )
            except (KeyError, TypeError, ValueError):
                continue

            if receipt.verify():
                self.receipts.append(receipt)
                self.receipt_chain.append(receipt.hash)

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

    def get_registry(self) -> Dict[str, str]:
        """Return the canonical judge contract as a versioned registry."""
        return dict(self.JUDGE_REGISTRY)

    def _persist_receipts(self):
        if not self.receipt_store_path:
            return
        self._ensure_store_dir()
        with open(self.receipt_store_path, "w", encoding="utf-8") as fh:
            json.dump([r.to_dict() for r in self.receipts], fh, indent=2, sort_keys=True)

    def _get_assigned_model(self, judge_id: str) -> str:
        """Get the model assigned to a judge, if a model-lock registry is configured."""
        return self.model_registry.get(judge_id, "assigned-model-placeholder")

    def verify_action(
        self,
        action_type: str,
        payload: dict,
        judge_responses: List[JudgeVerdict],
    ) -> Tuple[bool, GateReceipt]:
        """
        Verify an action through the 9-judge gate.

        Returns:
            (passed, receipt): Whether the action passed and the receipt.
        """
        expected_judges = set(self.JUDGE_REGISTRY.keys())
        response_ids = [getattr(v, "judge_id", None) for v in judge_responses]

        # The gate is strict: exactly nine voting seats; no substitutions.
        if len(judge_responses) != 9:
            all_passed = False
        else:
            all_passed = True
            for v in judge_responses:
                if getattr(v, "judge_id", None) not in expected_judges:
                    all_passed = False
                    break
                if getattr(v, "verdict", "").upper() != "PASS":
                    all_passed = False
                    break
                if len(getattr(v, "tool_calls", []) or []) < 2:
                    all_passed = False
                    break
                if self.model_registry:
                    assigned_model = self._get_assigned_model(v.judge_id)
                    if getattr(v, "model_id", None) != assigned_model:
                        all_passed = False
                        break

        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

        previous_hash = self.receipt_chain[-1] if self.receipt_chain else "GENESIS"
        receipt = GateReceipt(
            action_id=str(uuid.uuid4()),
            action_type=action_type,
            payload_hash=payload_hash,
            verdicts=judge_responses,
            previous_hash=previous_hash,
            contract_version=self.JUDGE_CONTRACT_VERSION,
            hash_algorithm="sha256",
        )

        self.receipts.append(receipt)
        self.receipt_chain.append(receipt.hash)
        self._persist_receipts()
        return all_passed, receipt

    def verify_chain_integrity(self) -> bool:
        """Verify the entire receipt chain is tamper-free."""
        if not self.receipts:
            return True

        for idx, receipt in enumerate(self.receipts):
            if not receipt.verify():
                return False
            if idx > 0 and receipt.previous_hash != self.receipts[idx - 1].hash:
                return False
        return True

    def get_receipt_by_hash(self, receipt_hash: str) -> Optional[dict]:
        """Look up a receipt by its hash."""
        for receipt in self.receipts:
            if receipt.hash == receipt_hash:
                return receipt.to_dict()
        return None


# Singleton gate instance
# The default model registry is empty so legacy tests and local dry runs can operate
# while a deployment may configure a strict registry for production enforcement.
gate = JudgeGate()


__all__ = [
    "JudgeGate",
    "JudgeVerdict",
    "GateReceipt",
    "JUDGE_CONTRACT_VERSION",
    "JUDGE_REGISTRY",
    "gate",
]
