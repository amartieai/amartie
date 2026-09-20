#!/usr/bin/env python3
"""witness/ledger.py — build the action ledger from OCR'd frames + broker toasts.

Input:
  frames/       — extracted frames (from frames.py), named dense_NNN.jpg
                  (NNN * --interval seconds after --start) or frame_HHMMSS.jpg
  clicks.txt    — one execution per line:
                  "2026-01-05T01:59:52 SELL 1 @ 105.37"
  --start       — recording start time (HH:MM:SS) for frame->time mapping
  --interval    — seconds between frames (must match frames.py --every)

Output:
  ledger.json           — every action, timestamped, with screen context
  ledger_receipts.jsonl — append-only receipt per action (never overwritten)

Frame association: each action is matched to the frame whose derived
timestamp is NEAREST the action timestamp, within half an interval.
Actions with no frame inside the tolerance get screen=null and are
reported — never silently matched to a far frame.
"""
import argparse, datetime, json, os, re, subprocess, sys


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


def frame_times(frames_dir, start, interval):
    """Map frame filename -> datetime. dense_NNN.jpg => NNN*interval seconds
    after start; frame_HHMMSS.jpg => absolute clock time that day."""
    t0 = datetime.datetime.strptime(start, "%H:%M:%S")
    out = {}
    for f in sorted(os.listdir(frames_dir)):
        if not f.endswith(".jpg"):
            continue
        # New frames.py index format: frame_000001_2026-01-05T01:59:40.jpg
        m = re.match(r"frame_(\d+)_(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})\.jpg", f)
        if m:
            ts = m.group(2).replace("-", ":", 2)
            out[f] = datetime.datetime.fromisoformat(ts)
            continue
        m = re.match(r"frame_(\d{2})(\d{2})(\d{2})\.jpg", f)
        if m:
            hh, mm, ss = map(int, m.groups())
            out[f] = t0.replace(hour=hh, minute=mm, second=ss)
            continue
        m = re.match(r"dense_(\d+)\.jpg", f)
        if m:
            out[f] = t0 + datetime.timedelta(seconds=int(m.group(1)) * interval)
    return out


def frame_index(frames_dir, start, interval):
    """Prefer the explicit frames.jsonl index emitted by frames.py.
    Fall back to legacy filename-based mapping for older directories."""
    index_path = os.path.join(frames_dir, "frames.jsonl")
    if os.path.exists(index_path):
        out = {}
        with open(index_path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                frame = rec.get("frame")
                if not frame:
                    continue
                ts = rec.get("timestamp")
                if ts:
                    out[os.path.basename(frame)] = datetime.datetime.fromisoformat(ts)
                    continue
                offset = rec.get("offset_seconds")
                if offset is not None:
                    base = datetime.datetime.strptime(start, "%H:%M:%S")
                    out[os.path.basename(frame)] = base + datetime.timedelta(seconds=float(offset))
        if out:
            return out
    return frame_times(frames_dir, start, interval)


def parse_readout(txt):
    """Pull the OHLC row's close and Vol from OCR text (last match wins)."""
    vol = None
    for m in re.finditer(r"Vol\.?\s*(\d+)", txt):
        vol = int(m.group(1))
    close = None
    for m in re.finditer(r"[C€CS]\s?([\d,]{4,8}(?:\.\d+)?)", txt):
        v = m.group(1).replace(",", "")
        try:
            if 0.01 < float(v) < 10_000_000:
                close = float(v)
        except ValueError:
            pass
    return close, vol


def nearest_frame(ftimes, action_dt, tolerance_s):
    best, best_d = None, None
    for f, t in ftimes.items():
        d = abs((t - action_dt).total_seconds())
        if best_d is None or d < best_d:
            best, best_d = f, d
    if best is None or best_d > tolerance_s:
        return None, None
    return best, best_d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("clicks")
    ap.add_argument("--out", default="ledger.json")
    ap.add_argument("--receipts", default="ledger_receipts.jsonl")
    ap.add_argument("--start", required=True, help="recording start HH:MM:SS")
    ap.add_argument("--interval", type=int, default=20, help="seconds between frames")
    a = ap.parse_args()

    clicks = parse_clicks(a.clicks)
    ftimes = frame_index(a.frames, a.start, a.interval)
    if not ftimes:
        print("no mappable frames found — use dense_NNN.jpg or frame_HHMMSS.jpg "
              "naming and pass --start/--interval")
        sys.exit(1)
    tol = a.interval / 2 + 1

    ocr_cache = {}
    ledger = []
    for c in clicks:
        adt = datetime.datetime.fromisoformat(c["ts"])
        fname, delta = nearest_frame(ftimes, adt, tol)
        entry = dict(c)
        entry["frame"] = fname
        entry["frame_delta_s"] = round(delta, 1) if delta is not None else None
        entry["screen"] = None
        if fname:
            if fname not in ocr_cache:
                ocr_cache[fname] = ocr(os.path.join(a.frames, fname))
            close, vol = parse_readout(ocr_cache[fname])
            if vol is not None or close is not None:
                entry["screen"] = {"screen_vol": vol, "screen_close": close,
                                   "frame": fname, "frame_delta_s": entry["frame_delta_s"]}
        ledger.append(entry)

    json.dump({"ledger": ledger}, open(a.out, "w"), indent=2)
    with open(a.receipts, "a") as rf:  # append-only
        for e in ledger:
            rf.write(json.dumps({"receipt": "action", **e}) + "\n")

    matched = sum(1 for e in ledger if e["frame"])
    screen = sum(1 for e in ledger if e["screen"])
    print(f"ledger: {len(ledger)} actions -> {a.out}")
    print(f"  frames matched within {tol:.0f}s: {matched}/{len(ledger)}")
    print(f"  screen context read: {screen}/{len(ledger)}")
    for e in ledger:
        print(f"  {e['ts']} {e['side']} {e['qty']} @ {e['px']}"
              f"  frame={e['frame']} d={e['frame_delta_s']}s")


if __name__ == "__main__":
    sys.exit(main())
