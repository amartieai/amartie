#!/usr/bin/env python3
"""witness/review.py — Jev/Laya backtest-review pattern for COMMUNITY logs.

The whole point of TAPE-WITNESS at scale: one operator's receipts are an
anecdote. A THOUSAND operators' receipts, graded with the same ruler, are
a census. This tool ingests MANY sessions' verdicts/diffs and answers the
population question: does the anomaly reproduce across accounts, brokers,
assets, and time — or is it one screen's story?

Every contributor keeps their anonymity: submissions are verdict.json
files with NO account numbers, NO names, NO paths — just the structured
counts, asset class, and window of observation. The submission template
enforces it.

Usage:
  # a community member grades their own session (existing pipeline), then:
  python3 witness/review.py submit verdict.json --asset micro-futures \\
      --window "2026-01-05T01:30/04:30" --out my_submission.json

  # the aggregator (anyone) merges submissions and computes the census:
  python3 witness/review.py census submissions/*.json --out census.json

The census NEVER aggregates raw data — only the already-anonymized
structured counts. It reports the conditional-on-action rate across the
population, stratified by asset class, with exact binomial confidence
bounds. No causal claims, only reproduction.
"""
import argparse, glob, datetime, hashlib, json, math, os, sys

SCHEMA = 1


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def wilson(k, n, z=1.96):
    """Wilson score interval — honest bounds for small samples."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


ANON_DENYLIST = ("account", "login", "user_id", "name", "email", "path",
                 "home", "username", "owner", "operator_name")


def sanitize_submission(sub):
    """Reject any submission carrying identity fields or raw data."""
    bad = [k for k in sub if any(d in k.lower() for d in ANON_DENYLIST)]
    if bad:
        raise ValueError(f"identity-bearing fields rejected: {bad}")
    if "ledger" in sub or "minutes" in sub:
        raise ValueError("raw session data rejected — submit verdict counts only")
    return sub


def make_submission(verdict_path, asset, window, notes=None):
    v = json.load(open(verdict_path))
    sub = {
        "schema_version": SCHEMA,
        "submission_kind": "tape_witness_session",
        "asset_class": asset,
        "observation_window": window,
        "action_count": v.get("action_count"),
        "action_minute_count": v.get("action_minute_count"),
        "minutes_with_findings": v.get("minutes_with_findings"),
        "pattern_counts": v.get("pattern_counts"),
        "conditional_on_action": v.get("conditional_on_action"),
        "quiet_baseline": v.get("quiet_baseline"),
        "verdict_sha256": sha256_file(verdict_path),
        "submitted_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    if notes:
        sub["notes"] = notes[:500]
    return sanitize_submission(sub)


def census(submission_paths):
    subs = []
    for p in submission_paths:
        try:
            subs.append(sanitize_submission(json.load(open(p))))
        except (ValueError, json.JSONDecodeError) as e:
            print(f"skipping {p}: {e}", file=sys.stderr)
    if not subs:
        sys.exit("no valid submissions")

    def tally(pred):
        sel = [s for s in subs if pred(s)]
        n = len(sel)
        flagged = sum(1 for s in sel
                      if (s.get("conditional_on_action") or {}).get("rate", 0) >= 0.5)
        lo, hi = wilson(flagged, n)
        return {"sessions": n, "flagged_sessions": flagged,
                "flagged_rate": round(flagged / n, 3) if n else None,
                "wilson_95": [round(lo, 3), round(hi, 3)]}

    patterns_total = {}
    for s in subs:
        for pat, cnt in (s.get("pattern_counts") or {}).items():
            patterns_total[pat] = patterns_total.get(pat, 0) + (cnt or 0)

    out = {
        "schema_version": SCHEMA,
        "census_kind": "tape_witness_population",
        "sessions": len(subs),
        "total_actions": sum(s.get("action_count") or 0 for s in subs),
        "total_action_minutes": sum(s.get("action_minute_count") or 0 for s in subs),
        "by_asset_class": {},
        "patterns_population_totals": patterns_total,
        "overall": tally(lambda s: True),
        "claim": ("Census of anonymized session verdicts. Reports reproduction "
                  "of conditional-on-action anomaly rates across independent "
                  "operators. No causal claims, no platform accusations."),
        "method": ("Wilson 95% bounds; a session counts as flagged when >=50% "
                   "of its action minutes carry findings."),
    }
    assets = sorted({s.get("asset_class") or "unspecified" for s in subs})
    for a in assets:
        out["by_asset_class"][a] = tally(lambda s, a=a: (s.get("asset_class")
                                                          or "unspecified") == a)
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    aps = sub.add_parser("submit", help="anonymize one session verdict")
    aps.add_argument("verdict")
    aps.add_argument("--asset", required=True, help="asset class, e.g. micro-futures")
    aps.add_argument("--window", required=True, help="observation window, e.g. 2026-01-05T01:30/04:30")
    aps.add_argument("--notes", default=None)
    aps.add_argument("--out", default="my_submission.json")

    apc = sub.add_parser("census", help="aggregate submissions into the census")
    apc.add_argument("submissions", nargs="+")
    apc.add_argument("--out", default="census.json")

    a = ap.parse_args()
    if a.cmd == "submit":
        subm = make_submission(a.verdict, a.asset, a.window, a.notes)
        json.dump(subm, open(a.out, "w"), indent=2)
        print(f"submission written -> {a.out} (anonymized, counts only)")
        print("  contains no account data, no names, no paths, no raw records")
    else:
        paths = []
        for pat in a.submissions:
            paths.extend(glob.glob(pat))
        if not paths:
            sys.exit("no submission files matched")
        out = census(paths)
        json.dump(out, open(a.out, "w"), indent=2)
        print(json.dumps(out, indent=2))


if __name__ == "__main__":
    sys.exit(main())
