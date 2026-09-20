import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from witness.reconcile import load_export, load_attempts  # noqa: E402


class CustodyTests(unittest.TestCase):
    """Blocking findings 1-3 + high-priority 4/10 of the custody review."""

    def test_frames_ledger_integration_with_mock_ffmpeg(self):
        """Regression for the disconnected pipeline: frames.py output must be
        consumable by ledger.py. Mocks ffmpeg by pre-creating the images the
        real extractor would produce, with the exact frames.py naming."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            frames = tmp / "frames"
            frames.mkdir()
            # what frames.py emits: timestamped names + frames.jsonl index
            index = [
                {"frame": "frame_000001_2026-01-05T01-58-00.jpg",
                 "offset_seconds": 0.0, "timestamp": "2026-01-05T01:58:00"},
                {"frame": "frame_000002_2026-01-05T01-58-20.jpg",
                 "offset_seconds": 20.0, "timestamp": "2026-01-05T01:58:20"},
                {"frame": "frame_000003_2026-01-05T01-58-40.jpg",
                 "offset_seconds": 40.0, "timestamp": "2026-01-05T01:58:40"},
            ]
            for rec in index:
                (frames / rec["frame"]).write_bytes(b"\xff\xd8\xff\xe0mockjpeg")
            with open(frames / "frames.jsonl", "w") as f:
                for rec in index:
                    f.write(json.dumps(rec) + "\n")
            clicks = tmp / "clicks.txt"
            clicks.write_text("2026-01-05T01:58:41 SELL 1 @ 105.37\n")
            out = tmp / "ledger.json"
            receipts = tmp / "ledger_receipts.jsonl"

            r = subprocess.run(
                [sys.executable, str(REPO / "witness" / "ledger.py"),
                 str(frames), str(clicks), "--start", "01:58:00",
                 "--interval", "20", "--out", str(out),
                 "--receipts", str(receipts)],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            led = json.loads(out.read_text())["ledger"]
            self.assertEqual(len(led), 1)
            # nearest frame is the 01:58:40 one (1s away), NOT 01:58:20
            self.assertEqual(led[0]["frame"],
                             "frame_000003_2026-01-05T01-58-40.jpg")
            self.assertEqual(led[0]["frame_delta_s"], 1.0)
            # invocation receipt: custody of inputs and output
            lines = [json.loads(l) for l in receipts.read_text().splitlines() if l.strip()]
            inv = [l for l in lines if l.get("receipt") == "ledger_invocation"]
            self.assertEqual(len(inv), 1)
            self.assertIn("sha256", json.dumps(inv[0]["inputs"]["clicks"]))
            self.assertEqual(len(inv[0]["inputs"]["referenced_frames"]), 1)
            self.assertEqual(inv[0]["inputs"]["referenced_frames"][0]["frame"],
                             "frame_000003_2026-01-05T01-58-40.jpg")
            self.assertTrue(inv[0]["output"]["sha256"])
            self.assertEqual(inv[0]["parameters"]["interval"], 20)

    def test_malformed_attempts_are_recorded_not_silent(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "attempts.jsonl"
            p.write_text('{"ts": "2026-01-05T02:36:10", "payload": "undefined"}\n'
                         "NOT JSON AT ALL\n"
                         '{"ts": "2026-01-05T02:37:10", "payload": "undefined"}\n')
            attempts, malformed = load_attempts(str(p))
            self.assertEqual(len(attempts), 2)
            self.assertEqual(malformed, [{"line": 2, "error": "invalid JSON"}])

    def test_duplicate_export_minutes_reported(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "dup.csv"
            p.write_text("time,open,high,low,close,Vol,UpVol,DnVol\n"
                         "2026-01-05T01:59,105.3,105.4,105.2,105.3,4,4,0\n"
                         "2026-01-05T01:59,105.3,105.4,105.2,105.3,9,9,0\n")
            bars, dups = load_export(str(p))
            self.assertEqual(len(bars), 1)  # last wins, but...
            self.assertEqual(dups, [{"line": 3, "minute": "2026-01-05T01:59"}])


if __name__ == "__main__":
    unittest.main()
