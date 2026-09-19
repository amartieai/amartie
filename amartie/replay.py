import hashlib
import json
from pathlib import Path

from .engine import check_session


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def replay(session_path, receipt_path):
    session = Path(session_path)
    receipt = Path(receipt_path)
    if not session.exists():
        return False, f"session file not found: {session}"
    if not receipt.exists():
        return False, f"receipt file not found: {receipt}"

    stored = json.loads(receipt.read_text(encoding="utf-8"))
    stored_hash = stored.get("receipt_hash") or stored.get("hash")
    if not stored_hash:
        return False, "receipt has no hash field"

    recomputed = check_session(session)
    recomputed_hash = hashlib.sha256(_canon(recomputed)).hexdigest()
    ok = recomputed_hash == stored_hash
    detail = {
        "session": str(session),
        "receipt": str(receipt),
        "stored_hash": stored_hash,
        "recomputed_hash": recomputed_hash,
        "match": ok,
        "mismatch_count_stored": len(stored.get("mismatches", [])),
        "mismatch_count_recomputed": len(recomputed),
    }
    return ok, detail


def verify_file(receipt_path):
    data = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    body = data.get("body", data.get("mismatches", []))
    stored = data.get("hash") or data.get("receipt_hash")
    recomputed = hashlib.sha256(_canon(body)).hexdigest()
    return stored == recomputed, stored, recomputed
