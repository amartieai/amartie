#!/usr/bin/env python3
"""witness/grade.py — grade the anomaly patterns from a structured reconcile diff.

The verdict logic is deliberately narrow: the anomaly claim is CONDITIONAL
ON ACTION. Counts are derived from structured pattern ids (schema_version 2
diffs), never from free-form strings. Actions and unique action minutes are
counted separately.

Usage:
  python3 witness/grade.py diff.json --export export_late.csv --out verdict.json

--export is the BASELINE export (the most complete late pull). Quiet-minute
baseline excludes action minutes.
"""
import argparse, csv, datetime, hashlib, json, statistics, sys

SCHEMA = 2
PATTERNS = ("minute_absent", "removal_proof", "inverted_classification",
            "volume_spike", "spike_unclassified", "volume_inflation",
            "reclick_signature", "screen_price_divergence",
            "export_behavior_anomaly")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def fnum(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def quiet_baseline(path, action_minutes):
    """Median volume over NON-action minutes only."""
    vols = []
    with open(path) as f:
        for r in csv.DictReader(f):
            t = (r.get("time") or r.get("timestamp") or "")[:16]
            if t in action_minutes:
                continue
            v = fnum(r.get("Vol") or r.get("vol") or r.get("volume"))
            if v is not None and v > 0:
                vols.append(v)
    return vols


def grade(diff, baseline_vols):
    counts = {p: 0 for p in PATTERNS}
    minutes = diff.get("minutes", [])
    action_minutes = [m["minute"] for m in minutes]
    actions = sum(len(m.get("actions", [])) for m in minutes)

    for m in minutes:
        for fnd in m.get("findings", []):
            p = fnd.get("pattern")
            if p in counts:
                counts[p] += 1
    for p in ("reclick_signature", "export_behavior_anomaly"):
        counts[p] = len(diff.get("session_findings", {}).get(p, []))

    flagged = sum(1 for m in minutes if m.get("findings"))
    med = statistics.median(baseline_vols) if baseline_vols else None

    lines = []
    if counts["removal_proof"]:
        lines.append(f"{counts['removal_proof']} action-minute bars present in early "
                     f"exports and absent from later pulls of the same feed")
    if counts["inverted_classification"]:
        lines.append(f"{counts['inverted_classification']} proven sell minutes printed "
                     f"as up-volume with zero down-volume")
    if counts["volume_spike"]:
        lines.append(f"{counts['volume_spike']} volume spikes >=5x quiet-median at "
                     f"action minutes")
    if counts["spike_unclassified"]:
        lines.append(f"{counts['spike_unclassified']} spikes with zeroed classification")
    if counts["volume_inflation"]:
        lines.append(f"{counts['volume_inflation']} minutes where public volume was 2x+ "
                     f"the locally recorded screen volume")
    if counts["reclick_signature"]:
        lines.append(f"{counts['reclick_signature']} paired re-clicks inside the window")
    if counts["screen_price_divergence"]:
        lines.append(f"{counts['screen_price_divergence']} minutes where the public print "
                     f"exceeded the screen's recorded range by the threshold")
    if counts["export_behavior_anomaly"]:
        lines.append(f"{counts['export_behavior_anomaly']} export-attempt sequences with "
                     f"empty payloads and/or forced logouts (observed sequence only)")

    return {
        "schema_version": SCHEMA,
        "action_count": actions,
        "action_minute_count": len(minutes),
        "minutes_with_findings": flagged,
        "quiet_baseline": {"median_volume": med, "bars": len(baseline_vols),
                           "excluded_action_minutes": True},
        "pattern_counts": counts,
        "conditional_on_action": {
            "flagged_action_minutes": flagged,
            "total_action_minutes": len(minutes),
            "rate": round(flagged / len(minutes), 3) if minutes else None,
        },
        "summary": " | ".join(lines) if lines else "no anomalies graded",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("diff")
    ap.add_argument("--export", required=True,
                    help="baseline public export (quiet minutes are taken from here)")
    ap.add_argument("--out", default="verdict.json")
    ap.add_argument("--receipts", default="grade_receipts.jsonl")
    a = ap.parse_args()

    diff = json.load(open(a.diff))
    action_minutes = {m["minute"] for m in diff.get("minutes", [])}
    baseline_vols = quiet_baseline(a.export, action_minutes)
    verdict = grade(diff, baseline_vols)

    json.dump(verdict, open(a.out, "w"), indent=2)
    with open(a.receipts, "a") as rf:  # append-only
        rf.write(json.dumps({
            "receipt": "grade",
            "created_at": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            .replace(microsecond=0).isoformat() + "Z",
            "inputs": [{"path": p, "sha256": sha256_file(p)}
                       for p in (a.diff, a.export)],
            "output": a.out, "output_sha256": sha256_file(a.out),
            "schema_version": SCHEMA}) + "\n")
    print(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    sys.exit(main())
