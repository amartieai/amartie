import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _hash(obj):
    return hashlib.sha256(_canon(obj)).hexdigest()


class CustodyLog:
    """Append-only, hash-chained log of every action on a session file."""

    def __init__(self, path="custody.jsonl"):
        self.path = Path(path)
        self.entries = []
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self.entries.append(json.loads(line))

    def _last_hash(self):
        if not self.entries:
            return GENESIS
        return self.entries[-1]["hash"]

    def append(self, action, detail=None, actor="system"):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "actor": actor,
            "detail": detail or {},
            "prev_hash": self._last_hash(),
        }
        entry["hash"] = _hash(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":"), ensure_ascii=False) + "\n")
        self.entries.append(entry)
        return entry

    def verify(self):
        prev = GENESIS
        for index, entry in enumerate(self.entries):
            if entry.get("prev_hash") != prev:
                return False, f"chain break at index {index}"
            recomputed = _hash({k: v for k, v in entry.items() if k != "hash"})
            if entry.get("hash") != recomputed:
                return False, f"tamper at index {index}"
            prev = entry["hash"]
        return True, None

    def export(self, out="custody_export.json"):
        Path(out).write_text(json.dumps(self.entries, indent=2, ensure_ascii=False), encoding="utf-8")
        return out
