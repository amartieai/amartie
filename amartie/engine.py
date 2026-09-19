import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

CAPABILITY_FAMILIES = {
    "vision": {"vision", "multimodal", "vl"},
    "embedding": {"embed", "embedding"},
    "audio": {"audio", "whisper", "tts"},
    "tool": {"tool", "function", "agent"},
    "chat": {"chat", "text", "llm", "kimi", "deepseek", "gpt", "claude", "glm", "ling"},
}


def load_session(path):
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]


def extract_fields(entry):
    req = entry.get("request", {}) if isinstance(entry, dict) else {}
    resp = entry.get("response", {}) if isinstance(entry, dict) else {}
    billed = req.get("model") or (req.get("body") or {}).get("model")
    choices = resp.get("choices") or []
    choice0 = choices[0] if choices else {}
    returned = resp.get("model") or (resp.get("body") or {}).get("model") or choice0.get("model")
    session_id = (
        req.get("session_id")
        or (req.get("headers") or {}).get("x-session-id")
        or resp.get("id")
        or resp.get("session_id")
    )
    latency = resp.get("latency_ms") or resp.get("duration_ms") or entry.get("duration_ms")
    intent = req.get("intent") or (req.get("body") or {}).get("intent") or entry.get("intent") or "unspecified"
    return {
        "billed": billed,
        "returned": returned,
        "session_id": session_id,
        "latency_ms": latency,
        "intent": intent,
        "ts": entry.get("timestamp") or entry.get("ts") or datetime.now(timezone.utc).isoformat(),
    }


def _family_of(model):
    m = (model or "").lower()
    for fam, keys in CAPABILITY_FAMILIES.items():
        if any(k in m for k in keys):
            return fam
    return "chat"


def detect_swap(fields):
    if not fields.get("billed") or not fields.get("returned"):
        return None
    intent = fields.get("intent", "unspecified")
    billed_fam = _family_of(fields["billed"])
    returned_fam = _family_of(fields["returned"])
    if intent in ("chat", "unspecified") and fields["billed"] != fields["returned"]:
        kind = "model_swap"
    elif intent in CAPABILITY_FAMILIES and returned_fam != intent and returned_fam != billed_fam:
        kind = "intent_mismatch"
    else:
        return None
    return {
        "type": kind,
        "billed": fields["billed"],
        "returned": fields["returned"],
        "intent": intent,
        "session_id": fields["session_id"],
        "latency_ms": fields["latency_ms"],
        "ts": fields["ts"],
    }


def check_session(path):
    out = []
    for entry in load_session(path):
        mismatch = detect_swap(extract_fields(entry))
        if mismatch:
            out.append(mismatch)
    return out


def receipt_hash(mismatches):
    canonical = json.dumps(mismatches, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
