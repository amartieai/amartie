import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def write_receipt(mismatches, out_dir="receipts"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {
        "version": "0.1.0",
        "generated_at": ts,
        "engine": "amartie",
        "mismatches": mismatches,
        "count": len(mismatches),
    }
    body_hash = hashlib.sha256(_canon(body)).hexdigest()
    receipt = {
        "schema": "amartie.receipt.v1",
        "hash": body_hash,
        "receipt_hash": body_hash,
        "body": body,
    }
    path = out / f"{ts}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(path), body_hash
