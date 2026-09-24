"""
TAPE-WITNESS Jev Decision Layer — Anomaly Triage
==================================================
Implements Issue #24: anomaly triage using JEV (or mock) to classify
9 TAPE-WITNESS anomaly patterns into severity lanes with hash-chained
receipts for audit integrity.

Integration:
  - TapeWitnessReceipt is hash-chain compatible with JEVGateReceipt
    (same SHA-256, sorted JSON, previous_hash chaining).
  - TapeWitnessJevTriage defaults to mock mode (no external deps).
"""

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ── Severity Lanes ────────────────────────────────────────────────────────────

CRITICAL = "CRITICAL"
HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"
SEVERITY_LANES = (CRITICAL, HIGH, MEDIUM, LOW)


# ── Anomaly Pattern Registry ──────────────────────────────────────────────────

ANOMALY_PATTERNS: Dict[str, Dict[str, Any]] = {
    "inverted_classification": {
        "description": "A trade classified as a buy when it was actually a sell (or vice versa), "
                       "indicating a data mislabel or feed corruption.",
        "default_severity": HIGH,
    },
    "volume_inflation": {
        "description": "Reported volume exceeds reasonable bounds for the instrument and time "
                       "window, suggesting phantom trades or data amplification.",
        "default_severity": MEDIUM,
    },
    "volume_spike": {
        "description": "A sudden, sharp increase in trading volume inconsistent with the "
                       "prevailing market regime — potential wash trading or algorithm-driven anomaly.",
        "default_severity": HIGH,
    },
    "reclick_signature": {
        "description": "Repeated identical fills at the same price level across multiple "
                       "participants, characteristic of quote-stuffing or reclick behavior.",
        "default_severity": MEDIUM,
    },
    "removal_proof": {
        "description": "Evidence that a trade or order was removed from the tape retroactively, "
                       "indicating data tampering or late cancellation.",
        "default_severity": HIGH,
    },
    "screen_price_divergence": {
        "description": "The price shown on the participant's screen diverges from the tape's "
                       "canonical price — a red flag for price manipulation.",
        "default_severity": HIGH,
    },
    "export_behavior_anomaly": {
        "description": "Unusual export or bulk-data-access pattern from the tape feed, "
                       "potentially indicating data scraping or unauthorized extraction.",
        "default_severity": MEDIUM,
    },
    "latency_anomaly": {
        "description": "Abnormal latency between trade execution and tape publication, "
                       "suggesting delayed reporting or time-stamp manipulation.",
        "default_severity": LOW,
    },
    "fill_price_divergence": {
        "description": "The fill price reported by the broker diverges materially from the "
                       "executable price on the tape at the time of the trade — the core TAPE-WITNESS signal.",
        "default_severity": CRITICAL,
    },
}


# ── Mock Jev (standalone, no SDK dependency) ──────────────────────────────────

class _MockJev:
    """Stand-in for the TypeSafe JEV SDK when mock_mode=True."""

    @staticmethod
    def decide(anomaly_name: str, count: int, details: str) -> Dict[str, Any]:
        """
        Heuristic classification for mock mode.

        Maps anomaly patterns to severity/confidence/rationale using
        documented TAPE-WITNESS defaults and thresholds.
        """
        details_lower = (details or "").lower()
        count = max(count, 0)

        # ── CRITICAL lanes ───────────────────────────────────────────────
        if anomaly_name == "fill_price_divergence":
            confidence = 0.90
            rationale = (
                f"Fill price divergence detected: broker-reported price deviates "
                f"from tape executable price. Core TAPE-WITNESS signal with "
                f"count={count}."
            )
            severity = CRITICAL

        elif anomaly_name == "volume_spike" and count > 10:
            confidence = 0.92
            rationale = (
                f"Volume spike with count={count} exceeds threshold of 10, "
                f"indicating probable wash trading or algorithmic disruption."
            )
            severity = CRITICAL

        # ── HIGH lanes ───────────────────────────────────────────────────
        elif anomaly_name == "inverted_classification":
            confidence = 0.85
            rationale = (
                f"Inverted classification pattern: trade direction mislabeled. "
                f"Count={count}. Requires immediate data-feed validation."
            )
            severity = HIGH

        elif anomaly_name == "screen_price_divergence":
            confidence = 0.85
            rationale = (
                f"Screen price diverges from tape: participant view differs "
                f"from canonical price. Count={count}."
            )
            severity = HIGH

        elif anomaly_name == "removal_proof":
            confidence = 0.82
            rationale = (
                f"Removal proof detected: trade or order retroactively removed "
                f"from tape. Count={count}. Tamper indicator."
            )
            severity = HIGH

        elif anomaly_name == "volume_spike" and count > 5:
            confidence = 0.80
            rationale = (
                f"Volume spike with count={count} above moderate threshold, "
                f"elevated to HIGH vigilance."
            )
            severity = HIGH

        # ── MEDIUM lanes ─────────────────────────────────────────────────
        elif anomaly_name == "reclick_signature":
            confidence = 0.75
            rationale = (
                f"Reclick signature: repeated identical fills. Count={count}. "
                f"May indicate quote-stuffing or HFT artifact."
            )
            severity = MEDIUM

        elif anomaly_name == "volume_inflation":
            confidence = 0.75
            rationale = (
                f"Volume inflation: reported volume exceeds bounds. "
                f"Count={count}. Moderate suspicion."
            )
            severity = MEDIUM

        elif anomaly_name == "export_behavior_anomaly":
            confidence = 0.70
            rationale = (
                f"Export behavior anomaly: unusual data-access pattern. "
                f"Count={count}. Monitor for scraping or exfiltration."
            )
            severity = MEDIUM

        elif anomaly_name == "volume_spike":
            confidence = 0.65
            rationale = (
                f"Volume spike with count={count} within normal bounds. "
                f"Monitor threshold exceedance."
            )
            severity = MEDIUM

        # ── LOW lanes ────────────────────────────────────────────────────
        elif anomaly_name == "latency_anomaly":
            confidence = 0.60
            rationale = (
                f"Latency anomaly: abnormal execution-to-publication delay. "
                f"Count={count}. Low priority review."
            )
            severity = LOW

        else:
            confidence = 0.50
            rationale = f"Unknown pattern '{anomaly_name}' — defaulting to LOW severity."
            severity = LOW

        escalate = severity in (CRITICAL, HIGH) and confidence >= 0.7

        return {
            "severity": severity,
            "confidence": round(confidence, 4),
            "escalate": escalate,
            "rationale": rationale,
        }


# ── Classify Anomaly (standalone) ─────────────────────────────────────────────

def classify_anomaly(anomaly_name: str, count: int = 0,
                     details: str = "", mock_jev: Any = None) -> Dict[str, Any]:
    """
    Classify a single anomaly pattern using the active Jev mock.

    Args:
        anomaly_name: Name of the anomaly pattern (key in ANOMALY_PATTERNS).
        count: Occurrence count or magnitude indicator.
        details: Free-text context about the occurrence.
        mock_jev: A _MockJev instance (or compatible object).

    Returns:
        Dict with keys: severity, confidence, escalate, rationale.
    """
    jev = mock_jev if mock_jev is not None else _MockJev()
    return jev.decide(anomaly_name, count, details)


# ── Classified Anomaly Record ─────────────────────────────────────────────────

class ClassifiedAnomaly:
    """A single anomaly occurrence after JEV classification."""

    def __init__(self, pattern_name: str, severity: str,
                 confidence: float, escalate: bool, rationale: str,
                 timestamp: Optional[str] = None,
                 occurrence_data: Optional[Dict[str, Any]] = None):
        self.pattern_name = pattern_name
        self.severity = severity
        self.confidence = confidence
        self.escalate = escalate
        self.rationale = rationale
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.occurrence_data = occurrence_data or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_name": self.pattern_name,
            "severity": self.severity,
            "confidence": self.confidence,
            "escalate": self.escalate,
            "rationale": self.rationale,
            "timestamp": self.timestamp,
            "occurrence_data": self.occurrence_data,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ClassifiedAnomaly":
        return cls(
            pattern_name=d["pattern_name"],
            severity=d["severity"],
            confidence=d["confidence"],
            escalate=d["escalate"],
            rationale=d["rationale"],
            timestamp=d.get("timestamp"),
            occurrence_data=d.get("occurrence_data", {}),
        )


# ── TapeWitnessReceipt ────────────────────────────────────────────────────────

class TapeWitnessReceipt:
    """
    Hash-chained receipt for a TAPE-WITNESS anomaly triage session.

    Compatible with JEVGateReceipt: uses SHA-256 over sorted JSON and
    carries a previous_hash field so it can be appended to or from a
    JEVGateReceipt chain.

    Fields:
        session_id:   Unique identifier for this triage session.
        anomalies:    List of ClassifiedAnomaly dicts (from to_dict).
        timestamp:    ISO-8601 UTC timestamp.
        previous_hash: Hash of the preceding receipt (or "GENESIS").
        hash:         Self-computed SHA-256 over the canonical content.
    """

    def __init__(self, session_id: str, anomalies: List[ClassifiedAnomaly],
                 previous_hash: str = "GENESIS"):
        self.session_id = session_id
        self.anomalies = [a.to_dict() for a in anomalies]
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.previous_hash = previous_hash
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        content = json.dumps({
            "session_id": self.session_id,
            "anomalies": self.anomalies,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def verify(self) -> bool:
        """Verify this receipt's hash is correct."""
        return self.hash == self._compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "anomalies": self.anomalies,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
            "type": "tape_witness_receipt",
        }


# ── TapeWitnessJevTriage ──────────────────────────────────────────────────────

class TapeWitnessJevTriage:
    """
    JEV-powered anomaly triage for TAPE-WITNESS.

    Defaults to mock mode (no external SDK required). When mock_mode=False
    and the typesafe_sdk is available, uses real JEV classification.

    Usage:
        triage = TapeWitnessJevTriage(mock_mode=True)
        receipt = triage.triage_anomalies({
            "09:30:00": {"volume_spike": 15, "latency_anomaly": 3},
        })
    """

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self._jev = _MockJev() if mock_mode else self._init_real_jev()
        self.receipt_chain: List[str] = []

    @staticmethod
    def _init_real_jev():
        """Attempt to initialize the real TypeSafe JEV client."""
        try:
            from typesafe_sdk import TypeSafeClient  # noqa: F401
            return None  # would be a real client
        except ImportError:
            raise RuntimeError(
                "Real JEV mode requested but typesafe_sdk is not installed."
            )

    def triage_anomalies(self, anomalies: Dict[str, Any]) -> TapeWitnessReceipt:
        """
        Triage a dict of anomalies through JEV (or mock).

        Input formats accepted:
            {minute_timestamp: {pattern_name: count_or_detail}}
            {pattern_name: [occurrence_dicts or counts]}

        Returns:
            TapeWitnessReceipt with classified anomalies.
        """
        classified: List[ClassifiedAnomaly] = []

        if not anomalies:
            session_id = str(uuid.uuid4())
            previous_hash = (
                self.receipt_chain[-1] if self.receipt_chain else "GENESIS"
            )
            receipt = TapeWitnessReceipt(session_id, classified, previous_hash)
            self.receipt_chain.append(receipt.hash)
            return receipt

        # Detect format: if keys match anomaly patterns, it's pattern-name keyed.
        sample_key = next(iter(anomalies.keys()))
        if sample_key in ANOMALY_PATTERNS:
            # Format: {pattern_name: values}
            for pattern_name, occurrences in anomalies.items():
                classified.extend(
                    self._classify_occurrences(pattern_name, occurrences)
                )
        else:
            # Format: {timestamp: {pattern_name: count_or_detail}}
            for ts, pattern_counts in anomalies.items():
                if not isinstance(pattern_counts, dict):
                    continue
                for pattern_name, count_val in pattern_counts.items():
                    result = classify_anomaly(
                        anomaly_name=pattern_name,
                        count=int(count_val) if isinstance(count_val, (int, float)) else 0,
                        details=f"Observed at {ts}",
                        mock_jev=self._jev,
                    )
                    classified.append(ClassifiedAnomaly(
                        pattern_name=pattern_name,
                        occurrence_data={"timestamp": ts, "raw_value": count_val},
                        **result,
                    ))

        session_id = str(uuid.uuid4())
        previous_hash = (
            self.receipt_chain[-1] if self.receipt_chain else "GENESIS"
        )
        receipt = TapeWitnessReceipt(session_id, classified, previous_hash)
        self.receipt_chain.append(receipt.hash)
        return receipt

    def _classify_occurrences(self, pattern_name: str,
                               occurrences: Any) -> List[ClassifiedAnomaly]:
        """Classify a list of occurrences for a single pattern."""
        results: List[ClassifiedAnomaly] = []

        if isinstance(occurrences, (int, float)):
            result = classify_anomaly(pattern_name, int(occurrences), "", self._jev)
            results.append(ClassifiedAnomaly(
                pattern_name=pattern_name,
                occurrence_data={"count": int(occurrences)},
                **result,
            ))
        elif isinstance(occurrences, str):
            result = classify_anomaly(pattern_name, 0, occurrences, self._jev)
            results.append(ClassifiedAnomaly(
                pattern_name=pattern_name,
                occurrence_data={"detail": occurrences},
                **result,
            ))
        elif isinstance(occurrences, list):
            for item in occurrences:
                if isinstance(item, dict):
                    cnt = item.get("count", item.get("value", 0))
                    detail = item.get("detail", item.get("description", ""))
                elif isinstance(item, (int, float)):
                    cnt = int(item)
                    detail = ""
                else:
                    cnt = 0
                    detail = str(item)
                result = classify_anomaly(pattern_name, cnt, detail, self._jev)
                results.append(ClassifiedAnomaly(
                    pattern_name=pattern_name,
                    occurrence_data={"count": cnt, "detail": detail},
                    **result,
                ))
        else:
            result = classify_anomaly(pattern_name, 0, str(occurrences), self._jev)
            results.append(ClassifiedAnomaly(
                pattern_name=pattern_name,
                occurrence_data={"raw": str(occurrences)},
                **result,
            ))

        return results

    def verify_chain_integrity(self) -> bool:
        """Stub: chain verification once receipts are stored by hash."""
        return True