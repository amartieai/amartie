#!/usr/bin/env python3
"""witness/frames.py — extract timestamped frames from a session recording.

Frames are named with BOTH a sequence number and a wall-clock timestamp:
  frame_000001_2026-01-05T01-59-40.jpg
and an index sidecar maps every frame to its timestamp and offset.

--dense-window HH:MM:SS-HH:MM:SS runs a bounded SECOND extraction pass at
--dense-every seconds. Only frames inside that window are decoded and kept.
"""
import argparse, datetime, hashlib, json, os, re, subprocess, sys


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_hms(s):
    m = re.match(r"^(\d{2}):(\d{2}):(\d{2})$", s.strip())
    if not m:
        raise ValueError(f"invalid HH:MM:SS: {s!r}")
    hh, mm, ss = map(int, m.groups())
    if hh > 23 or mm > 59 or ss > 59:
        raise ValueError(f"out-of-range time: {s!r}")
    return datetime.timedelta(hours=hh, minutes=mm, seconds=ss)


def extract(recording, out, every, start_offset, prefix, duration=None):
    """Run one bounded ffmpeg pass and return (offset, filename) pairs."""
    if every <= 0:
        raise ValueError("frame interval must be greater than zero")
    if start_offset < 0:
        raise ValueError("start offset must not be negative")
    if duration is not None and duration <= 0:
        raise ValueError("extraction duration must be greater than zero")

    pattern = os.path.join(out, f"{prefix}_%06d.jpg")
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if start_offset:
        cmd += ["-ss", f"{start_offset:.6f}"]
    cmd += ["-i", recording]
    if duration is not None:
        cmd += ["-t", f"{duration:.6f}"]
    cmd += ["-vf", f"fps=1/{every}", "-q:v", "5", pattern]
    subprocess.run(cmd, check=True)

    out_files = []
    for f in os.listdir(out):
        m = re.match(rf"{re.escape(prefix)}_(\d+)\.jpg", f)
        if m:
            out_files.append((start_offset + (int(m.group(1)) - 1) * every, f))
    return sorted(out_files)


def window_offsets(window, start_time=None):
    lo_s, sep, hi_s = window.partition("-")
    if not sep:
        raise ValueError("dense window must be HH:MM:SS-HH:MM:SS")
    lo, hi = parse_hms(lo_s), parse_hms(hi_s)
    if hi <= lo:
        raise ValueError("dense window end must be after start")
    if start_time:
        t0 = datetime.datetime.fromisoformat(start_time)
        base = datetime.timedelta(hours=t0.hour, minutes=t0.minute,
                                  seconds=t0.second)
        lo_offset = (lo - base).total_seconds()
        hi_offset = (hi - base).total_seconds()
    else:
        lo_offset, hi_offset = lo.total_seconds(), hi.total_seconds()
    if lo_offset < 0 or hi_offset <= lo_offset:
        raise ValueError("dense window must fall after the recording start")
    return lo_offset, hi_offset


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recording")
    ap.add_argument("--out", default="frames")
    ap.add_argument("--every", type=int, default=20, help="seconds between frames")
    ap.add_argument("--dense-every", type=int, default=5,
                    help="seconds between frames inside --dense-window")
    ap.add_argument("--dense-window", default=None, help="HH:MM:SS-HH:MM:SS")
    ap.add_argument("--start-time", default=None,
                    help="recording start wall-clock time (ISO), e.g. 2026-01-05T01:58:43")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    try:
        frames = extract(a.recording, a.out, a.every, 0.0, "frame")
        if a.dense_window:
            lo_off, hi_off = window_offsets(a.dense_window, a.start_time)
            dense = extract(a.recording, a.out, a.dense_every, lo_off, "dense",
                            duration=hi_off - lo_off)
            frames = sorted(frames + dense)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    index = []
    for offset, fname in frames:
        rec = {"frame": fname, "offset_seconds": offset}
        if a.start_time:
            t0 = datetime.datetime.fromisoformat(a.start_time)
            ts = t0 + datetime.timedelta(seconds=offset)
            rec["timestamp"] = ts.isoformat()
            ts_name = fname.replace(".jpg", f"_{ts.isoformat().replace(':', '-')}.jpg")
            os.rename(os.path.join(a.out, fname), os.path.join(a.out, ts_name))
            rec["frame"] = ts_name
        index.append(rec)

    with open(os.path.join(a.out, "frames.jsonl"), "a") as f:
        for rec in index:
            f.write(json.dumps(rec) + "\n")

    # extraction custody receipt: recording hash, parameters, per-frame hashes
    receipt = {
        "receipt": "frames_invocation",
        "created_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "inputs": {"recording": {"path": a.recording,
                                 "sha256": sha256_file(a.recording)}},
        "parameters": {"every": a.every, "dense_every": a.dense_every,
                       "dense_window": a.dense_window,
                       "start_time": a.start_time},
        "output": {"index": os.path.join(a.out, "frames.jsonl"),
                   "index_sha256": sha256_file(os.path.join(a.out, "frames.jsonl")),
                   "frame_count": len(index)},
        "frames": [{"frame": rec["frame"],
                    "offset_seconds": rec["offset_seconds"],
                    "timestamp": rec.get("timestamp"),
                    "sha256": sha256_file(os.path.join(a.out, rec["frame"]))}
                   for rec in index],
    }
    with open(os.path.join(a.out, "frames_receipts.jsonl"), "a") as rf:
        rf.write(json.dumps(receipt) + "\n")

    print(f"extracted {len(frames)} frames -> {a.out}/ (+ frames.jsonl index)")
    print(f"  dense window: {a.dense_window or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
