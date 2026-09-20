"""Regression tests for the PR #20 review findings (Hermes fixes).

Finding 2: strict model-lock must fail closed with an EMPTY registry.
Finding 6: roster_reason must be recorded in the receipt, not discarded.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amartie.gate import JudgeGate, JudgeVerdict  # noqa: E402


def make_verdict(judge_id, verdict="PASS", model_id="m1", tool_calls=("a", "b")):
    return JudgeVerdict(
        judge_id=judge_id,
        model_id=model_id,
        verdict=verdict,
        tool_calls=list(tool_calls),
        rationale="ok",
    )


def all_nine(model_id="m1"):
    return [make_verdict(f"J{i}", model_id=model_id) for i in range(1, 10)]


def make_gate(**kwargs):
    """Isolated receipt store per test — never touch the shared home store."""
    tmp = tempfile.mkdtemp()
    return JudgeGate(receipt_store_path=str(Path(tmp) / "receipts.json"), **kwargs)


class TestStrictModelLockEmptyRegistry:
    def test_empty_registry_fails_closed(self):
        # review finding 2: strict lock + empty registry = FAIL, not bypass
        gate = make_gate(strict_model_lock=True)
        gate.model_registry = {}
        assert gate.model_registry == {}
        passed, receipt = gate.verify_action(
            "tool.call", {"x": 1}, all_nine())
        assert passed is False

    def test_empty_registry_with_no_model_id_fails(self):
        gate = make_gate(strict_model_lock=True)
        gate.model_registry = {}
        verdicts = all_nine()
        verdicts = [JudgeVerdict(judge_id=v.judge_id, model_id=None,
                                 verdict="PASS", tool_calls=["a", "b"],
                                 rationale="ok") for v in verdicts]
        passed, _ = gate.verify_action("tool.call", {"x": 1}, verdicts)
        assert passed is False

    def test_registered_matching_models_pass(self):
        # control: strict lock passes when every judge ran its assigned model
        gate = make_gate(strict_model_lock=True)
        gate.model_registry = {f"J{i}": "m1" for i in range(1, 10)}
        passed, _ = gate.verify_action("tool.call", {"x": 1}, all_nine())
        assert passed is True

    def test_wrong_model_fails_even_with_registry(self):
        gate = make_gate(strict_model_lock=True)
        gate.model_registry = {f"J{i}": "m1" for i in range(1, 10)}
        verdicts = all_nine()
        verdicts[3].model_id = "wrong-model"
        passed, _ = gate.verify_action("tool.call", {"x": 1}, verdicts)
        assert passed is False


class TestRosterReasonRecorded:
    def test_roster_reason_in_receipt_metadata(self):
        # review finding 6: the machine-readable roster reason must be
        # available on the receipt, not computed and discarded
        gate = make_gate()
        gate.model_registry = {}
        # 8 judges = invalid roster -> reason recorded
        verdicts = all_nine()[:8]
        passed, receipt = gate.verify_action("tool.call", {"x": 1}, verdicts)
        assert passed is False
        assert receipt.metadata.get("roster_valid") is False
        assert isinstance(receipt.metadata.get("roster_reason"), str)
        assert len(receipt.metadata["roster_reason"]) > 0
        assert receipt.metadata.get("executed") is False
        # and the receipt still verifies with its metadata
        assert receipt.verify()

    def test_valid_roster_records_reason_too(self):
        gate = make_gate()
        gate.model_registry = {}
        passed, receipt = gate.verify_action("tool.call", {"x": 1}, all_nine())
        assert passed is True
        assert receipt.metadata.get("roster_valid") is True
        assert receipt.metadata.get("executed") is True
        assert receipt.verify()


if __name__ == "__main__":
    import unittest
    unittest.main()
