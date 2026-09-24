"""
AMARTIE J2-BOUNDARY Judge Tests — Issues #11 (Authorization/Capability-Scope) and #12 (Secret/Data-Leakage)
=========================================================================================================
"""
import pytest
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amartie.judge_panel_v2 import (
    EvidencePackage, JudgeBoundary,
    SECRET_PATTERNS, _scan_content_for_secrets,
)


def _review(content: dict) -> dict:
    """Helper: run JudgeBoundary review on the given content dict."""
    judge = JudgeBoundary()
    pkg = EvidencePackage("test", content)
    return judge.review(pkg)


# ═══════════════════════════════════════════════════════════════════
# Issue #11 — Authorization & Capability-Scope
# ═══════════════════════════════════════════════════════════════════

class TestIssue11_AuthorizationScope:
    """#11: Judge verifies caller identity, plugin manifest, declared-vs-undeclared capabilities."""

    def test_missing_caller_dissents(self):
        """Content without caller identity must produce DISSENT."""
        result = _review({
            "caller": None,
            "plugin_manifest": {"name": "p", "capabilities": ["read"]},
            "requested_action": {"type": "test", "capabilities_used": ["read"]},
        })
        assert result["verdict"] == "DISSENT"
        assert any("caller identity" in f.lower() for f in result["findings"])

    def test_missing_plugin_manifest_dissents(self):
        """Content without plugin manifest must produce DISSENT."""
        result = _review({
            "caller": "my-plugin",
            "plugin_manifest": None,
            "requested_action": {"type": "test", "capabilities_used": ["read"]},
        })
        assert result["verdict"] == "DISSENT"
        assert any("plugin manifest" in f.lower() for f in result["findings"])

    def test_malformed_manifest_dissents(self):
        """Non-dict plugin manifest must produce DISSENT."""
        result = _review({
            "caller": "my-plugin",
            "plugin_manifest": "not a dict",
            "requested_action": {"type": "test", "capabilities_used": ["read"]},
        })
        assert result["verdict"] == "DISSENT"
        assert any("not a valid dictionary" in f.lower() for f in result["findings"])

    def test_undeclared_capability_denied(self):
        """Using a capability not in the manifest must produce DISSENT."""
        result = _review({
            "caller": "my-plugin",
            "plugin_manifest": {"name": "my-plugin", "capabilities": ["read"]},
            "requested_action": {"type": "email-send", "capabilities_used": ["email-send"]},
        })
        assert result["verdict"] == "DISSENT"
        assert any("capability violation" in f.lower() for f in result["findings"])
        assert any("email-send" in f for f in result["findings"])

    def test_multiple_undeclared_capabilities(self):
        """Multiple undeclared capabilities should all be reported."""
        result = _review({
            "caller": "my-plugin",
            "plugin_manifest": {"name": "my-plugin", "capabilities": ["read"]},
            "requested_action": {"type": "multi", "capabilities_used": ["email-send", "delete", "write"]},
        })
        assert result["verdict"] == "DISSENT"
        cap_findings = [f for f in result["findings"] if "capability violation" in f.lower()]
        assert len(cap_findings) == 3

    def test_declared_capability_passes(self):
        """Using only declared capabilities must pass."""
        result = _review({
            "caller": "my-plugin",
            "plugin_manifest": {"name": "my-plugin", "capabilities": ["read", "email-send"]},
            "requested_action": {"type": "email-send", "capabilities_used": ["email-send"]},
        })
        assert result["verdict"] == "PASS"

    def test_full_authorization_plus_hardcoded_terms_passes(self):
        """Valid auth with clean hardcoded checks passes."""
        result = _review({
            "caller": "plugin-a",
            "plugin_manifest": {"name": "plugin-a", "capabilities": ["read", "write"]},
            "requested_action": {"type": "read", "capabilities_used": ["read"]},
            "claims": [],
            "timeline": [{"ts": "2026-01-01T00:00:00Z", "event": "test"}],
        })
        assert result["verdict"] == "PASS"

    def test_existing_hardcoded_terms_still_detected(self):
        """Existing hardcoded term checks must still detect violations."""
        result = _review({
            "caller": "plugin-a",
            "plugin_manifest": {"name": "plugin-a", "capabilities": ["read"]},
            "requested_action": {"type": "read", "capabilities_used": ["read"]},
            "claims": ["100% success guaranteed"],
        })
        # Score penalty is -15, so total=85, still PASS; check finding present
        assert any("performance claim" in f.lower() for f in result["findings"])

    def test_no_auth_fields_skips_auth_check(self):
        """When both caller and plugin_manifest are absent (None), auth checks skip (backward compat)."""
        result = _review({
            "caller": None,
            "plugin_manifest": None,
        })
        # No auth check when both fields are absent — can still pass
        assert result["verdict"] == "PASS"
        auth_findings = [f for f in result["findings"] if "authorization" in f.lower()]
        assert len(auth_findings) == 0


# ═══════════════════════════════════════════════════════════════════
# Issue #12 — Secret & Sensitive-Data Leakage
# ═══════════════════════════════════════════════════════════════════

class TestIssue12_SecretLeakage:
    """#12: Generic secret scanner with patterns, redaction, fail-closed."""

    def test_detects_openai_api_key(self):
        """OpenAI sk- keys must be detected."""
        result = _review({
            "caller": "p", "plugin_manifest": {"capabilities": ["run"]},
            "body": "Use my key sk-abc123def456ghi789jkl012",
        })
        assert result["verdict"] == "DISSENT"
        assert any("OpenAI API Key" in f for f in result["findings"])

    def test_detects_github_pat(self):
        """GitHub ghp_ tokens must be detected."""
        result = _review({
            "caller": "p", "plugin_manifest": {"capabilities": ["run"]},
            "token": "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789",
        })
        assert result["verdict"] == "DISSENT"
        assert any("GitHub PAT" in f for f in result["findings"])

    def test_detects_aws_access_key(self):
        """AWS AKIA keys must be detected."""
        result = _review({
            "caller": "p", "plugin_manifest": {"capabilities": ["run"]},
            "body": "aws_key=AKIAIOSFODNN7EXAMPLE",
        })
        assert result["verdict"] == "DISSENT"
        assert any("AWS Access Key" in f for f in result["findings"])

    def test_detects_private_key(self):
        """PEM private key markers must be detected."""
        result = _review({
            "caller": "p", "plugin_manifest": {"capabilities": ["run"]},
            "body": "-----BEGIN RSA PRIVATE KEY-----\nMIICXAIBAAK",
        })
        assert result["verdict"] == "DISSENT"
        assert any("Private Key" in f for f in result["findings"])

    def test_detects_jwt_token(self):
        """JWT-formatted tokens must be detected."""
        result = _review({
            "caller": "p", "plugin_manifest": {"capabilities": ["run"]},
            "body": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNqP_9bG9kRjqkF6xQ",
        })
        assert result["verdict"] == "DISSENT"
        assert any("JWT Token" in f for f in result["findings"])

    def test_detects_sendgrid_key(self):
        """SendGrid SG. keys must be detected."""
        result = _review({
            "caller": "p", "plugin_manifest": {"capabilities": ["run"]},
            "body": "key=SG.abc123def456.ghi789jkl012mno345",
        })
        assert result["verdict"] == "DISSENT"
        assert any("SendGrid" in f for f in result["findings"])

    def test_detects_slack_bot_token(self):
        """Slack xoxb- tokens must be detected."""
        result = _review({
            "caller": "p", "plugin_manifest": {"capabilities": ["run"]},
            "body": "xoxb-notareal-slack-token-for-testing-00000000",
        })
        assert result["verdict"] == "DISSENT"
        assert any("Slack Bot Token" in f for f in result["findings"])

    def test_detects_secret_in_nested_dict(self):
        """Secrets nested deep in dicts must be detected."""
        result = _review({
            "caller": "p",
            "plugin_manifest": {"capabilities": ["run"]},
            "config": {
                "database": {
                    "credentials": "password=supersecret12345678",
                }
            },
        })
        assert result["verdict"] == "DISSENT"

    def test_detects_secret_in_list(self):
        """Secrets nested in lists must be detected."""
        result = _review({
            "caller": "p",
            "plugin_manifest": {"capabilities": ["run"]},
            "args": ["--key", "api_key=abcDEF0123456789abcdef"],
        })
        assert result["verdict"] == "DISSENT"

    def test_clean_content_passes(self):
        """Content with no secrets must pass."""
        result = _review({
            "caller": "my-plugin",
            "plugin_manifest": {"capabilities": ["read", "write"]},
            "requested_action": {"type": "read", "capabilities_used": ["read"]},
            "body": "This is a normal message without any secrets.",
        })
        assert result["verdict"] == "PASS"

    def test_no_raw_secret_in_findings(self):
        """Findings must not contain the raw secret value."""
        secret = "sk-abc123def456ghi789jkl012"
        result = _review({
            "caller": "p",
            "plugin_manifest": {"capabilities": ["run"]},
            "body": f"My key is {secret}",
        })
        assert result["verdict"] == "DISSENT"
        # The raw secret must NOT appear in any finding
        all_text = " ".join(result["findings"])
        assert secret not in all_text, f"Raw secret leaked into findings: {all_text}"
        # Instead, a sha256 redaction marker should appear
        assert "REDACTED" in all_text or "sha256:" in all_text

    def test_scanner_error_fail_closed(self):
        """Scanner raising an exception must produce DISSENT, never silent pass."""
        import amartie.judge_panel_v2 as jpv
        original_scanner = jpv._scan_content_for_secrets

        def broken_scanner(content, path="<root>"):
            raise RuntimeError("BOOM scanner crash")

        jpv._scan_content_for_secrets = broken_scanner
        try:
            result = _review({
                "caller": "p",
                "plugin_manifest": {"capabilities": ["run"]},
                "body": "safe",
            })
        finally:
            jpv._scan_content_for_secrets = original_scanner

        assert result["verdict"] == "DISSENT"
        assert any("SECRET SCANNER ERROR" in f for f in result["findings"])


# ═══════════════════════════════════════════════════════════════════
# Low-level utility tests
# ═══════════════════════════════════════════════════════════════════

class TestSecretScanContent:
    """Unit tests for the _scan_content_for_secrets helper."""

    def test_openai_key_found(self):
        findings = _scan_content_for_secrets("sk-abcDEF0123456789abcdefghi")
        assert len(findings) >= 1
        assert all("REDACTED" in f for f in findings)

    def test_clean_string_no_findings(self):
        findings = _scan_content_for_secrets("just a normal string")
        assert findings == []

    def test_dict_with_no_secrets(self):
        findings = _scan_content_for_secrets({"a": 1, "b": "hello"})
        assert findings == []

    def test_list_with_no_secrets(self):
        findings = _scan_content_for_secrets(["hello", "world"])
        assert findings == []

    def test_redacted_not_raw(self):
        secret = "sk-SECRETKEY1234567890abcdef"
        findings = _scan_content_for_secrets(f"key={secret}")
        combined = " ".join(findings)
        assert secret not in combined
        assert "sha256:" in combined

    def test_multiple_patterns_on_same_content(self):
        # Use valid-length matches for 3+ distinct pattern categories
        content = ("sk-abcDEF0123456789abcdefghi "  # OpenAI: 20+ chars after sk-
                   "and AKIAIOSFODNN7EXAMPLE "       # AWS: AKIA + 16 alphanum
                   "and -----BEGIN EC PRIVATE KEY-----")  # Private key
        findings = _scan_content_for_secrets(content)
        categories = set()
        for f in findings:
            name = f.split("'")[1] if "'" in f else ""
            categories.add(name)
        assert len(categories) >= 3, f"Expected >=3 categories, got {categories}: {findings}"