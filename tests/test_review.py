import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from witness.review import make_submission, census, sanitize_submission  # noqa: E402


def make_verdict(path, rate=1.0):
    v = {
        "schema_version": 2,
        "action_count": 6,
        "action_minute_count": 5,
        "minutes_with_findings": 5 if rate >= 0.5 else 1,
        "pattern_counts": {"inverted_classification": 4, "removal_proof": 3,
                           "volume_spike": 3, "minute_absent": 3,
                           "volume_inflation": 4, "reclick_signature": 2,
                           "spike_unclassified": 1, "screen_price_divergence": 1,
                           "export_behavior_anomaly": 1},
        "conditional_on_action": {"flagged_action_minutes": 5 if rate >= 0.5 else 1,
                                  "total_action_minutes": 5, "rate": rate},
        "quiet_baseline": {"median_volume": 8, "bars": 90,
                           "excluded_action_minutes": True},
    }
    Path(path).write_text(json.dumps(v))
    return v


class ReviewTests(unittest.TestCase):
    def test_submission_is_anonymized(self):
        with tempfile.TemporaryDirectory() as d:
            v = make_verdict(Path(d) / "verdict.json")
            s = make_submission(str(Path(d) / "verdict.json"),
                                "micro-futures", "2026-01-05T01:30/04:30")
            blob = json.dumps(s)
            for deny in ("account", "name", "path", "home", "operator"):
                self.assertNotIn(deny, blob.lower().replace("path", "path")
                                 if False else blob)
            # the denylist check is on KEYS; values must not leak paths either
            self.assertNotIn(d, blob)  # no local paths in the submission
            self.assertEqual(s["action_count"], 6)
            self.assertTrue(s["verdict_sha256"])

    def test_identity_fields_rejected(self):
        with self.assertRaises(ValueError):
            sanitize_submission({"account_number": "12345",
                                 "pattern_counts": {}})
        with self.assertRaises(ValueError):
            sanitize_submission({"ledger": ["raw"], "pattern_counts": {}})

    def test_census_aggregates_and_bounds(self):
        with tempfile.TemporaryDirectory() as d:
            subs = []
            for i, rate in enumerate([1.0, 1.0, 1.0, 0.2, 1.0, 1.0, 1.0, 1.0]):
                vp = Path(d) / f"v{i}.json"
                make_verdict(vp, rate)
                sp = Path(d) / f"s{i}.json"
                json.dump(make_submission(str(vp),
                          "micro-futures" if i % 2 else "forex",
                          "2026-01-05T01:30/04:30"), open(sp, "w"))
                subs.append(str(sp))
            c = census(subs)
            self.assertEqual(c["sessions"], 8)
            self.assertEqual(c["overall"]["flagged_sessions"], 7)
            self.assertEqual(c["overall"]["flagged_rate"], 0.875)
            lo, hi = c["overall"]["wilson_95"]
            self.assertTrue(0.5 < lo < 0.875 < hi < 1.0)
            self.assertEqual(c["by_asset_class"]["forex"]["sessions"], 4)
            self.assertEqual(c["by_asset_class"]["micro-futures"]["sessions"], 4)
            # population pattern totals are summed, not averaged
            self.assertEqual(c["patterns_population_totals"]
                             ["inverted_classification"], 32)

    def test_census_skips_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            good = Path(d) / "good.json"
            vp = Path(d) / "v.json"
            make_verdict(vp)
            json.dump(make_submission(str(vp), "forex", "w"),
                      open(good, "w"))
            bad = Path(d) / "bad.json"
            bad.write_text(json.dumps({"account": "x"}))
            c = census([str(good), str(bad)])
            self.assertEqual(c["sessions"], 1)


if __name__ == "__main__":
    unittest.main()
