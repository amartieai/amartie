# Tests for AMARTIE Gate Engine
import json
import tempfile
from pathlib import Path

import pytest

from amartie.gate import EXPECTED_JUDGE_IDS, GateReceipt, JudgeGate, JudgeVerdict


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

    def test_from_dict_preserves_timestamp(self):
        v = JudgeVerdict(
            judge_id="J1",
            model_id="test",
            verdict="PASS",
            findings=["x"],
            corrections=[],
            tool_calls=["a", "b"],
            timestamp="2026-09-18T12:00:00+00:00",
        )
        d = v.to_dict()
        v2 = JudgeVerdict.from_dict(d)
        assert v2.timestamp == "2026-09-18T12:00:00+00:00"
        assert v2.judge_id == "J1"

    def test_from_dict_defaults_timestamp(self):
        v = JudgeVerdict.from_dict({
            "judge_id": "J1",
            "model_id": "test",
            "verdict": "PASS",
        })
        assert v.timestamp is not None


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
            verdicts=[v.to_dict()],
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
            verdicts=[v.to_dict()],
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
            verdicts=[v.to_dict()],
            previous_hash="GENESIS",
        )
        r.hash = "tampered"
        assert r.verify() is False

    def test_from_dict_preserves_timestamp(self):
        r = GateReceipt(
            action_id="test",
            action_type="test",
            payload_hash="test",
            verdicts=[],
            previous_hash="GENESIS",
            timestamp="2026-09-18T12:00:00+00:00",
        )
        d = r.to_dict()
        r2 = GateReceipt.from_dict(d)
        assert r2.timestamp == "2026-09-18T12:00:00+00:00"
        assert r2.verify() is True
        assert r2.hash == r.hash

    def test_payload_tamper_detectable(self):
        r = GateReceipt(
            action_id="test",
            action_type="test",
            payload_hash="original",
            verdicts=[],
        )
        d = r.to_dict()
        d["payload_hash"] = "modified"
        r2 = GateReceipt.from_dict(d)
        assert r2.verify() is False

    def test_verdict_tamper_detectable(self):
        r = GateReceipt(
            action_id="test",
            action_type="test",
            payload_hash="test",
            verdicts=[{"judge_id": "J1", "verdict": "PASS"}],
        )
        d = r.to_dict()
        d["verdicts"][0]["verdict"] = "DISSENT"
        r2 = GateReceipt.from_dict(d)
        assert r2.verify() is False

    def test_previous_hash_tamper_fails(self):
        r = GateReceipt(
            action_id="test",
            action_type="test",
            payload_hash="test",
            verdicts=[],
            previous_hash="GENESIS",
        )
        d = r.to_dict()
        d["previous_hash"] = "FAKE"
        r2 = GateReceipt.from_dict(d)
        assert r2.verify() is False

    def test_rejects_non_sha256(self):
        with pytest.raises(ValueError):
            GateReceipt(
                action_id="bad",
                action_type="test",
                payload_hash="hash",
                verdicts=[],
                hash_algorithm="sha1",
            )


class TestJudgeGate:
    def _make_verdicts(self, verdict="PASS", count=9, tool_calls=None):
        if tool_calls is None:
            tool_calls = ["cmd1", "cmd2"]
        verdicts = []
        for i in range(count):
            v = JudgeVerdict(
                judge_id=f"J{i + 1}",
                model_id="test-model",
                verdict=verdict,
                findings=["verified"],
                corrections=[],
                tool_calls=tool_calls if verdict == "PASS" else [],
            )
            verdicts.append(v)
        return verdicts

    def _make_gate(self, tmp_path, **kwargs):
        """Create a JudgeGate with a temporary store path."""
        store = tmp_path / "receipts.json"
        return JudgeGate(receipt_store_path=str(store), **kwargs)

    def test_create_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = self._make_gate(Path(tmp))
            assert len(g.JUDGE_REGISTRY) == 9
            assert g.round_cap == 4

    def test_get_rotated_judge_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = self._make_gate(Path(tmp))
            rotated = g.get_rotated_judge_id("J1", "2026-09-17")
            assert "J1" in rotated
            assert len(rotated) > len("J1")

    def test_rotation_changes_daily(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = self._make_gate(Path(tmp))
            id1 = g.get_rotated_judge_id("J1", "2026-09-17")
            id2 = g.get_rotated_judge_id("J1", "2026-09-18")
            assert id1 != id2

    def test_verify_action_pass(self, tmp_path):
        g = self._make_gate(tmp_path)
        verdicts = self._make_verdicts()
        passed, receipt = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed is True
        assert receipt.hash is not None
        assert len(receipt.hash) == 64

    def test_verify_action_fail_on_dissent(self, tmp_path):
        g = self._make_gate(tmp_path)
        verdicts = self._make_verdicts()
        # Change last to DISSENT
        verdicts[8] = JudgeVerdict(
            judge_id="J9",
            model_id="test-model",
            verdict="DISSENT",
            findings=[],
            corrections=["fix this"],
            tool_calls=["cmd1", "cmd2"],
        )
        passed, receipt = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed is False

    def test_verify_action_fail_on_rubber_stamp(self, tmp_path):
        g = self._make_gate(tmp_path)
        verdicts = self._make_verdicts(tool_calls=["cmd1"])  # Only 1 tool call
        passed, receipt = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed is False

    def test_chain_integrity(self, tmp_path):
        g = self._make_gate(tmp_path)
        assert g.verify_chain_integrity() is True  # Empty chain

        verdicts = self._make_verdicts()
        g.verify_action("test1", {"a": 1}, verdicts)
        g.verify_action("test2", {"b": 2}, verdicts)
        assert g.verify_chain_integrity() is True
        assert len(g.receipt_chain) == 2

    def test_missing_or_unknown_judge_ids_fail(self, tmp_path):
        g = self._make_gate(tmp_path)
        verdicts = self._make_verdicts()
        # Replace J9 with bad ID
        verdicts[8] = JudgeVerdict(
            judge_id="BAD-JUDGE",
            model_id="test-model",
            verdict="PASS",
            findings=["verified"],
            corrections=[],
            tool_calls=["cmd1", "cmd2"],
        )
        passed, _ = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed is False

    def test_duplicate_judge_ids_fail(self, tmp_path):
        g = self._make_gate(tmp_path)
        verdicts = self._make_verdicts()
        # Replace J9 with duplicate of J1
        verdicts[8] = JudgeVerdict(
            judge_id="J1",
            model_id="test-model",
            verdict="PASS",
            findings=["verified"],
            corrections=[],
            tool_calls=["cmd1", "cmd2"],
        )
        passed, _ = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed is False

    def test_wrong_number_of_verdicts_fails(self, tmp_path):
        g = self._make_gate(tmp_path)
        verdicts = self._make_verdicts(count=8)  # Only 8
        passed, _ = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed is False

    def test_model_lock_correct_passes(self, tmp_path):
        g = self._make_gate(tmp_path, strict_model_lock=True)
        g.model_registry = {f"J{i}": "assigned-model" for i in range(1, 10)}
        verdicts = self._make_verdicts()
        for v in verdicts:
            v.model_id = "assigned-model"
        passed, _ = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed is True

    def test_model_lock_wrong_fails(self, tmp_path):
        g = self._make_gate(tmp_path, strict_model_lock=True)
        g.model_registry = {f"J{i}": "assigned-model" for i in range(1, 10)}
        verdicts = self._make_verdicts()
        verdicts[0].model_id = "wrong-model"
        passed, _ = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed is False

    def test_model_lock_missing_fails(self, tmp_path):
        g = self._make_gate(tmp_path, strict_model_lock=True)
        g.model_registry = {f"J{i}": "assigned-model" for i in range(1, 10)}
        # Remove one registry entry
        del g.model_registry["J5"]
        verdicts = self._make_verdicts()
        for v in verdicts:
            v.model_id = "assigned-model"
        passed, _ = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed is False

    def test_persisted_receipts_reload_identical(self, tmp_path):
        g = self._make_gate(tmp_path)
        verdicts = self._make_verdicts()
        g.verify_action("persist-test", {"x": 1}, verdicts)

        # Load a new gate from the same store
        g2 = self._make_gate(tmp_path)
        assert len(g2.receipts) == 1
        assert g2.receipts[0].hash == g.receipts[0].hash
        assert g2.receipts[0].timestamp == g.receipts[0].timestamp
        assert g2.verify_chain_integrity() is True

    def test_corrupted_persistence_fails_validation(self, tmp_path):
        store = tmp_path / "receipts.json"
        # Write corrupted data
        store.write_text("not valid json")
        g = JudgeGate(receipt_store_path=str(store))
        # Should not crash, should have empty receipts
        assert len(g.receipts) == 0

    def test_corrupted_first_receipt_fails_closed(self, tmp_path):
        """If the first receipt is corrupted, the entire store fails closed."""
        g = self._make_gate(tmp_path)
        verdicts = self._make_verdicts()
        g.verify_action("t1", {"a": 1}, verdicts)
        g.verify_action("t2", {"b": 2}, verdicts)

        # Tamper with the FIRST receipt only
        store = tmp_path / "receipts.json"
        data = json.loads(store.read_text())
        data[0]["hash"] = "tampered_first"
        store.write_text(json.dumps(data))

        # Reload — entire store should fail closed
        g2 = self._make_gate(tmp_path)
        assert g2.store_corrupted is True
        assert len(g2.receipts) == 0
        assert g2.verify_chain_integrity() is False

    def test_corrupted_second_receipt_fails_closed(self, tmp_path):
        """If any receipt is corrupted, the entire store fails closed."""
        g = self._make_gate(tmp_path)
        verdicts = self._make_verdicts()
        g.verify_action("t1", {"a": 1}, verdicts)
        g.verify_action("t2", {"b": 2}, verdicts)
        g.verify_action("t3", {"c": 3}, verdicts)

        # Tamper with the MIDDLE receipt
        store = tmp_path / "receipts.json"
        data = json.loads(store.read_text())
        data[1]["hash"] = "tampered_middle"
        store.write_text(json.dumps(data))

        # Reload — entire store should fail closed
        g2 = self._make_gate(tmp_path)
        assert g2.store_corrupted is True
        assert len(g2.receipts) == 0

    def test_broken_chain_link_fails_closed(self, tmp_path):
        """If chain links are broken, the store fails closed."""
        g = self._make_gate(tmp_path)
        verdicts = self._make_verdicts()
        g.verify_action("t1", {"a": 1}, verdicts)
        g.verify_action("t2", {"b": 2}, verdicts)

        # Break the chain link
        store = tmp_path / "receipts.json"
        data = json.loads(store.read_text())
        data[1]["previous_hash"] = "broken_link"
        store.write_text(json.dumps(data))

        g2 = self._make_gate(tmp_path)
        assert g2.store_corrupted is True
        assert len(g2.receipts) == 0

    def test_receipt_chain_tamper_detected(self, tmp_path):
        g = self._make_gate(tmp_path)
        verdicts = self._make_verdicts()
        g.verify_action("t1", {"a": 1}, verdicts)
        g.verify_action("t2", {"b": 2}, verdicts)
        assert len(g.receipts) == 2

        # Tamper with the persisted file
        store = tmp_path / "receipts.json"
        data = json.loads(store.read_text())
        data[0]["hash"] = "tampered"
        store.write_text(json.dumps(data))

        # Reload — entire store should fail closed
        g2 = self._make_gate(tmp_path)
        assert g2.store_corrupted is True
        assert len(g2.receipts) == 0
        assert g2.verify_chain_integrity() is False

    def test_no_test_writes_to_home(self, tmp_path):
        """Verify no test writes to the user's real ~/.amartie."""
        # The _make_gate helper uses tmp_path, not home
        home_store = Path.home() / ".amartie" / "receipts.json"
        mtime_before = home_store.stat().st_mtime if home_store.exists() else None
        
        g = self._make_gate(tmp_path)
        verdicts = self._make_verdicts()
        g.verify_action("home-check", {"x": 1}, verdicts)
        
        # Home store should not have been modified
        if mtime_before is not None:
            mtime_after = home_store.stat().st_mtime if home_store.exists() else None
            assert mtime_after == mtime_before, "Home receipt store was modified by test"
