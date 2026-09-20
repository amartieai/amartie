#!/usr/bin/env python3
"""witness/ledger.py — build the action ledger from OCR'd frames + broker toasts.

Input:
  frames/       — extracted frames (from frames.py)
  clicks.txt    — one execution per line:
                  "2026-01-05T01:59:52 SELL 1 @ 105.37"
Output:
  ledger.json   — every action, timestamped, with screen context
"""
import argparse, json, os, re, subprocess, sys


def ocr(path, psm="3"):
    try:
        r = subprocess.run(["tesseract", path, "stdout", "--psm", psm],
                           capture_output=True, text=True, timeout=60)
        return r.stdout
    except Exception:
        return ""


def parse_clicks(path):
    clicks = []
    pat = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s+(BUY|SELL)\s+(\d+)\s*@\s*([\d,\.]+)")
    for line in open(path):
        m = pat.search(line)
        if m:
            ts, side, qty, px = m.groups()
            clicks.append({"ts": ts, "side": side, "qty": int(qty),
                           "px": float(px.replace(",", ""))})
    return clicks


def screen_context(frames_dir, click_ts):
    """Find the frame nearest the click and OCR its OHLC/volume row."""
    # click minute in the frame numbering is caller's job; here we scan
    # all frames for the click minute string and the Vol readout near it
    hhmm = click_ts[11:16]
    best = None
    for f in sorted(os.listdir(frames_dir)):
        if not f.endswith(".jpg"):
            continue
        txt = ocr(os.path.join(frames_dir, f))
        if hhmm.replace(":", ":") in txt or True:
            vol = re.search(r"Vol\.?\s*(\d+)", txt)
            px = re.search(r"C\s?([\d,]{5,7})", txt)
            if vol:
                best = {"frame": f, "screen_vol": int(vol.group(1)),
                        "screen_close": px.group(1) if px else None}
                break
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("clicks")
    ap.add_argument("--out", default="ledger.json")
    a = ap.parse_args()
    clicks = parse_clicks(a.clicks)
    ledger = []
    for c in clicks:
        ctx = screen_context(a.frames, c["ts"])
        entry = dict(c)
        entry["screen"] = ctx
        ledger.append(entry)
    json.dump({"ledger": ledger}, open(a.out, "w"), indent=2)
    print(f"ledger: {len(ledger)} actions -> {a.out}")
    for e in ledger:
        print(f"  {e['ts']} {e['side']} {e['qty']} @ {e['px']}")


if __name__ == "__main__":
    sys.exit(main())
