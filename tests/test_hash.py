import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HASH = REPO / "witness" / "hash.py"


def run_hash(root):
    r = subprocess.run([sys.executable, str(HASH), str(root)],
                       capture_output=True, text=True, timeout=60)
    return r


class HashTests(unittest.TestCase):
    def test_idempotent_when_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.txt").write_text("hello")
            run_hash(d)
            manifest = Path(d) / "HASHES.txt"
            first = manifest.read_text()
            run_hash(d)
            self.assertEqual(first, manifest.read_text())

    def test_changed_file_gets_new_observation(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.txt"
            p.write_text("hello")
            run_hash(d)
            p.write_text("tampered")  # simulate a change
            run_hash(d)
            lines = [l for l in (Path(d) / "HASHES.txt").read_text().splitlines() if l.strip()]
            self.assertEqual(len(lines), 2)  # original + new observation
            self.assertNotEqual(lines[0].split()[0], lines[1].split()[0])
            self.assertTrue(lines[1].endswith("Z"))  # timestamped

    def test_hash_value_is_correct_sha256(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.txt"
            p.write_text("hello")
            run_hash(d)
            expected = hashlib.sha256(b"hello").hexdigest()
            first = (Path(d) / "HASHES.txt").read_text().splitlines()[0]
            self.assertTrue(first.startswith(expected))


if __name__ == "__main__":
    unittest.main()
