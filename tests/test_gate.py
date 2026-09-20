# Tests for AMARTIE Gate Engine

import pytest

from amartie.gate import GateReceipt, JudgeGate, JudgeVerdict, gate


class TestJudgeVerdict:
    def test_create_verdict(self):
        v = JudgeVerdict(
            judge_id="J1",
            model_id="claude-3-5-sonnet",
            verdict="PASS",
            findings=["Claim verified"],
            corrections=[],
            tool_calls=["ls", "cat /etc/hosts"],
        )
        assert v.verdict == "PASS"
        assert v.judge_id == "J1"
        assert len(v.findings) == 1

    def test_to_dict(self):
        v = JudgeVerdict(
            judge_id="J1",
            model_id="claude-3-5-sonnet",
            verdict="PASS",
            findings=["test"],
            corrections=[],
            tool_calls=["cmd"],
        )
        d = v.to_dict()
        assert "judge_id" in d
        assert "model_id" in d
        assert "verdict" in d
        assert "timestamp" in d


class TestGateReceipt:
    def test_create_receipt(self):
        v = JudgeVerdict(
            judge_id="J1",
            model_id="claude-3-5-sonnet",
            verdict="PASS",
            findings=["test"],
            corrections=[],
            tool_calls=["cmd"],
        )
        r = GateReceipt(
            action_id="test-123",
            action_type="email-send",
            payload_hash="abc123",
            verdicts=[v],
            previous_hash="GENESIS",
        )
        assert r.action_id == "test-123"
        assert r.previous_hash == "GENESIS"
        assert len(r.hash) == 64

    def test_hash_verification(self):
        v = JudgeVerdict(
            judge_id="J1",
            model_id="test",
            verdict="PASS",
            findings=[],
            corrections=[],
            tool_calls=["cmd"],
        )
        r = GateReceipt(
            action_id="test",
            action_type="test",
            payload_hash="test",
            verdicts=[v],
            previous_hash="GENESIS",
        )
        assert r.verify() is True

    def test_tamper_detection(self):
        v = JudgeVerdict(
            judge_id="J1",
            model_id="test",
            verdict="PASS",
            findings=[],
            corrections=[],
            tool_calls=["cmd"],
        )
        r = GateReceipt(
            action_id="test",
            action_type="test",
            payload_hash="test",
            verdicts=[v],
            previous_hash="GENESIS",
        )
        r.hash = "tampered"
        assert r.verify() is False


class TestJudgeGate:
    def test_create_gate(self):
        g = JudgeGate()
        assert len(g.JUDGE_REGISTRY) == 9
        assert g.round_cap == 4

    def test_get_rotated_judge_id(self):
        g = JudgeGate()
        rotated = g.get_rotated_judge_id("J1", "2026-09-17")
        assert "J1" in rotated
        assert len(rotated) > len("J1")

    def test_rotation_changes_daily(self):
        g = JudgeGate()
        id1 = g.get_rotated_judge_id("J1", "2026-09-17")
        id2 = g.get_rotated_judge_id("J1", "2026-09-18")
        assert id1 != id2

    def test_verify_action_pass(self):
        g = JudgeGate()
        verdicts = []
        for i in range(9):
            v = JudgeVerdict(
                judge_id=f"J{i + 1}",
                model_id="test-model",
                verdict="PASS",
                findings=["verified"],
                corrections=[],
                tool_calls=["cmd1", "cmd2"],
            )
            verdicts.append(v)

        passed, receipt = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed is True
        assert receipt.hash is not None

    def test_verify_action_fail_on_dissent(self):
        g = JudgeGate()
        verdicts = []
        for i in range(9):
            verdict = "PASS" if i < 8 else "DISSENT"
            v = JudgeVerdict(
                judge_id=f"J{i + 1}",
                model_id="test-model",
                verdict=verdict,
                findings=["verified"] if verdict == "PASS" else [],
                corrections=["fix this"] if verdict == "DISSENT" else [],
                tool_calls=["cmd1", "cmd2"],
            )
            verdicts.append(v)

        passed, receipt = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed is False

    def test_verify_action_fail_on_rubber_stamp(self):
        g = JudgeGate()
        verdicts = []
        for i in range(9):
            v = JudgeVerdict(
                judge_id=f"J{i + 1}",
                model_id="test-model",
                verdict="PASS",
                findings=["verified"],
                corrections=[],
                tool_calls=["cmd1"],
            )
            verdicts.append(v)

        passed, receipt = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed is False

    def test_chain_integrity(self):
        g = JudgeGate()
        assert g.verify_chain_integrity() is True

        verdicts = []
        for i in range(9):
            v = JudgeVerdict(
                judge_id=f"J{i + 1}",
                model_id="test-model",
                verdict="PASS",
                findings=["verified"],
                corrections=[],
                tool_calls=["cmd1", "cmd2"],
            )
            verdicts.append(v)

        g.verify_action("test1", {"a": 1}, verdicts)
        g.verify_action("test2", {"b": 2}, verdicts)
        assert g.verify_chain_integrity() is True
        assert len(g.receipt_chain) == 2

    def test_missing_or_unknown_judge_ids_fail(self):
        g = JudgeGate()
        verdicts = []
        for i in range(9):
            judge_id = f"J{i + 1}" if i < 8 else "BAD-JUDGE"
            v = JudgeVerdict(
                judge_id=judge_id,
                model_id="test-model",
                verdict="PASS",
                findings=["verified"],
                corrections=[],
                tool_calls=["cmd1", "cmd2"],
            )
            verdicts.append(v)

        passed, _ = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed is False
