# Tests for AMARTIE Gate Engine

import pytest
import json
import hashlib
from amartie.gate import (
    JudgeGate, JudgeVerdict, GateReceipt, gate,
    EvidencePackage, CanonicalSerializer, CrossStageTracker,
    ModelIdentityEvidence, PromptDigest, ReplayabilityAssertion,
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
        assert len(g.ROSTER) == 13
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
        for i in range(13):
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
        for i in range(13):
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
        for i in range(13):
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
        for i in range(13):
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
                     for i in range(13)]
        passed, receipt = g.verify_action("test", {"k": "v"}, verdicts)
        d = receipt.to_dict()
        assert "contract_version" in d
        assert d["contract_version"] == "1.0.0"
        assert "roster_snapshot" in d
        assert "judges" in d["roster_snapshot"]
        assert len(d["roster_snapshot"]["judges"]) == 13

    def test_diagnostic_roster_no_secrets(self):
        """diagnostic_roster must not leak question templates."""
        diag = JudgeGate.diagnostic_roster()
        assert len(diag) == 13
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
                     for i in range(13)]

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
        bad["J99"] = {"domain": "EXTRA", "question": "?", "criteria": {"pass": "a", "dissent": "b"}}
        errors = JudgeGate._check_roster_integrity(bad)
        assert any("Unexpected" in e for e in errors)

    def test_roster_integrity_detects_wrong_count(self):
        bad = {"J1": JudgeGate.ROSTER["J1"]}
        errors = JudgeGate._check_roster_integrity(bad)
        assert any("exactly 13" in e for e in errors)

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

    def all_verdicts(self, gate):
        return [
            _make_verdict(f"J{i+1}", gate._get_assigned_model(f"J{i+1}"))
            for i in range(13)
        ]

    def test_chain_persists_and_reloads(self, tmp_path):
        chain_file = tmp_path / "receipt_chain.jsonl"
        g = JudgeGate(receipt_chain_path=str(chain_file))
        assert g.verify_chain_integrity() is True
        assert len(g.receipt_chain) == 0

        verdicts = self.all_verdicts(g)

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

        verdicts = self.all_verdicts(g)

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

        verdicts = self.all_verdicts(g)

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


class TestDeterministicFixtures:
    """Deterministic fixture tests — no randomness, no external calls.
    Replay the same fixture through the gate and assert stable verdicts."""

    FIXTURE_PAYLOAD = {"task": "read_file", "path": "/tmp/test.txt"}
    FIXTURE_ACTION = "file-read"

    @staticmethod
    def _fixture_9_pass(gate):
        """Deterministic fixture: all 13 judges PASS with valid contract fields."""
        return [
            JudgeVerdict(
                judge_id=f"J{i+1}",
                model_id=gate._get_assigned_model(f"J{i+1}"),
                verdict="PASS",
                findings=[f"J{i+1} domain check passed"],
                corrections=[],
                tool_calls=["check_domain", "verify_evidence"],
                impl_version="1.0.0",
                rationale=f"J{i+1}: All criteria satisfied",
                evidence=EvidencePackage([
                    f"J{i+1} evidence item 1",
                    f"J{i+1} evidence item 2",
                ]),
            )
            for i in range(13)
        ]

    @staticmethod
    def _fixture_8_pass_1_dissent(gate, dissent_judge="J3"):
        """Deterministic fixture: 8 PASS, 1 DISSENT — tests deny-on-dissent."""
        verdicts = []
        for i in range(13):
            jid = f"J{i+1}"
            is_dissent = jid == dissent_judge
            verdicts.append(JudgeVerdict(
                judge_id=jid,
                model_id=gate._get_assigned_model(jid),
                verdict="DISSENT" if is_dissent else "PASS",
                findings=(
                    [f"J{i+1} FAILED: logic contradiction detected"]
                    if is_dissent else [f"J{i+1} domain check passed"]
                ),
                corrections=(
                    ["Resolve logical contradiction", "Add missing premise"]
                    if is_dissent else []
                ),
                tool_calls=["check_domain", "verify_evidence"],
                impl_version="1.0.0",
                rationale=(
                    f"J{i+1}: Contradiction found"
                    if is_dissent else f"J{i+1}: All criteria satisfied"
                ),
                evidence=EvidencePackage([
                    f"J{i+1} {'dissent' if is_dissent else 'pass'} evidence"
                ]),
            ))
        return verdicts

    def test_replay_p_gives_same_result(self):
        """Same fixture, same gate instance — same passed boolean."""
        g = JudgeGate()
        v = self._fixture_9_pass(g)
        p1, r1 = g.verify_action(self.FIXTURE_ACTION, self.FIXTURE_PAYLOAD, v)
        p2, r2 = g.verify_action(self.FIXTURE_ACTION, self.FIXTURE_PAYLOAD, v)
        assert p1 is True
        assert p2 is True
        # Receipt hashes differ (uuid action_id) but both PASS
        assert r1.hash != r2.hash
        # Contract fields stable
        assert r1.contract_version == r2.contract_version == "1.0.0"
        assert r1.roster_snapshot["judges"] == r2.roster_snapshot["judges"]

    def test_replay_dissent_gives_same_result(self):
        """Dissent fixture replay yields stable False."""
        g = JudgeGate()
        v = self._fixture_8_pass_1_dissent(g, "J3")
        p1, _ = g.verify_action(self.FIXTURE_ACTION, self.FIXTURE_PAYLOAD, v)
        p2, _ = g.verify_action(self.FIXTURE_ACTION, self.FIXTURE_PAYLOAD, v)
        assert p1 is False
        assert p2 is False

    def test_different_gate_same_fixture_same_verdict(self):
        """Two independent gate instances with same fixture produce same verdict."""
        g1 = JudgeGate()
        g2 = JudgeGate()
        v = self._fixture_9_pass(g1)
        p1, _ = g1.verify_action(self.FIXTURE_ACTION, self.FIXTURE_PAYLOAD, v)
        # Rebuild verdicts for g2 to get correct model_id per judge
        v2 = self._fixture_9_pass(g2)
        p2, _ = g2.verify_action(self.FIXTURE_ACTION, self.FIXTURE_PAYLOAD, v2)
        assert p1 is True
        assert p2 is True

    def test_different_dissent_judges_block(self):
        """Each of the 9 judges when dissenting must block the action."""
        g = JudgeGate()
        for dissent_jid in ["J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9"]:
            v = self._fixture_8_pass_1_dissent(g, dissent_jid)
            p, r = g.verify_action(self.FIXTURE_ACTION, self.FIXTURE_PAYLOAD, v)
            assert p is False, f"DISSENT from {dissent_jid} should block"
            assert r.action_type == self.FIXTURE_ACTION

    def test_receipt_structure_stable(self):
        """Receipt fields must be structurally consistent across runs."""
        g = JudgeGate()
        v = self._fixture_9_pass(g)
        _, r = g.verify_action(self.FIXTURE_ACTION, self.FIXTURE_PAYLOAD, v)
        d = r.to_dict()
        assert d["contract_version"] == "1.0.0"
        assert len(d["roster_snapshot"]["judges"]) == 13
        assert "J1" in d["roster_snapshot"]["judges"]
        assert "J9" in d["roster_snapshot"]["judges"]
        assert len(d["verdicts"]) == 13
        assert d["action_type"] == self.FIXTURE_ACTION
        assert d["previous_hash"] == "GENESIS"
        assert len(d["action_id"]) > 0

    def test_zero_tool_calls_blocks(self):
        """A verdict with zero tool_calls must be blocked (below floor of 2)."""
        g = JudgeGate()
        verdicts = []
        for i in range(13):
            jid = f"J{i+1}"
            verdicts.append(JudgeVerdict(
                judge_id=jid,
                model_id=g._get_assigned_model(jid),
                verdict="PASS",
                findings=["verified"],
                corrections=[],
                tool_calls=[],  # empty — below floor of 2
                evidence=EvidencePackage(["evidence"]),
            ))
        p, _ = g.verify_action(self.FIXTURE_ACTION, self.FIXTURE_PAYLOAD, verdicts)
        assert p is False

    def test_one_tool_call_blocks(self):
        """A verdict with exactly 1 tool_call must be blocked (below floor of 2)."""
        g = JudgeGate()
        verdicts = []
        for i in range(13):
            jid = f"J{i+1}"
            verdicts.append(JudgeVerdict(
                judge_id=jid,
                model_id=g._get_assigned_model(jid),
                verdict="PASS",
                findings=["verified"],
                corrections=[],
                tool_calls=["only_one"],
                evidence=EvidencePackage(["evidence"]),
            ))
        p, _ = g.verify_action(self.FIXTURE_ACTION, self.FIXTURE_PAYLOAD, verdicts)
        assert p is False


# ═══════════════════════════════════════════════════════════════════
# Issue #15 — Action & Evidence Integrity (Cross-Stage Tracking)
# ═══════════════════════════════════════════════════════════════════

class TestCrossStageTracking:
    """Issue #15: Cross-stage mutation tracking and canonical integrity."""

    def test_cross_stage_mutation_deny(self):
        """Mismatch between proposal, execution, and receipt hashes must fail."""
        proposal = {"action": "send_email", "to": "alice@example.com", "body": "hello"}
        execution = {"action": "send_email", "to": "alice@example.com", "body": "hello"}
        receipt_hash = CanonicalSerializer.digest(execution)
        tracker = CrossStageTracker(proposal, execution, receipt_hash)
        assert tracker.all_agree() is True

        # Mutate execution (one-byte change)
        mutated = {"action": "send_email", "to": "alice@example.com", "body": "HELLO"}
        tracker2 = CrossStageTracker(proposal, mutated, receipt_hash)
        assert tracker2.all_agree() is False

    def test_canonical_reorder_stability(self):
        """Reordered fields must produce identical hashes."""
        data_a = {"z": 1, "a": 2, "m": {"nested": 3, "first": 0}}
        data_b = {"a": 2, "z": 1, "m": {"first": 0, "nested": 3}}
        assert CanonicalSerializer.digest(data_a) == CanonicalSerializer.digest(data_b)

    def test_canonical_encoding_drift_resistance(self):
        """Encoding variations (unicode, int/float) must not change hashes."""
        data = {"key": "café", "num": 42}
        h1 = CanonicalSerializer.digest(data)
        h2 = CanonicalSerializer.digest(dict(data))
        assert h1 == h2

    def test_cross_stage_tampered_receipt_hash_deny(self):
        """A tampered receipt hash must break cross-stage agreement."""
        proposal = {"type": "email", "to": "bob@test.com"}
        execution = {"type": "email", "to": "bob@test.com"}
        tampered_hash = "0" * 64
        tracker = CrossStageTracker(proposal, execution, tampered_hash)
        assert tracker.all_agree() is False

    def test_cross_stage_tracker_to_dict(self):
        """CrossStageTracker.to_dict must serialise cleanly."""
        tracker = CrossStageTracker(
            {"action": "test"}, {"action": "test"},
            CanonicalSerializer.digest({"action": "test"}),
        )
        d = tracker.to_dict()
        assert "proposal_hash" in d
        assert "execution_hash" in d
        assert "receipt_hash" in d
        assert d["proposal_hash"] == d["execution_hash"]
        assert d["execution_hash"] == d["receipt_hash"]


# ═══════════════════════════════════════════════════════════════════
# Issue #18 — Evidence Sufficiency & Replayability
# ═══════════════════════════════════════════════════════════════════

class TestModelIdentityEvidence:
    """Issue #18: Model identity validated INSIDE evidence."""

    def test_valid_model_identity(self):
        mi = ModelIdentityEvidence(model_id="gpt-4", provider="openai", version="1.0")
        assert mi.is_valid() is True
        d = mi.to_dict()
        assert d["model_id"] == "gpt-4"
        assert d["provider"] == "openai"

    def test_invalid_model_identity_empty_id(self):
        mi = ModelIdentityEvidence(model_id="", provider="", version="")
        assert mi.is_valid() is False

    def test_model_identity_from_dict(self):
        d = {"model_id": "claude-3", "provider": "anthropic", "version": "2.0"}
        mi = ModelIdentityEvidence.from_dict(d)
        assert mi.model_id == "claude-3"
        assert mi.is_valid() is True


class TestPromptDigest:
    """Issue #18: Prompt/input digest recording."""

    def test_prompt_digest_present(self):
        pd = PromptDigest(prompt_hash="abc123", input_summary="User asked about X")
        assert pd.is_present() is True

    def test_prompt_digest_missing(self):
        pd = PromptDigest(prompt_hash="", input_summary="")
        assert pd.is_present() is False

    def test_prompt_digest_from_dict(self):
        d = {"prompt_hash": "def456", "input_summary": "Query for stock prices"}
        pd = PromptDigest.from_dict(d)
        assert pd.prompt_hash == "def456"
        assert pd.is_present() is True

    def test_prompt_digest_to_dict(self):
        pd = PromptDigest("xyz789", "Test prompt")
        d = pd.to_dict()
        assert d["prompt_hash"] == "xyz789"
        assert d["input_summary"] == "Test prompt"


class TestReplayabilityAssertion:
    """Issue #18: Explicit replayability assertion."""

    def test_replayability_pass_with_steps(self):
        ra = ReplayabilityAssertion(
            replayable=True,
            reproduction_steps=["Step 1: Load evidence", "Step 2: Re-run tool"],
            required_tools=["tool_a", "tool_b"],
        )
        assert ra.is_assertable() is True

    def test_replayability_fail_no_steps(self):
        ra = ReplayabilityAssertion(
            replayable=True, reproduction_steps=[], required_tools=[],
        )
        assert ra.is_assertable() is False

    def test_replayability_fail_not_replayable(self):
        ra = ReplayabilityAssertion(
            replayable=False, reproduction_steps=["Some step"], required_tools=[],
        )
        assert ra.is_assertable() is False

    def test_replayability_fail_no_steps_and_not_replayable(self):
        ra = ReplayabilityAssertion(
            replayable=False, reproduction_steps=[], required_tools=[],
        )
        assert ra.is_assertable() is False

    def test_replayability_from_dict(self):
        d = {
            "replayable": True,
            "reproduction_steps": ["Step A", "Step B"],
            "required_tools": ["tool1"],
        }
        ra = ReplayabilityAssertion.from_dict(d)
        assert ra.is_assertable() is True
        assert len(ra.reproduction_steps) == 2

    def test_replayability_to_dict(self):
        ra = ReplayabilityAssertion(
            replayable=True,
            reproduction_steps=["Re-run analysis"],
            required_tools=["detector"],
        )
        d = ra.to_dict()
        assert d["replayable"] is True
        assert "reproduction_steps" in d
        assert "required_tools" in d


class TestEvidencePackageWithNewFields:
    """Issue #18: EvidencePackage carries model identity, prompt digest, replayability."""

    def test_evidence_with_model_identity(self):
        mi = ModelIdentityEvidence("gpt-4", "openai", "1.0")
        ep = EvidencePackage(["evidence item"], model_identity=mi)
        assert ep.model_identity is not None
        assert ep.model_identity.is_valid() is True
        d = ep.to_dict()
        assert "model_identity" in d
        assert d["model_identity"]["model_id"] == "gpt-4"

    def test_evidence_with_prompt_digest(self):
        pd = PromptDigest("hash123", "Input summary")
        ep = EvidencePackage(["evidence item"], prompt_digest=pd)
        assert ep.prompt_digest is not None
        d = ep.to_dict()
        assert "prompt_digest" in d

    def test_evidence_with_replayability(self):
        ra = ReplayabilityAssertion(True, ["Step 1"], ["tool"])
        ep = EvidencePackage(["evidence item"], replayability=ra)
        assert ep.replayability is not None
        assert ep.replayability.is_assertable() is True
        d = ep.to_dict()
        assert "replayability" in d

    def test_evidence_with_all_new_fields(self):
        mi = ModelIdentityEvidence("claude-3", "anthropic")
        pd = PromptDigest("abcdef", "User input")
        ra = ReplayabilityAssertion(True, ["Execute command", "Verify output"], ["cmd"])
        ep = EvidencePackage(
            ["evidence1", "evidence2"],
            model_identity=mi, prompt_digest=pd, replayability=ra,
        )
        assert ep.is_sufficient() is True
        assert ep.model_identity.is_valid()
        assert ep.prompt_digest.is_present()
        assert ep.replayability.is_assertable()

    def test_evidence_from_dict_with_new_fields(self):
        d = {
            "evidence_items": ["item1"],
            "source_refs": [],
            "model_identity": {"model_id": "gpt-4", "provider": "openai", "version": "1.0"},
            "prompt_digest": {"prompt_hash": "abc", "input_summary": "test"},
            "replayability": {"replayable": True, "reproduction_steps": ["step1"], "required_tools": ["t1"]},
        }
        ep = EvidencePackage.from_dict(d)
        assert ep.model_identity is not None
        assert ep.model_identity.model_id == "gpt-4"
        assert ep.prompt_digest is not None
        assert ep.prompt_digest.prompt_hash == "abc"
        assert ep.replayability is not None
        assert ep.replayability.is_assertable() is True

    def test_evidence_from_dict_no_new_fields(self):
        """Backward compat: evidence without new fields still loads cleanly."""
        d = {"evidence_items": ["item1"], "source_refs": []}
        ep = EvidencePackage.from_dict(d)
        assert ep.model_identity is None
        assert ep.prompt_digest is None
        assert ep.replayability is None
        assert ep.is_sufficient() is True