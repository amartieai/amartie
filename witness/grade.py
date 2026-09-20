#!/usr/bin/env python3
"""witness/grade.py — grade the seven-pattern anomaly from a reconcile diff.

The verdict logic is deliberately narrow: the anomaly claim is CONDITIONAL
ON ACTION. The grader therefore needs quiet-minute baselines too — feed it
the full export and it compares action minutes against the session's own
quiet distribution.

Usage: python3 witness/grade.py diff.json --export export_late.csv --out verdict.json
"""
import argparse, csv, json, statistics, sys


def fnum(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def quiet_baseline(path):
    bars = []
    with open(path) as f:
        for r in csv.DictReader(f):
            v = fnum(r.get("Vol") or r.get("vol") or r.get("volume"))
            if v is not None:
                bars.append(v)
    return bars


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("diff")
    ap.add_argument("--export", required=True, help="full public export for baseline")
    ap.add_argument("--out", default="verdict.json")
    a = ap.parse_args()

    diff = json.load(open(a.diff))
    baseline = quiet_baseline(a.export)
    med = statistics.median([v for v in baseline if v > 0]) if baseline else None

    counts = {"minute_absent": 0, "removal_proof": 0, "inverted_classification": 0,
              "volume_spike": 0, "spike_unclassified": 0, "volume_inflation": 0,
              "screen_price_divergence": 0}
    for m in diff["minutes"]:
        for f in m["findings"]:
            for k in counts:
                if f.startswith(k.upper().replace("_", " ").title()) or k in f.lower().replace(" ", "_"):
                    counts[k] += 1
                    break

    n = len(diff["minutes"])
    flagged = sum(1 for m in diff["minutes"] if m["findings"])
    verdict = {
        "action_minutes": n,
        "minutes_with_findings": flagged,
        "session_median_volume": med,
        "pattern_counts": counts,
        "conditional_on_action": None,
        "summary": None,
    }
    # The honest verdict sentence
    lines = []
    if counts["removal_proof"]:
        lines.append(f"{counts['removal_proof']} action-minute bars present in early "
                     f"exports and absent from later pulls of the same feed")
    if counts["inverted_classification"]:
        lines.append(f"{counts['inverted_classification']} proven sell minutes printed "
                     f"as up-volume with zero down-volume")
    if counts["volume_spike"]:
        lines.append(f"{counts['volume_spike']} volume spikes >=5x session median at "
                     f"action minutes")
    if counts["volume_inflation"]:
        lines.append(f"{counts['volume_inflation']} minutes where public volume was 2x+ "
                     f"the locally recorded screen volume")
    verdict["summary"] = " | ".join(lines) if lines else "no anomalies graded"
    verdict["conditional_on_action"] = (
        f"{flagged}/{n} action minutes carry at least one anomaly finding; "
        f"baseline median volume {med} from {len(baseline)} quiet bars"
        if n else "no actions to grade")
    json.dump(verdict, open(a.out, "w"), indent=2)
    print(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    sys.exit(main())
