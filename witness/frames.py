#!/usr/bin/env python3
"""witness/frames.py — extract timestamped frames from a session recording.

Frames are named with BOTH a sequence number and a wall-clock timestamp:
  frame_000001_2026-01-05T01-59-40.jpg
and an index sidecar maps every frame to its timestamp and offset:

  frames.jsonl: {"frame": "...", "timestamp": "2026-01-05T01:59:40",
                 "offset_seconds": 100.0}

Timestamps derive from --start-time (the recording's wall-clock start).
Without --start-time, frames are named by offset only
(frame_000001+100s.jpg) and the index carries offset_seconds — ledger.py
then requires --start to map them to wall clock. No wall-clock time is
ever silently inferred.

--dense-window HH:MM:SS-HH:MM:SS runs a SECOND extraction pass at
--dense-every seconds, limited to that window. Invalid or inverted
windows are rejected.

Usage:
  python3 witness/frames.py session.mkv --out frames/ --every 20 \
      --start-time 2026-01-05T01:58:43 [--dense-window 01:59:00-02:05:00]
"""
import argparse, datetime, json, os, re, subprocess, sys


def parse_hms(s):
    m = re.match(r"^(\d{2}):(\d{2}):(\d{2})$", s.strip())
    if not m:
        raise ValueError(f"invalid HH:MM:SS: {s!r}")
    hh, mm, ss = map(int, m.groups())
    if hh > 23 or mm > 59 or ss > 59:
        raise ValueError(f"out-of-range time: {s!r}")
    return datetime.timedelta(hours=hh, minutes=mm, seconds=ss)


def extract(recording, out, every, start_offset, prefix):
    """One ffmpeg pass; returns sorted list of (offset_seconds, filename)."""
    pattern = os.path.join(out, f"{prefix}_%06d.jpg")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", recording,
                    "-vf", f"fps=1/{every}", "-q:v", "5", pattern], check=True)
    out_files = []
    for f in os.listdir(out):
        m = re.match(rf"{prefix}_(\d+)\.jpg", f)
        if m:
            # ffmpeg numbers from 1; offset = (n-1)*every + start_offset
            out_files.append((start_offset + (int(m.group(1)) - 1) * every, f))
    return sorted(out_files)


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

    frames = extract(a.recording, a.out, a.every, 0.0, "frame")

    if a.dense_window:
        lo_s, hi_s = a.dense_window.split("-")
        try:
            lo, hi = parse_hms(lo_s), parse_hms(hi_s)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(2)
        if hi <= lo:
            print("error: dense window end must be after start", file=sys.stderr)
            sys.exit(2)
        # offsets are relative to recording start
        if a.start_time:
            t0 = datetime.datetime.fromisoformat(a.start_time)
            lo_off = (lo - datetime.timedelta(hours=t0.hour, minutes=t0.minute,
                                              seconds=t0.second)).total_seconds()
            hi_off = (hi - datetime.timedelta(hours=t0.hour, minutes=t0.minute,
                                              seconds=t0.second)).total_seconds()
        else:
            lo_off, hi_off = lo.total_seconds(), hi.total_seconds()
        dense = extract(a.recording, a.out, a.dense_every, 0.0, "dense")
        frames = sorted(set(frames + [f for f in dense
                                      if lo_off <= f[0] <= hi_off]))

    # build the index with timestamps
    index = []
    for offset, fname in frames:
        rec = {"frame": fname, "offset_seconds": offset}
        if a.start_time:
            t0 = datetime.datetime.fromisoformat(a.start_time)
            ts = t0 + datetime.timedelta(seconds=offset)
            rec["timestamp"] = ts.isoformat()
            # rename to carry the timestamp in the filename
            ts_name = fname.replace(".jpg", f"_{ts.isoformat().replace(':', '-')}.jpg")
            os.rename(os.path.join(a.out, fname), os.path.join(a.out, ts_name))
            rec["frame"] = ts_name
        index.append(rec)

    with open(os.path.join(a.out, "frames.jsonl"), "a") as f:  # append-only
        for rec in index:
            f.write(json.dumps(rec) + "\n")

    print(f"extracted {len(frames)} frames -> {a.out}/ (+ frames.jsonl index)")
    if a.start_time:
        print(f"  timestamps derived from --start-time {a.start_time}")
    else:
        print("  no --start-time: offsets only (pass --start to ledger.py)")
    print(f"  dense window: {a.dense_window or 'none'}")


if __name__ == "__main__":
    sys.exit(main())
