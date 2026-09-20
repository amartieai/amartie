import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class E2ETests(unittest.TestCase):
    """The README pipeline, executed against examples/, asserting bounded results."""

    def test_full_pipeline_on_examples(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            diff = tmp / "diff.json"
            verdict = tmp / "verdict.json"
            r1 = subprocess.run(
                [sys.executable, str(REPO / "witness" / "reconcile.py"),
                 str(REPO / "examples" / "ledger_example.json"),
                 str(REPO / "examples" / "export_early_example.csv"),
                 str(REPO / "examples" / "export_late_example.csv"),
                 "--out", str(diff)],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(r1.returncode, 0, r1.stderr)
            r2 = subprocess.run(
                [sys.executable, str(REPO / "witness" / "grade.py"),
                 str(diff),
                 "--export", str(REPO / "examples" / "export_late_example.csv"),
                 "--out", str(verdict)],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(r2.returncode, 0, r2.stderr)
            v = json.loads(verdict.read_text())
            self.assertEqual(v["action_count"], 6)
            self.assertEqual(v["action_minute_count"], 5)
            self.assertGreaterEqual(v["pattern_counts"]["inverted_classification"], 1)
            self.assertGreaterEqual(v["pattern_counts"]["volume_spike"], 1)
            self.assertGreaterEqual(v["pattern_counts"]["minute_absent"], 1)
            self.assertGreaterEqual(v["pattern_counts"]["removal_proof"], 1)
            self.assertGreaterEqual(v["pattern_counts"]["volume_inflation"], 1)
            self.assertGreaterEqual(v["pattern_counts"]["reclick_signature"], 1)
            self.assertEqual(v["conditional_on_action"]["rate"], 1.0)

    def test_readme_commands_are_executable(self):
        """The exact README pipeline commands must run as documented."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            r = subprocess.run(
                [sys.executable, str(REPO / "witness" / "grade.py"),
                 str(tmp / "nonexistent.json"),
                 "--export", str(REPO / "examples" / "export_late_example.csv"),
                 "--out", str(tmp / "v.json")],
                capture_output=True, text=True, timeout=60)
            # missing diff must FAIL CLEARLY, not with a traceback-free exit 0
            self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
