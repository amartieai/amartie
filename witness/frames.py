#!/usr/bin/env python3
"""witness/frames.py — extract frames from a session recording for OCR.

Usage: python3 witness/frames.py session.mkv --out frames/ --every 20
"""
import argparse, os, subprocess, sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recording")
    ap.add_argument("--out", default="frames")
    ap.add_argument("--every", type=int, default=20, help="seconds between frames")
    ap.add_argument("--dense-window", default=None,
                    help="HH:MM:SS-HH:MM:SS to also extract at 5s density")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a.recording,
                    "-vf", f"fps=1/{a.every}", "-q:v", "5",
                    os.path.join(a.out, "dense_%03d.jpg")], check=True)
    n = len([f for f in os.listdir(a.out) if f.startswith("dense_")])
    print(f"extracted {n} frames at {a.every}s -> {a.out}/")
    print("next: OCR the tape/volume readouts (tesseract) and log executions")


if __name__ == "__main__":
    sys.exit(main())
