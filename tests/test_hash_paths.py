import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HASH = REPO / "witness" / "hash.py"


def run_hash(root):
    return subprocess.run([sys.executable, str(HASH), str(root)],
                          capture_output=True, text=True, timeout=60)


class HashPathTests(unittest.TestCase):
    def test_paths_with_spaces_round_trip(self):
        """Finding #6: 'screens/session one.jpg' must parse back correctly,
        not become 'screens/session' with a false new observation each run."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "screens" / "session one.jpg"
            p.parent.mkdir()
            p.write_bytes(b"junk")
            run_hash(d)
            manifest = (Path(d) / "HASHES.txt").read_text()
            self.assertIn("screens/session one.jpg", manifest)
            r2 = run_hash(d)
            self.assertIn("0 new", r2.stdout)  # idempotent: no false re-add
            # and a genuine change to the spaced path IS detected
            p.write_bytes(b"tampered")
            r3 = run_hash(d)
            self.assertIn("1 changed", r3.stdout)

    def test_nested_paths_with_spaces(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "evidence dir" / "sub folder" / "a b.txt"
            p.parent.mkdir(parents=True)
            p.write_bytes(b"x")
            run_hash(d)
            r2 = run_hash(d)
            self.assertIn("0 new", r2.stdout)


if __name__ == "__main__":
    unittest.main()
