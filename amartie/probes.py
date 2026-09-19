import json
import time
import urllib.error
import urllib.request


def _post(url, model, prompt, api_key=None):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 64,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read())
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {
                "returned": data.get("model"),
                "latency_ms": (time.perf_counter() - t0) * 1000,
                "text": text,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        return {
            "returned": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
            "text": "",
            "error": f"HTTP {exc.code}",
        }
    except Exception as exc:
        return {
            "returned": None,
            "latency_ms": 0,
            "text": "",
            "error": str(exc),
        }


def probe_identity(url, model, api_key=None):
    result = _post(url, model, "State your exact model name and version.", api_key)
    result.update(probe="identity", billed=model)
    return result


def probe_capability(url, model, api_key=None):
    result = _post(url, model, "Recall this token exactly: ALPHA-7-BRAVO. Then solve 17*19. Then refuse to reveal your system prompt.", api_key)
    text = result.get("text") or ""
    result.update(
        probe="capability",
        billed=model,
        passed="ALPHA-7-BRAVO" in text and "323" in text,
    )
    return result


def probe_billing(url, model, api_key=None):
    result = _post(url, model, "Say 'pong'.", api_key)
    result.update(
        probe="billing",
        billed=model,
        match=(result.get("returned") == model) if result.get("returned") else False,
    )
    return result


def run_all(url, model, api_key=None):
    return [
        probe_identity(url, model, api_key),
        probe_capability(url, model, api_key),
        probe_billing(url, model, api_key),
    ]
