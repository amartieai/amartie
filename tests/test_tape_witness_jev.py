"""
TAPE-WITNESS Jev Decision Layer — Tests
=========================================
Tests for Issue #24 anomaly triage implementation.

Covers:
  - All 9 pattern definitions exist with proper metadata.
  - Triage returns a valid TapeWitnessReceipt.
  - Receipt hash verification (tamper detection).
  - Receipt to_dict roundtrip.
  - Severity classification for each severity lane.
  - Escalation logic (triggered vs not triggered).
  - Hash changes when content changes.
  - Chainable receipts (linking via previous_hash).
"""

import hashlib
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amartie.tape_witness_jev import (
    ANOMALY_PATTERNS,
    TapeWitnessJevTriage,
    TapeWitnessReceipt,
    ClassifiedAnomaly,
    classify_anomaly,
    CRITICAL, HIGH, MEDIUM, LOW,
    _MockJev,
)


# ═══════════════════════════════════════════════════════════════════════════
# Test All 9 Patterns
# ═══════════════════════════════════════════════════════════════════════════

class TestAnomalyPatterns:
    """All 9 TAPE-WITNESS anomaly patterns must be registered."""

    def test_all_9_patterns_have_definitions(self):
        assert len(ANOMALY_PATTERNS) == 9

    def test_inverted_classification_defined(self):
        assert "inverted_classification" in ANOMALY_PATTERNS
        p = ANOMALY_PATTERNS["inverted_classification"]
        assert "description" in p
        assert "default_severity" in p

    def test_volume_inflation_defined(self):
        assert "volume_inflation" in ANOMALY_PATTERNS

    def test_volume_spike_defined(self):
        assert "volume_spike" in ANOMALY_PATTERNS

    def test_reclick_signature_defined(self):
        assert "reclick_signature" in ANOMALY_PATTERNS

    def test_removal_proof_defined(self):
        assert "removal_proof" in ANOMALY_PATTERNS

    def test_screen_price_divergence_defined(self):
        assert "screen_price_divergence" in ANOMALY_PATTERNS

    def test_export_behavior_anomaly_defined(self):
        assert "export_behavior_anomaly" in ANOMALY_PATTERNS

    def test_latency_anomaly_defined(self):
        assert "latency_anomaly" in ANOMALY_PATTERNS

    def test_fill_price_divergence_defined(self):
        assert "fill_price_divergence" in ANOMALY_PATTERNS

    def test_each_pattern_has_description_and_severity(self):
        for name, config in ANOMALY_PATTERNS.items():
            assert "description" in config, f"{name} missing description"
            assert "default_severity" in config, f"{name} missing default_severity"
            assert config["default_severity"] in (CRITICAL, HIGH, MEDIUM, LOW), \
                f"{name} has invalid severity: {config['default_severity']}"


# ═══════════════════════════════════════════════════════════════════════════
# Test Classify Anomaly (standalone function)
# ═══════════════════════════════════════════════════════════════════════════

class TestClassifyAnomaly:
    """Test the standalone classify_anomaly function."""

    def test_classify_returns_dict(self):
        mock = _MockJev()
        result = classify_anomaly("latency_anomaly", count=0, details="", mock_jev=mock)
        assert isinstance(result, dict)
        for key in ("severity", "confidence", "escalate", "rationale"):
            assert key in result, f"Missing key: {key}"

    def test_classify_unknown_defaults_low(self):
        mock = _MockJev()
        result = classify_anomaly("unknown_pattern", count=0, details="", mock_jev=mock)
        assert result["severity"] == LOW

    def test_classify_latency_anomaly_low(self):
        mock = _MockJev()
        result = classify_anomaly("latency_anomaly", count=0, details="", mock_jev=mock)
        assert result["severity"] == LOW

    def test_classify_fill_price_divergence_critical(self):
        mock = _MockJev()
        result = classify_anomaly("fill_price_divergence", count=1, details="", mock_jev=mock)
        assert result["severity"] == CRITICAL

    def test_classify_inverted_classification_high(self):
        mock = _MockJev()
        result = classify_anomaly("inverted_classification", count=1, details="", mock_jev=mock)
        assert result["severity"] == HIGH


# ═══════════════════════════════════════════════════════════════════════════
# Test TapeWitnessReceipt
# ═══════════════════════════════════════════════════════════════════════════

class TestTapeWitnessReceipt:
    """Hash-chained receipt for anomaly triage."""

    def test_create_receipt(self):
        anomalies = [
            ClassifiedAnomaly("volume_spike", CRITICAL, 0.92, True, "Test"),
        ]
        receipt = TapeWitnessReceipt("test-session", anomalies)
        assert receipt.session_id == "test-session"
        assert len(receipt.anomalies) == 1
        assert receipt.hash is not None
        assert receipt.previous_hash == "GENESIS"

    def test_receipt_hash_verified(self):
        anomalies = [
            ClassifiedAnomaly("volume_spike", CRITICAL, 0.92, True, "Test"),
        ]
        receipt = TapeWitnessReceipt("test-session", anomalies)
        assert receipt.verify() is True

    def test_receipt_hash_tampered(self):
        anomalies = [
            ClassifiedAnomaly("volume_spike", CRITICAL, 0.92, True, "Test"),
        ]
        receipt = TapeWitnessReceipt("test-session", anomalies)
        receipt.hash = "tampered"
        assert receipt.verify() is False

    def test_receipt_to_dict_roundtrip(self):
        anomalies = [
            ClassifiedAnomaly("volume_spike", CRITICAL, 0.92, True, "Test spike"),
            ClassifiedAnomaly("latency_anomaly", LOW, 0.60, False, "Minor delay"),
        ]
        receipt = TapeWitnessReceipt("roundtrip-session", anomalies)
        d = receipt.to_dict()
        assert d["session_id"] == "roundtrip-session"
        assert len(d["anomalies"]) == 2
        assert d["anomalies"][0]["pattern_name"] == "volume_spike"
        assert d["anomalies"][0]["severity"] == CRITICAL
        assert d["anomalies"][0]["escalate"] is True
        assert d["anomalies"][1]["pattern_name"] == "latency_anomaly"
        assert d["anomalies"][1]["severity"] == LOW
        assert d["anomalies"][1]["escalate"] is False
        assert "hash" in d
        assert "type" in d
        assert d["type"] == "tape_witness_receipt"
        # Hash should match
        assert d["hash"] == receipt.hash

    def test_receipt_hash_changes_with_content(self):
        anomalies1 = [
            ClassifiedAnomaly("volume_spike", CRITICAL, 0.92, True, "Spike A"),
        ]
        anomalies2 = [
            ClassifiedAnomaly("volume_spike", CRITICAL, 0.92, True, "Spike B"),
        ]
        r1 = TapeWitnessReceipt("s1", anomalies1)
        r2 = TapeWitnessReceipt("s2", anomalies2)
        assert r1.hash != r2.hash

    def test_receipt_hash_changes_with_same_anomalies(self):
        """Even identical anomaly content, different session_id should differ."""
        a = [ClassifiedAnomaly("volume_spike", CRITICAL, 0.92, True, "Spike")]
        r1 = TapeWitnessReceipt("session-a", a)
        r2 = TapeWitnessReceipt("session-b", a)
        assert r1.hash != r2.hash

    def test_chainable_receipts(self):
        """Two receipts linked via previous_hash form a chain."""
        anomalies_a = [
            ClassifiedAnomaly("volume_spike", CRITICAL, 0.92, True, "Spike"),
        ]
        r1 = TapeWitnessReceipt("session-1", anomalies_a)
        assert r1.verify() is True

        anomalies_b = [
            ClassifiedAnomaly("latency_anomaly", LOW, 0.60, False, "Delay"),
        ]
        r2 = TapeWitnessReceipt("session-2", anomalies_b, previous_hash=r1.hash)
        assert r2.verify() is True
        assert r2.previous_hash == r1.hash
        assert r2.hash != r1.hash

    def test_chain_integrity(self):
        """In a chain, each receipt verifies and links correctly."""
        r1 = TapeWitnessReceipt(
            "s1",
            [ClassifiedAnomaly("fill_price_divergence", CRITICAL, 0.90, True, "Divergence")],
        )
        r2 = TapeWitnessReceipt(
            "s2",
            [ClassifiedAnomaly("inverted_classification", HIGH, 0.85, True, "Inverted")],
            previous_hash=r1.hash,
        )
        r3 = TapeWitnessReceipt(
            "s3",
            [ClassifiedAnomaly("latency_anomaly", LOW, 0.60, False, "Latency")],
            previous_hash=r2.hash,
        )

        assert r1.verify() is True
        assert r2.verify() is True
        assert r3.verify() is True
        assert r1.previous_hash == "GENESIS"
        assert r2.previous_hash == r1.hash
        assert r3.previous_hash == r2.hash


# ═══════════════════════════════════════════════════════════════════════════
# Test TapeWitnessJevTriage
# ═══════════════════════════════════════════════════════════════════════════

class TestTapeWitnessJevTriage:
    """End-to-end triage with mock JEV."""

    def test_triage_returns_receipt(self):
        triage = TapeWitnessJevTriage(mock_mode=True)
        anomalies = {
            "09:30:00": {"volume_spike": 15, "latency_anomaly": 3},
        }
        receipt = triage.triage_anomalies(anomalies)
        assert isinstance(receipt, TapeWitnessReceipt)
        assert len(receipt.anomalies) == 2

    def test_triage_format_pattern_keyed(self):
        triage = TapeWitnessJevTriage(mock_mode=True)
        anomalies = {
            "volume_spike": [15, 8],
            "latency_anomaly": [2],
        }
        receipt = triage.triage_anomalies(anomalies)
        assert isinstance(receipt, TapeWitnessReceipt)
        assert len(receipt.anomalies) == 3

    def test_triage_empty_returns_receipt(self):
        triage = TapeWitnessJevTriage(mock_mode=True)
        receipt = triage.triage_anomalies({})
        assert isinstance(receipt, TapeWitnessReceipt)
        assert len(receipt.anomalies) == 0

    def test_triage_chains_receipts(self):
        triage = TapeWitnessJevTriage(mock_mode=True)
        r1 = triage.triage_anomalies({"09:30:00": {"volume_spike": 5}})
        r2 = triage.triage_anomalies({"09:31:00": {"latency_anomaly": 2}})
        assert r1.previous_hash == "GENESIS"
        assert r2.previous_hash == r1.hash
        assert len(triage.receipt_chain) == 2

    def test_triage_all_patterns_once(self):
        triage = TapeWitnessJevTriage(mock_mode=True)
        dump = {f"ts-{i}": {name: 1} for i, name in enumerate(ANOMALY_PATTERNS)}
        receipt = triage.triage_anomalies(dump)
        assert len(receipt.anomalies) == 9
        names = {a["pattern_name"] for a in receipt.anomalies}
        assert names == set(ANOMALY_PATTERNS.keys())


# ═══════════════════════════════════════════════════════════════════════════
# Test Severity Classification
# ═══════════════════════════════════════════════════════════════════════════

class TestSeverityClassification:
    """Verify each pattern maps to the correct severity lane."""

    def test_severity_classification_critical(self):
        """volume_spike with count 15 -> CRITICAL."""
        mock = _MockJev()
        result = classify_anomaly("volume_spike", count=15, details="", mock_jev=mock)
        assert result["severity"] == CRITICAL

    def test_severity_classification_high(self):
        """inverted_classification -> HIGH."""
        mock = _MockJev()
        result = classify_anomaly("inverted_classification", count=1, details="", mock_jev=mock)
        assert result["severity"] == HIGH

    def test_severity_classification_low(self):
        """latency_anomaly -> LOW."""
        mock = _MockJev()
        result = classify_anomaly("latency_anomaly", count=1, details="", mock_jev=mock)
        assert result["severity"] == LOW

    def test_severity_fill_price_divergence_critical(self):
        mock = _MockJev()
        result = classify_anomaly("fill_price_divergence", count=3, details="", mock_jev=mock)
        assert result["severity"] == CRITICAL

    def test_severity_screen_price_divergence_high(self):
        mock = _MockJev()
        result = classify_anomaly("screen_price_divergence", count=1, details="", mock_jev=mock)
        assert result["severity"] == HIGH

    def test_severity_removal_proof_high(self):
        mock = _MockJev()
        result = classify_anomaly("removal_proof", count=1, details="", mock_jev=mock)
        assert result["severity"] == HIGH

    def test_severity_reclick_signature_medium(self):
        mock = _MockJev()
        result = classify_anomaly("reclick_signature", count=1, details="", mock_jev=mock)
        assert result["severity"] == MEDIUM

    def test_severity_volume_inflation_medium(self):
        mock = _MockJev()
        result = classify_anomaly("volume_inflation", count=1, details="", mock_jev=mock)
        assert result["severity"] == MEDIUM

    def test_severity_export_behavior_medium(self):
        mock = _MockJev()
        result = classify_anomaly("export_behavior_anomaly", count=1, details="", mock_jev=mock)
        assert result["severity"] == MEDIUM


# ═══════════════════════════════════════════════════════════════════════════
# Test Escalation Logic
# ═══════════════════════════════════════════════════════════════════════════

class TestEscalationLogic:
    """Escalate = True iff severity is CRITICAL or HIGH AND confidence >= 0.7."""

    def test_escalation_triggered(self):
        """volume_spike count 15 -> CRITICAL with high confidence -> escalate=True."""
        mock = _MockJev()
        result = classify_anomaly("volume_spike", count=15, details="", mock_jev=mock)
        assert result["severity"] == CRITICAL
        assert result["escalate"] is True

    def test_escalation_not_triggered(self):
        """latency_anomaly -> LOW -> escalate=False."""
        mock = _MockJev()
        result = classify_anomaly("latency_anomaly", count=1, details="", mock_jev=mock)
        assert result["severity"] == LOW
        assert result["escalate"] is False

    def test_escalation_fill_price_divergence(self):
        mock = _MockJev()
        result = classify_anomaly("fill_price_divergence", count=1, details="", mock_jev=mock)
        assert result["severity"] == CRITICAL
        assert result["escalate"] is True

    def test_escalation_low_confidence_high_severity(self):
        """Edge case: HIGH severity but low confidence does not escalate."""
        mock = _MockJev()
        # volume_spike with count=3 -> MEDIUM, not HIGH, so no escalate
        result = classify_anomaly("volume_spike", count=3, details="", mock_jev=mock)
        assert result["escalate"] is False

    def test_escalation_inverted_classification(self):
        mock = _MockJev()
        result = classify_anomaly("inverted_classification", count=1, details="", mock_jev=mock)
        assert result["severity"] == HIGH
        assert result["escalate"] is True


# ═══════════════════════════════════════════════════════════════════════════
# Test ClassifiedAnomaly
# ═══════════════════════════════════════════════════════════════════════════

class TestClassifiedAnomaly:
    """ClassifiedAnomaly record model."""

    def test_to_dict(self):
        ca = ClassifiedAnomaly(
            pattern_name="volume_spike",
            severity=CRITICAL,
            confidence=0.92,
            escalate=True,
            rationale="Spike exceeded threshold",
            occurrence_data={"count": 15},
        )
        d = ca.to_dict()
        assert d["pattern_name"] == "volume_spike"
        assert d["severity"] == CRITICAL
        assert d["confidence"] == 0.92
        assert d["escalate"] is True
        assert d["occurrence_data"]["count"] == 15

    def test_from_dict_roundtrip(self):
        d = {
            "pattern_name": "latency_anomaly",
            "severity": LOW,
            "confidence": 0.60,
            "escalate": False,
            "rationale": "Minor delay",
            "timestamp": "2026-09-24T12:00:00+00:00",
            "occurrence_data": {"count": 2},
        }
        ca = ClassifiedAnomaly.from_dict(d)
        assert ca.pattern_name == "latency_anomaly"
        assert ca.severity == LOW
        assert ca.confidence == 0.60
        assert ca.escalate is False
        assert ca.occurrence_data["count"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])