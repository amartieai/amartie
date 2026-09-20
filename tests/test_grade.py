import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from witness.grade import grade  # noqa: E402


def make_diff(patterns_per_minute):
    minutes = []
    for i, pats in enumerate(patterns_per_minute):
        minutes.append({
            "minute": f"2026-01-05T02:{i:02d}",
            "actions": [{"ts": f"2026-01-05T02:{i:02d}:00", "side": "SELL",
                         "qty": 1, "px": 105.0}],
            "findings": [{"pattern": p, "detected": True, "evidence": {}} for p in pats],
        })
    return {"schema_version": 2, "minutes": minutes,
            "session_findings": {"reclick_signature": [], "export_behavior_anomaly": []}}


class GradeTests(unittest.TestCase):
    def test_counts_structured_pattern_ids(self):
        diff = make_diff([["removal_proof", "inverted_classification"],
                          ["volume_spike", "spike_unclassified"],
                          ["minute_absent"]])
        v = grade(diff, [1, 2, 3])
        self.assertEqual(v["pattern_counts"]["removal_proof"], 1)
        self.assertEqual(v["pattern_counts"]["inverted_classification"], 1)
        self.assertEqual(v["pattern_counts"]["volume_spike"], 1)
        self.assertEqual(v["pattern_counts"]["spike_unclassified"], 1)
        self.assertEqual(v["pattern_counts"]["minute_absent"], 1)

    def test_actions_vs_minutes_distinct(self):
        diff = make_diff([[], []])
        diff["minutes"][0]["actions"].append(
            {"ts": "2026-01-05T02:00:20", "side": "SELL", "qty": 4, "px": 105.0})
        v = grade(diff, [1, 2, 3])
        self.assertEqual(v["action_count"], 3)
        self.assertEqual(v["action_minute_count"], 2)

    def test_unsupported_pattern_never_counted(self):
        diff = make_diff([["some_unknown_pattern"]])
        v = grade(diff, [1, 2, 3])
        for count in v["pattern_counts"].values():
            self.assertEqual(count, 0)

    def test_conditional_rate(self):
        diff = make_diff([["removal_proof"], []])
        v = grade(diff, [1, 2, 3])
        self.assertEqual(v["conditional_on_action"]["flagged_action_minutes"], 1)
        self.assertEqual(v["conditional_on_action"]["total_action_minutes"], 2)
        self.assertEqual(v["conditional_on_action"]["rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
