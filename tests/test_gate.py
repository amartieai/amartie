# Tests for AMARTIE Gate Engine

import pytest
import json
import hashlib
from amartie.gate import (
    JudgeGate, JudgeVerdict, GateReceipt, gate,
    EvidencePackage,
)


def _make_verdict(judge_id, model_id, verdict="PASS",
                  findings=None, corrections=None,
                  tool_calls=None, evidence_items=None):
    """Helper to build JudgeVerdict with required evidence contract fields."""
    return JudgeVerdict(
        judge_id=judge_id,
        model_id=model_id,
        verdict=verdict,
        findings=findings or ["verified"],
        corrections=corrections or [],
        tool_calls=tool_calls or ["cmd1", "cmd2"],
        evidence=EvidencePackage(evidence_items or ["Verified evidence"]),
    )


class TestJudgeVerdict:
    def test_create_verdict(self):
        v = JudgeVerdict(
            judge_id="J1-TRUTH",
            model_id="claude-3-5-sonnet",
            verdict="PASS",
            findings=["Claim verified"],
            corrections=[],
            tool_calls=["ls", "cat /etc/hosts"],
            evidence=EvidencePackage(["Checked /etc/hosts"]),
        )
        assert v.verdict == "PASS"
        assert v.judge_id == "J1-TRUTH"
        assert len(v.findings) == 1
        assert v.impl_version == "1.0.0"
        assert v.evidence.is_sufficient() is True

    def test_to_dict(self):
        v = JudgeVerdict(
            judge_id="J1-TRUTH",
            model_id="claude-3-5-sonnet",
            verdict="PASS",
            findings=["test"],
            corrections=[],
            tool_calls=["cmd"],
            evidence=EvidencePackage(["test evidence"]),
        )
        d = v.to_dict()
        assert "judge_id" in d
        assert "model_id" in d
        assert "verdict" in d
        assert "timestamp" in d
        assert "evidence" in d
        assert "impl_version" in d
        assert "rationale" in d

    def test_valid_empty_evidence_fails_closed(self):
        """Verdict with empty evidence must fail is_sufficient()."""
        v = JudgeVerdict(
            judge_id="J1",
            model_id="test",
            verdict="PASS",
            findings=["test"],
            corrections=[],
            tool_calls=["cmd1", "cmd2"],
            evidence=EvidencePackage([]),
        )
        assert v.evidence.is_sufficient() is False

    def test_validate_verdict_dict_rejects_missing_evidence(self):
        """validate_verdict_dict must flag missing evidence field."""
        errors = JudgeVerdict.validate_verdict_dict({
            "judge_id": "J1",
            "verdict": "PASS",
            "findings": ["x"],
            "tool_calls": ["cmd"],
        })
        assert any("Missing evidence" in e for e in errors)

    def test_validate_verdict_dict_rejects_empty_evidence_items(self):
        errors = JudgeVerdict.validate_verdict_dict({
            "judge_id": "J1",
            "verdict": "PASS",
            "findings": ["x"],
            "tool_calls": ["cmd"],
            "evidence": {"evidence_items": [], "source_refs": []},
        })
        assert any("Insufficient evidence" in e for e in errors)

    def test_validate_verdict_dict_rejects_invalid_verdict(self):
        errors = JudgeVerdict.validate_verdict_dict({
            "judge_id": "J1",
            "verdict": "MAYBE",
            "findings": ["x"],
            "tool_calls": ["cmd"],
            "evidence": {"evidence_items": ["ok"], "source_refs": []},
        })
        assert any("Invalid verdict" in e for e in errors)

    def test_validate_verdict_dict_accepts_valid(self):
        errors = JudgeVerdict.validate_verdict_dict({
            "judge_id": "J1",
            "verdict": "PASS",
            "findings": ["x"],
            "corrections": [],
            "tool_calls": ["cmd"],
            "evidence": {"evidence_items": ["verified"], "source_refs": []},
        })
        assert errors == []


class TestGateReceipt:
    def test_create_receipt(self):
        v = _make_verdict("J1-TRUTH", "claude-3-5-sonnet")
        r = GateReceipt(
            action_id="test-123",
            action_type="email-send",
            payload_hash="abc123",
            verdicts=[v],
            previous_hash="GENESIS"
        )
        assert r.action_id == "test-123"
        assert r.previous_hash == "GENESIS"
        assert len(r.hash) == 64  # sha256 hex

    def test_hash_verification(self):
        v = _make_verdict("J1-TRUTH", "test")
        r = GateReceipt(
            action_id="test",
            action_type="test",
            payload_hash="test",
            verdicts=[v],
            previous_hash="GENESIS"
        )
        assert r.verify() == True

    def test_tamper_detection(self):
        v = _make_verdict("J1-TRUTH", "test")
        r = GateReceipt(
            action_id="test",
            action_type="test",
            payload_hash="test",
            verdicts=[v],
            previous_hash="GENESIS"
        )
        r.hash = "tampered"
        assert r.verify() == False

    def test_receipt_has_contract_version(self):
        v = _make_verdict("J1", "test")
        r = GateReceipt(
            action_id="x", action_type="t", payload_hash="h",
            verdicts=[v]
        )
        d = r.to_dict()
        assert "contract_version" in d
        assert "roster_snapshot" in d

    def test_receipt_to_dict_includes_contract_fields(self):
        """to_dict must include contract_version and roster_snapshot."""
        v = _make_verdict("J1", "test")
        r = GateReceipt(
            action_id="x",
            action_type="t",
            payload_hash="h",
            verdicts=[v],
            contract_version="1.0.0",
            roster_snapshot={"roster_version": "1.0.0", "judges": ["J1"]},
        )
        d = r.to_dict()
        assert d["contract_version"] == "1.0.0"
        assert d["roster_snapshot"]["roster_version"] == "1.0.0"


class TestJudgeGate:
    def test_create_gate(self):
        g = JudgeGate()
        assert len(g.ROSTER) == 9
        assert g.round_cap == 4

    def test_get_rotated_judge_id(self):
        g = JudgeGate()
        rotated = g.get_rotated_judge_id("J1-TRUTH", "2026-09-17")
        assert "J1-TRUTH" in rotated
        assert len(rotated) > len("J1-TRUTH")

    def test_rotation_changes_daily(self):
        g = JudgeGate()
        id1 = g.get_rotated_judge_id("J1-TRUTH", "2026-09-17")
        id2 = g.get_rotated_judge_id("J1-TRUTH", "2026-09-18")
        assert id1 != id2

    def test_verify_action_pass(self):
        g = JudgeGate()
        verdicts = []
        for i in range(9):
            judge_id = f"J{i+1}"
            v = _make_verdict(
                judge_id=judge_id,
                model_id=g._get_assigned_model(judge_id),
            )
            verdicts.append(v)

        passed, receipt = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed == True
        assert receipt.hash is not None

    def test_verify_action_fail_on_dissent(self):
        g = JudgeGate()
        verdicts = []
        for i in range(9):
            judge_id = f"J{i+1}"
            verdict = "PASS" if i < 8 else "DISSENT"
            v = _make_verdict(
                judge_id=judge_id,
                model_id=g._get_assigned_model(judge_id),
                verdict=verdict,
            )
            verdicts.append(v)

        passed, receipt = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed == False

    def test_verify_action_fail_on_rubber_stamp(self):
        g = JudgeGate()
        verdicts = []
        for i in range(9):
            judge_id = f"J{i+1}"
            v = _make_verdict(
                judge_id=judge_id,
                model_id=g._get_assigned_model(judge_id),
                tool_calls=["cmd1"],
            )
            verdicts.append(v)

        passed, receipt = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed == False

    def test_verify_action_fails_on_empty_evidence(self):
        """Missing evidence must fail closed."""
        g = JudgeGate()
        verdicts = []
        for i in range(9):
            judge_id = f"J{i+1}"
            v = JudgeVerdict(
                judge_id=judge_id,
                model_id=g._get_assigned_model(judge_id),
                verdict="PASS",
                findings=["verified"],
                corrections=[],
                tool_calls=["cmd1", "cmd2"],
                evidence=EvidencePackage([]),
            )
            verdicts.append(v)

        passed, _ = g.verify_action("test", {"key": "value"}, verdicts)
        assert passed == False

    def test_receipt_contains_contract_version_and_roster(self):
        """Receipt from verify_action must include contract and roster info."""
        g = JudgeGate()
        verdicts = [_make_verdict(f"J{i+1}", g._get_assigned_model(f"J{i+1}"))
                     for i in range(9)]
        passed, receipt = g.verify_action("test", {"k": "v"}, verdicts)
        d = receipt.to_dict()
        assert "contract_version" in d
        assert d["contract_version"] == "1.0.0"
        assert "roster_snapshot" in d
        assert "judges" in d["roster_snapshot"]
        assert len(d["roster_snapshot"]["judges"]) == 9

    def test_diagnostic_roster_no_secrets(self):
        """diagnostic_roster must not leak question templates."""
        diag = JudgeGate.diagnostic_roster()
        assert len(diag) == 9
        for entry in diag:
            assert "judge_id" in entry
            assert "domain" in entry
            assert "question" not in entry
            assert "criteria" not in entry

    def test_chain_integrity(self, tmp_path):
        chain_file = tmp_path / "receipt_chain.jsonl"
        g = JudgeGate(receipt_chain_path=str(chain_file))
        assert g.verify_chain_integrity() == True

        verdicts = [_make_verdict(f"J{i+1}", g._get_assigned_model(f"J{i+1}"))
                     for i in range(9)]

        g.verify_action("test1", {"a": 1}, verdicts)
        g.verify_action("test2", {"b": 2}, verdicts)
        assert g.verify_chain_integrity() == True
        assert len(g.receipt_chain) == 2


class TestRosterValidation:
    """Tests for issue #10: roster/registry validation."""

    def test_roster_integrity_passes_for_valid(self):
        errors = JudgeGate._check_roster_integrity(JudgeGate.ROSTER)
        assert errors == []

    def test_roster_integrity_detects_missing_judge(self):
        bad = dict(JudgeGate.ROSTER)
        del bad["J5"]
        errors = JudgeGate._check_roster_integrity(bad)
        assert any("Missing" in e for e in errors)

    def test_roster_integrity_detects_extra_judge(self):
        bad = dict(JudgeGate.ROSTER)
        bad["J10"] = {"domain": "EXTRA", "question": "?", "criteria": {"pass": "a", "dissent": "b"}}
        errors = JudgeGate._check_roster_integrity(bad)
        assert any("Unexpected" in e for e in errors)

    def test_roster_integrity_detects_wrong_count(self):
        bad = {"J1": JudgeGate.ROSTER["J1"]}
        errors = JudgeGate._check_roster_integrity(bad)
        assert any("exactly 9" in e for e in errors)

    def test_init_fails_on_bad_roster(self):
        """Constructor must raise RuntimeError on a bad roster."""
        with pytest.raises(RuntimeError, match="Roster validation FAILED"):
            class BadGate(JudgeGate):
                ROSTER = {"J1": {"domain": "X", "question": "?", "criteria": {"pass": "a", "dissent": "b"}}}
            BadGate()

    def test_init_with_validate_roster_false_skips_check(self):
        """Passing validate_roster=False must skip the check."""
        class BadGate(JudgeGate):
            ROSTER = {"J1": {"domain": "X", "question": "?", "criteria": {"pass": "a", "dissent": "b"}}}
        g = BadGate(validate_roster=False)
        assert g is not None


class TestChainPersistence:
    """Tests for disk persistence of the receipt chain."""

    def _make_9_verdicts(self, gate):
        return [
            _make_verdict(f"J{i+1}", gate._get_assigned_model(f"J{i+1}"))
            for i in range(9)
        ]

    def test_chain_persists_and_reloads(self, tmp_path):
        chain_file = tmp_path / "receipt_chain.jsonl"
        g = JudgeGate(receipt_chain_path=str(chain_file))
        assert g.verify_chain_integrity() is True
        assert len(g.receipt_chain) == 0

        verdicts = self._make_9_verdicts(g)

        g.verify_action("test1", {"a": 1}, verdicts)
        g.verify_action("test2", {"b": 2}, verdicts)
        assert g.verify_chain_integrity() is True
        assert len(g.receipt_chain) == 2

        # Fresh gate loads same file — chain should replay
        g2 = JudgeGate(receipt_chain_path=str(chain_file))
        assert len(g2.receipt_chain) == 2, "Should load persisted chain"
        assert g2.verify_chain_integrity() is True, "Replayed chain must verify"

        for idx, h in enumerate(g2.receipt_chain):
            receipt = g2._receipt_store[h]
            expected_prev = g2.receipt_chain[idx - 1] if idx > 0 else "GENESIS"
            assert receipt.previous_hash == expected_prev

    def test_fail_closed_on_missing_file(self, tmp_path):
        chain_file = tmp_path / "does_not_exist.jsonl"
        g = JudgeGate(receipt_chain_path=str(chain_file))
        assert g.verify_chain_integrity() is True
        assert len(g.receipt_chain) == 0

    def test_fail_closed_on_malformed_json(self, tmp_path):
        chain_file = tmp_path / "bad.jsonl"
        chain_file.write_text("not valid json\n")
        g = JudgeGate(receipt_chain_path=str(chain_file))
        assert len(g.receipt_chain) == 0, "Should reset on malformed data"
        assert g.verify_chain_integrity() is True

    def test_flip_one_byte_fails_integrity(self, tmp_path):
        chain_file = tmp_path / "receipt_chain.jsonl"
        g = JudgeGate(receipt_chain_path=str(chain_file))

        verdicts = self._make_9_verdicts(g)

        g.verify_action("flip_test", {"x": 1}, verdicts)
        assert len(g.receipt_chain) == 1
        assert g.verify_chain_integrity() is True

        # Flip one byte in the file
        data = bytearray(chain_file.read_bytes())
        for i in range(len(data)):
            if data[i] != ord("\n"):
                data[i] ^= 0x01
                break
        chain_file.write_bytes(bytes(data))

        g2 = JudgeGate(receipt_chain_path=str(chain_file))
        assert len(g2.receipt_chain) == 0

    def test_fail_closed_on_broken_chain_link(self, tmp_path):
        chain_file = tmp_path / "receipt_chain.jsonl"
        g = JudgeGate(receipt_chain_path=str(chain_file))

        verdicts = self._make_9_verdicts(g)

        g.verify_action("action1", {"a": 1}, verdicts)
        g.verify_action("action2", {"b": 2}, verdicts)
        assert len(g.receipt_chain) == 2
        assert g.verify_chain_integrity() is True

        # Read lines, modify previous_hash in second receipt
        lines = chain_file.read_text().strip().split("\n")
        entries = [json.loads(line) for line in lines]
        entries[1]["previous_hash"] = "BADHASH"
        chain_file.write_text(
            "\n".join(json.dumps(e, sort_keys=True) for e in entries) + "\n"
        )

        g2 = JudgeGate(receipt_chain_path=str(chain_file))
        assert len(g2.receipt_chain) == 0, "Broken chain link must reset to empty"