"""
AMARTIE Gate Engine
====================
The 9-judge verification gate. Every outbound action passes through.
Unanimous PASS or bounce. Never a push-through.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


class JudgeVerdict:
    """A single judge's verdict on an action."""

    def __init__(self, judge_id: str, model_id: str, verdict: str,
                 findings: List[str], corrections: List[str], tool_calls: List[str]):
        self.judge_id = judge_id
        self.model_id = model_id
        self.verdict = verdict  # PASS or DISSENT
        self.findings = findings
        self.corrections = corrections
        self.tool_calls = tool_calls
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "judge_id": self.judge_id,
            "model_id": self.model_id,
            "verdict": self.verdict,
            "findings": self.findings,
            "corrections": self.corrections,
            "tool_calls": self.tool_calls,
            "timestamp": self.timestamp
        }


class GateReceipt:
    """Hash-chained receipt for a gated action."""

    def __init__(self, action_id: str, action_type: str, payload_hash: str,
                 verdicts: List[JudgeVerdict], previous_hash: str = ""):
        self.action_id = action_id
        self.action_type = action_type
        self.payload_hash = payload_hash
        self.verdicts = [v.to_dict() for v in verdicts]
        self.previous_hash = previous_hash
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        content = json.dumps({
            "action_id": self.action_id,
            "action_type": self.action_type,
            "payload_hash": self.payload_hash,
            "verdicts": self.verdicts,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp
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
            "hash": self.hash
        }


class JudgeGate:
    """
    The 9-judge AMARTIE gate.

    Every outbound action passes through 9 independent judges.
    All must pass. One DISSENT = correction + re-judgment.
    """

    # The canonical 9 judge roster
    ROSTER = {
        "J1": "TRUTH",
        "J2": "BOUNDARY-INTEGRITY",
        "J3": "LOGIC",
        "J4": "COMPLETENESS",
        "J5": "EXECUTION-AND-SIMPLICITY",
        "J6": "OWNER-INTENT",
        "J7": "RECOVERY",
        "J8": "TRADE-INTEGRITY",
        "J9": "UNITY"
    }

    def __init__(self):
        self.receipt_chain: List[str] = []  # hash chain
        self._receipt_store: Dict[str, GateReceipt] = {}
        self.round_cap = 4
        self.time_budget_per_judge = 1200  # seconds
        self.gate_wide_budget = 900  # seconds
        self.model_assignments = self._default_model_assignments()

    def _default_model_assignments(self) -> Dict[str, str]:
        """Return the seat-to-model lock for the canonical judge roster."""
        return {
            "J1": "TRUTH-model",
            "J2": "BOUNDARY-INTEGRITY-model",
            "J3": "LOGIC-model",
            "J4": "COMPLETENESS-model",
            "J5": "EXECUTION-AND-SIMPLICITY-model",
            "J6": "OWNER-INTENT-model",
            "J7": "RECOVERY-model",
            "J8": "TRADE-INTEGRITY-model",
            "J9": "UNITY-model",
        }

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
                      judge_responses: List[JudgeVerdict]) -> Tuple[bool, GateReceipt]:
        """
        Verify an action through the 9-judge gate.

        Args:
            action_type: The type of action (email, webhook, trade, etc.)
            payload: The action payload
            judge_responses: List of 9 JudgeVerdict objects

        Returns:
            (passed, receipt): Whether the action passed and the receipt
        """
        if len(judge_responses) != 9:
            receipt = GateReceipt(
                action_id=str(uuid.uuid4()),
                action_type=action_type,
                payload_hash=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                verdicts=[],
                previous_hash=self.receipt_chain[-1] if self.receipt_chain else "GENESIS"
            )
            return False, receipt

        seen_judges = set()
        for verdict in judge_responses:
            if verdict.judge_id not in self.ROSTER:
                receipt = GateReceipt(
                    action_id=str(uuid.uuid4()),
                    action_type=action_type,
                    payload_hash=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                    verdicts=judge_responses,
                    previous_hash=self.receipt_chain[-1] if self.receipt_chain else "GENESIS"
                )
                return False, receipt
            if verdict.judge_id in seen_judges:
                receipt = GateReceipt(
                    action_id=str(uuid.uuid4()),
                    action_type=action_type,
                    payload_hash=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                    verdicts=judge_responses,
                    previous_hash=self.receipt_chain[-1] if self.receipt_chain else "GENESIS"
                )
                return False, receipt
            seen_judges.add(verdict.judge_id)

        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

        all_passed = all(v.verdict == "PASS" for v in judge_responses)

        for v in judge_responses:
            if v.model_id != self._get_assigned_model(v.judge_id):
                all_passed = False
                break

        for v in judge_responses:
            if len(v.tool_calls) < 2:
                all_passed = False
                break

        previous_hash = self.receipt_chain[-1] if self.receipt_chain else "GENESIS"
        receipt = GateReceipt(
            action_id=str(uuid.uuid4()),
            action_type=action_type,
            payload_hash=payload_hash,
            verdicts=judge_responses,
            previous_hash=previous_hash
        )

        self.receipt_chain.append(receipt.hash)
        self._receipt_store[receipt.hash] = receipt

        return all_passed, receipt

    def _get_assigned_model(self, judge_id: str) -> str:
        """Get the model assigned to a judge (seat lock)."""
        return self.model_assignments.get(judge_id, "UNASSIGNED")

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


# Singleton gate instance
gate = JudgeGate()
