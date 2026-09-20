#!/usr/bin/env python3
"""witness/hash.py — append-only hash manifest for an evidence directory.

Usage: python3 witness/hash.py [dir]  (default .)
Writes/extends HASHES.txt with sha256 of every file. Never overwrites.
"""
import hashlib, os, sys


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    manifest = os.path.join(root, "HASHES.txt")
    have = set()
    if os.path.exists(manifest):
        have = {l.split()[1] for l in open(manifest) if len(l.split()) > 1}
    added = 0
    with open(manifest, "a") as out:
        for dirpath, _, files in os.walk(root):
            for f in sorted(files):
                if f == "HASHES.txt":
                    continue
                p = os.path.join(dirpath, f)
                rel = os.path.relpath(p, root)
                if rel in have:
                    continue
                h = hashlib.sha256(open(p, "rb").read()).hexdigest()
                out.write(f"{h}  {rel}\n")
                added += 1
    print(f"manifest: {added} new entries appended -> {manifest}")
    print("append-only: existing entries never rewritten")


if __name__ == "__main__":
    sys.exit(main())
