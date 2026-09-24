"""Tests for J10-RESOURCE-QUOTA and J11-POLICY-COMPLIANCE (issues #16, #17).

Requirement summary:
  J10 — resource/quota judge: token budget, time budget, storage, API cost, rate-limit.
        Any resource exceeding its declared limit = DISSENT.
  J11 — policy-compliance judge: policy precedence, conflict detection, policy version.
        Fails closed on conflict, records policy version in receipt.
Both: read-only, deterministic, unanimous-PASS, no secrets leaked, no side effects.
"""

import pytest
from amartie.judge_panel_v2 import (
    JudgeResourceQuota, JudgePolicyCompliance,
    EvidencePackage, PanelV2,
)


# ═══════════════════════════════════════════════════════════════════════
# J10 — RESOURCE-QUOTA (#16)
# ═══════════════════════════════════════════════════════════════════════


class TestJudgeResourceQuota:
    """Issue #16: resource/cost/quota/rate-limit enforcement."""

    IN_LIMITS = {
        "resource_limits": {
            "scope": "action",
            "user": "agent-alpha",
            "studio": "default",
            "plugin": "data-pipeline",
            "token_budget": {"current": 1500, "limit": 100_000},
            "time_budget": {"current": 12, "limit": 300},
            "storage_quota": {"current": 45, "limit": 500},
            "api_cost": {"current": 0.03, "limit": 10.00},
            "rate_limit": {"current": 5, "limit": 100},
        }
    }

    OVER_TOKEN = {
        "resource_limits": {
            "scope": "action",
            "token_budget": {"current": 99_999, "limit": 50_000},
            "time_budget": {"current": 10, "limit": 300},
            "storage_quota": {"current": 10, "limit": 500},
            "api_cost": {"current": 0.01, "limit": 10.00},
            "rate_limit": {"current": 1, "limit": 100},
        }
    }

    OVER_RATE = {
        "resource_limits": {
            "scope": "action",
            "token_budget": {"current": 100, "limit": 100_000},
            "time_budget": {"current": 5, "limit": 300},
            "storage_quota": {"current": 10, "limit": 500},
            "api_cost": {"current": 0.01, "limit": 10.00},
            "rate_limit": {"current": 250, "limit": 100},
        }
    }

    def test_within_limits_passes(self):
        """All resources within declared limits => PASS."""
        judge = JudgeResourceQuota()
        package = EvidencePackage("test", self.IN_LIMITS)
        result = judge.review(package)
        assert result["verdict"] == "PASS", f"Expected PASS, got {result['findings']}"
        assert result["score"] >= 80

    def test_over_token_budget_denies(self):
        """Token budget exceeded => DISSENT with finding."""
        judge = JudgeResourceQuota()
        package = EvidencePackage("test", self.OVER_TOKEN)
        result = judge.review(package)
        assert result["verdict"] == "DISSENT"
        assert any("OVER BUDGET" in f for f in result["findings"])
        assert any("Token" in f for f in result["findings"])

    def test_over_rate_limit_denies(self):
        """Rate limit exceeded => DISSENT."""
        judge = JudgeResourceQuota()
        package = EvidencePackage("test", self.OVER_RATE)
        result = judge.review(package)
        assert result["verdict"] == "DISSENT"
        assert any("OVER BUDGET" in f for f in result["findings"])
        assert any("Rate" in f for f in result["findings"])

    def test_missing_resource_limits(self):
        """Missing resource_limits section => findings but still lenient PASS threshold."""
        judge = JudgeResourceQuota()
        package = EvidencePackage("test", {"other": "data"})
        result = judge.review(package)
        # Score drops to 60 (100 - 40) => DISSENT
        assert result["verdict"] == "DISSENT"
        assert any("MISSING" in f and "resource_limits" in f for f in result["findings"])

    def test_missing_limit_field(self):
        """A resource with current but no limit => finding but not auto-fail."""
        judge = JudgeResourceQuota()
        pkg = EvidencePackage("test", {
            "resource_limits": {
                "token_budget": {"current": 50},  # no 'limit' key
            }
        })
        result = judge.review(pkg)
        assert any("MISSING LIMIT" in f for f in result["findings"])

    def test_zero_limit_rejected(self):
        """Zero limit => finding (must be positive)."""
        judge = JudgeResourceQuota()
        pkg = EvidencePackage("test", {
            "resource_limits": {
                "token_budget": {"current": 0, "limit": 0},
            }
        })
        result = judge.review(pkg)
        assert any("ZERO LIMIT" in f for f in result["findings"])

    def test_read_only_no_side_effects(self):
        """review() must not mutate the evidence content."""
        judge = JudgeResourceQuota()
        import copy
        original = copy.deepcopy(self.IN_LIMITS)
        package = EvidencePackage("test", self.IN_LIMITS)
        judge.review(package)
        assert package.content == original

    def test_deterministic(self):
        """Same input => same verdict every time."""
        judge = JudgeResourceQuota()
        pkg1 = EvidencePackage("t", self.IN_LIMITS)
        pkg2 = EvidencePackage("t", self.IN_LIMITS)
        r1 = judge.review(pkg1)
        r2 = judge.review(pkg2)
        assert r1["verdict"] == r2["verdict"]
        assert r1["score"] == r2["score"]
        assert r1["findings"] == r2["findings"]


# ═══════════════════════════════════════════════════════════════════════
# J11 — POLICY-COMPLIANCE (#17)
# ═══════════════════════════════════════════════════════════════════════


class TestJudgePolicyCompliance:
    """Issue #17: policy precedence, conflict detection, policy version."""

    NO_CONFLICT = {
        "policy_inputs": {
            "precedence": ["org-policy", "studio-policy", "user-policy"],
            "policies": {
                "org-policy": {
                    "version": "2.1.0",
                    "rules": [
                        {"key": "allow_external_sharing", "action": "deny"},
                        {"key": "max_storage_gb", "value": "100"},
                    ],
                },
                "studio-policy": {
                    "version": "1.4.0",
                    "rules": [
                        {"key": "logging_level", "value": "verbose"},
                    ],
                },
                "user-policy": {
                    "version": "3.0.0",
                    "rules": [
                        {"key": "rate_limit_per_minute", "value": "60"},
                    ],
                },
            },
        }
    }

    CONFLICT = {
        "policy_inputs": {
            "precedence": ["org-policy", "studio-policy"],
            "policies": {
                "org-policy": {
                    "version": "2.1.0",
                    "rules": [
                        {"key": "allow_external_sharing", "action": "deny"},
                    ],
                },
                "studio-policy": {
                    "version": "1.4.0",
                    "rules": [
                        {"key": "allow_external_sharing", "action": "allow"},
                    ],
                },
            },
        }
    }

    PRECEDENCE_PREVENTS_CONFLICT = {
        "policy_inputs": {
            "precedence": ["org-policy", "studio-policy", "team-policy"],
            "policies": {
                "org-policy": {
                    "version": "2.1.0",
                    "rules": [
                        {"key": "allow_external_sharing", "action": "deny"},
                    ],
                },
                "studio-policy": {
                    "version": "1.4.0",
                    "rules": [
                        {"key": "allow_external_sharing", "action": "deny"},
                    ],
                },
                "team-policy": {
                    "version": "1.0.0",
                    "rules": [
                        {"key": "instance_type", "value": "standard"},
                    ],
                },
            },
        }
    }

    def test_no_conflict_passes(self):
        """No conflicting rules => PASS with policy versions."""
        judge = JudgePolicyCompliance()
        package = EvidencePackage("test", self.NO_CONFLICT)
        result = judge.review(package)
        assert result["verdict"] == "PASS", f"Expected PASS, got {result['findings']}"
        assert result["score"] >= 80

    def test_policy_versions_in_result(self):
        """Policy versions are recorded in result['policy_versions']."""
        judge = JudgePolicyCompliance()
        package = EvidencePackage("test", self.NO_CONFLICT)
        result = judge.review(package)
        assert "policy_versions" in result
        assert result["policy_versions"]["org-policy"] == "2.1.0"
        assert result["policy_versions"]["studio-policy"] == "1.4.0"
        assert result["policy_versions"]["user-policy"] == "3.0.0"

    def test_policy_conflict_denies(self):
        """Conflicting rule actions => DISSENT."""
        judge = JudgePolicyCompliance()
        package = EvidencePackage("test", self.CONFLICT)
        result = judge.review(package)
        assert result["verdict"] == "DISSENT"
        assert any("POLICY CONFLICT" in f for f in result["findings"])

    def test_same_values_not_conflict(self):
        """Same action on same key across policies should not trigger conflict."""
        judge = JudgePolicyCompliance()
        package = EvidencePackage("test", self.PRECEDENCE_PREVENTS_CONFLICT)
        result = judge.review(package)
        assert result["verdict"] == "PASS"
        assert not any("POLICY CONFLICT" in f for f in result["findings"])

    def test_missing_policy_inputs(self):
        """Missing policy_inputs => score drop but not auto-fail."""
        judge = JudgePolicyCompliance()
        package = EvidencePackage("test", {"other": "data"})
        result = judge.review(package)
        assert result["verdict"] == "DISSENT"
        assert any("MISSING" in f and "policy_inputs" in f for f in result["findings"])

    def test_version_recorded_even_on_conflict(self):
        """Policy versions are still recorded when there's a conflict."""
        judge = JudgePolicyCompliance()
        package = EvidencePackage("test", self.CONFLICT)
        result = judge.review(package)
        assert result["verdict"] == "DISSENT"
        assert result["policy_versions"]["org-policy"] == "2.1.0"
        assert result["policy_versions"]["studio-policy"] == "1.4.0"

    def test_empty_precedence(self):
        """Empty precedence list => finding but versions still collected."""
        judge = JudgePolicyCompliance()
        pkg = EvidencePackage("test", {
            "policy_inputs": {
                "precedence": [],
                "policies": {
                    "default": {"version": "1.0", "rules": []},
                },
            }
        })
        result = judge.review(pkg)
        assert any("MISSING: policy precedence order" in f for f in result["findings"])
        assert result["policy_versions"]["default"] == "1.0"

    def test_duplicate_precedence(self):
        """Duplicate IDs in precedence => finding."""
        judge = JudgePolicyCompliance()
        pkg = EvidencePackage("test", {
            "policy_inputs": {
                "precedence": ["a", "a"],
                "policies": {
                    "a": {"version": "1.0", "rules": []},
                },
            }
        })
        result = judge.review(pkg)
        assert any("PRECEDENCE ERROR" in f for f in result["findings"])

    def test_missing_policy_in_precedence(self):
        """Policy ID in precedence but not in policies => finding."""
        judge = JudgePolicyCompliance()
        pkg = EvidencePackage("test", {
            "policy_inputs": {
                "precedence": ["missing-policy"],
                "policies": {"existing": {"version": "1.0", "rules": []}},
            }
        })
        result = judge.review(pkg)
        assert any("POLICY MISSING" in f for f in result["findings"])

    def test_read_only_no_side_effects(self):
        """review() must not mutate the evidence content."""
        judge = JudgePolicyCompliance()
        import copy
        original = copy.deepcopy(self.NO_CONFLICT)
        package = EvidencePackage("test", self.NO_CONFLICT)
        judge.review(package)
        assert package.content == original

    def test_deterministic(self):
        """Same input => same verdict every time."""
        judge = JudgePolicyCompliance()
        pkg1 = EvidencePackage("t", self.NO_CONFLICT)
        pkg2 = EvidencePackage("t", self.NO_CONFLICT)
        r1 = judge.review(pkg1)
        r2 = judge.review(pkg2)
        assert r1["verdict"] == r2["verdict"]
        assert r1["score"] == r2["score"]
        assert r1["findings"] == r2["findings"]


# ═══════════════════════════════════════════════════════════════════════
# Integration: PanelV2 includes both new judges
# ═══════════════════════════════════════════════════════════════════════


class TestPanelV2IncludesNewJudges:
    """PanelV2 must include J10 and J11 in its voting roster."""

    def test_panel_has_13_judges(self):
        panel = PanelV2()
        assert len(panel.voting_judges) == 13

    def test_panel_includes_j10(self):
        panel = PanelV2()
        names = [j.name for j in panel.voting_judges]
        assert "J10-RESOURCE-QUOTA" in names

    def test_panel_includes_j11(self):
        panel = PanelV2()
        names = [j.name for j in panel.voting_judges]
        assert "J11-POLICY-COMPLIANCE" in names

    def test_full_panel_pass_with_limits(self):
        """Full panel with resource_limits and policy_inputs => unanimous pass."""
        panel = PanelV2()
        evidence = {
            "total_requests": 10,
            "identity_conflicts": [{"requested": "sonnet", "detected": "haiku",
                                     "score": 3, "file": "/tmp/test.txt"}],
            "quality_drops": [{"expected": 0.8, "actual": 0.5}],
            "timeline": [{"ts": "2026-09-01T00:00:00Z", "event": "start"},
                         {"ts": "2026-09-01T01:00:00Z", "event": "end"}],
            "error_summary": {"400": 2},
            "models_requested": ["claude"],
            "swap_mechanism": "credit exhaustion",
            "preservation": {"locations": ["local", "cloud"], "off_box": True},
            "chain_of_custody": "signed log",
            "methodology": "forensic analysis",
            "tooling": ["/usr/bin/grep", "/usr/bin/diff"],
            "receipt_hash": "abc123",
            "dataflow": "source -> analysis -> verdict",
            "tooling_interfaces": "cross-checked",
            "performance_budget": "<500ms",
            "claims": [],
            # J2: caller identity & plugin manifest
            "caller": "agent-alpha",
            "plugin_manifest": {"name": "data-pipeline", "version": "1.0"},
            # J10: resource limits within budget
            "resource_limits": {
                "token_budget": {"current": 100, "limit": 100_000},
                "time_budget": {"current": 5, "limit": 300},
                "storage_quota": {"current": 10, "limit": 500},
                "api_cost": {"current": 0.01, "limit": 10.00},
                "rate_limit": {"current": 2, "limit": 100},
            },
            # J11: policy with no conflicts
            "policy_inputs": {
                "precedence": ["org"],
                "policies": {
                    "org": {
                        "version": "1.0.0",
                        "rules": [{"key": "allow_sharing", "action": "deny"}],
                    },
                },
            },
            # J12: destination for safety check
            "destination": "/tmp/out.txt",
            "is_dry_run": True,
            "explicit_no_network": True,
            # J13: declared intent matching action
            "declared_intent": "run analysis pipeline",
            "action_text": "run analysis pipeline",
            "action_parameters": {"pipeline": "analysis", "mode": "dry"},
        }
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("test data")
            tmp_path = f.name
        try:
            evidence["identity_conflicts"][0]["file"] = tmp_path
            evidence["tooling"] = [tmp_path, "/usr/bin/diff"]
            package = EvidencePackage("full_test", evidence)
            result = panel.review(package)
            dissenting = result["dissenting_judges"]
            assert result["unanimous"] is True, (
                f"Panel should pass unanimously, got dissents: {dissenting}"
                f"\nVerdicts: {[(v['judge'], v['verdict'], v['findings']) for v in result['verdicts'] if v['verdict'] == 'DISSENT']}"
            )
            assert result["verdict_label"] == "UNANIMOUS_PASS_13/13"
        finally:
            os.unlink(tmp_path)