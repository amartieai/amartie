#!/usr/bin/env python3
"""witness/hash.py — append-only hash HISTORY for an evidence directory.

The manifest is a history of observations, not a deduplicated path list:

  <sha256>  <relative-path>  <observed-at-UTC>

Behavior:
  - new path                 -> append an observation
  - unchanged path + hash    -> no new entry (idempotent)
  - changed path (new hash)  -> append a NEW observation (never silent)
  - HASHES.txt itself is never hashed

Running twice with no changes adds zero entries. A modified file always
produces a new dated line, so tampering and legitimate edits are both
visible in the history.

Usage: python3 witness/hash.py [dir]  (default .)
"""
import datetime, hashlib, os, sys


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    manifest = os.path.join(root, "HASHES.txt")
    seen = {}  # path -> latest hash
    if os.path.exists(manifest):
        with open(manifest) as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    seen[parts[1]] = parts[0]

    now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    added = changed = 0
    entries = []
    for dirpath, _, files in os.walk(root):
        for f in sorted(files):
            if f == "HASHES.txt":
                continue
            p = os.path.join(dirpath, f)
            rel = os.path.relpath(p, root)
            h = sha256_file(p)
            if rel not in seen:
                entries.append(f"{h}  {rel}  {now}")
                added += 1
            elif seen[rel] != h:
                entries.append(f"{h}  {rel}  {now}")
                changed += 1
    if entries:
        with open(manifest, "a") as out:
            for e in entries:
                out.write(e + "\n")
    print(f"hash history: {added} new, {changed} changed -> {manifest}")
    print("append-only: prior observations are never rewritten")


if __name__ == "__main__":
    sys.exit(main())
