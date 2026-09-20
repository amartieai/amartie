import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from witness.reconcile import reconcile  # noqa: E402


def make_ledger(tmp):
    ledger = {"ledger": [
        {"ts": "2026-01-05T01:59:52", "side": "SELL", "qty": 1, "px": 105.37,
         "screen": {"screen_vol": 1}},
        {"ts": "2026-01-05T01:59:58", "side": "SELL", "qty": 2, "px": 105.30,
         "screen": {"screen_vol": 1}},
    ]}
    p = tmp / "ledger.json"
    p.write_text(json.dumps(ledger))
    return str(p)


def make_export(tmp, name, rows):
    p = tmp / name
    p.write_text("time,open,high,low,close,Vol,UpVol,DnVol\n" +
                 "\n".join(",".join(str(c) for c in r) for r in rows))
    return str(p)


class ReconcileTests(unittest.TestCase):
    def test_export_order_is_argument_order_not_lexical(self):
        """Removal proof must use argument order: a bar present in the
        FIRST-supplied export and absent from the SECOND-supplied one is a
        removal, even when the second label sorts BEFORE the first."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path
            tmp = Path(d)
            ledger = make_ledger(tmp)
            # bar exists in the export supplied FIRST (label sorts LATER)
            early = make_export(tmp, "z_early.csv", [
                ("2026-01-05T01:59", 105.3, 105.4, 105.2, 105.3, 4, 4, 0)])
            late = make_export(tmp, "a_late.csv", [])  # no bars at all
            led = json.load(open(ledger))["ledger"]
            diff = reconcile(led, [("z_early.csv", __import__("witness.reconcile",
                             importlib=__import__("importlib")).load_export(early) if False else None)],
                             {}) if False else None
            # do it properly through the module
            from witness.reconcile import load_export
            diff = reconcile(led, [("z_early.csv", load_export(early)[0]),
                                   ("a_late.csv", load_export(late)[0])], {})
            pats = [f["pattern"] for m in diff["minutes"] for f in m["findings"]]
            self.assertIn("removal_proof", pats)

    def test_duplicate_actions_in_one_minute_aggregate(self):
        """Two actions in the same minute = ONE minute row, two action records."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path
            tmp = Path(d)
            led = json.load(open(make_ledger(tmp)))["ledger"]
            from witness.reconcile import load_export
            bars = load_export(make_export(tmp, "x.csv", [
                ("2026-01-05T01:59", 105.3, 105.4, 105.2, 105.3, 4, 4, 0)]))[0]
            diff = reconcile(led, [("x.csv", bars)], {})
            self.assertEqual(len(diff["minutes"]), 1)
            self.assertEqual(len(diff["minutes"][0]["actions"]), 2)

    def test_missing_screen_context_is_not_inflation(self):
        """No screen volume -> no volume_inflation finding, ever."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path
            tmp = Path(d)
            ledger = {"ledger": [
                {"ts": "2026-01-05T01:59:52", "side": "SELL", "qty": 1,
                 "px": 105.37, "screen": None}]}
            from witness.reconcile import load_export
            bars = load_export(make_export(tmp, "x.csv", [
                ("2026-01-05T01:59", 105.3, 105.4, 105.2, 105.3, 99, 99, 0)]))[0]
            diff = reconcile(ledger["ledger"], [("x.csv", bars)], {})
            pats = [f["pattern"] for m in diff["minutes"] for f in m["findings"]]
            self.assertNotIn("volume_inflation", pats)


if __name__ == "__main__":
    unittest.main()
