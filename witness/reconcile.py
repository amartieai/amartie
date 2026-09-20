#!/usr/bin/env python3
"""witness/reconcile.py — diff the action ledger against public data exports.

The core comparison: for every action minute, what did the SCREEN record vs
what does the PUBLIC record claim? Multiple exports are supported — an early
pull proves minutes existed; a later pull missing them proves removal.

Usage:
  python3 witness/reconcile.py ledger.json export_early.csv export_late.csv --out diff.json
"""
import argparse, csv, json, statistics, sys


def load_export(path):
    bars = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            t = (r.get("time") or r.get("timestamp") or "")[:16]
            if not t:
                continue
            bars[t] = {
                "open": r.get("open"), "high": r.get("high"),
                "low": r.get("low"), "close": r.get("close"),
                "vol": r.get("Vol") or r.get("vol") or r.get("volume"),
                "upvol": r.get("UpVol") or r.get("upvol"),
                "dnvol": r.get("DnVol") or r.get("dnvol"),
            }
    return bars


def fnum(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def reconcile(ledger, exports):
    """exports: list of (label, bars) pulled in chronological order."""
    vols = [fnum(b["vol"]) for _, bars in exports for b in bars.values()]
    vols = [v for v in vols if v is not None and v > 0]
    median_vol = statistics.median(vols) if vols else None

    out = []
    for e in ledger:
        minute = e["ts"][:16]
        row = {"action": e, "minute": minute, "public": {}, "findings": []}
        for label, bars in exports:
            b = bars.get(minute)
            row["public"][label] = b
            if b is None:
                row["findings"].append(f"MINUTE ABSENT from {label} export")
        # earliest export that has it vs later that doesn't = removal proof
        labels = [label for label, bars in exports]
        present = [label for label in labels if row["public"].get(label)]
        absent = [label for label in labels if not row["public"].get(label)]
        if present and absent and absent > present:
            row["findings"].append(
                f"REMOVAL: present in {present[0]}, absent from {absent[-1]}")
        # volume classification at proven sell minutes
        b = next((row["public"][l] for l in labels if row["public"].get(l)), None)
        if b and e.get("side") == "SELL":
            up, dn = fnum(b["upvol"]), fnum(b["dnvol"])
            if up is not None and dn is not None and up > 0 and dn == 0:
                row["findings"].append(
                    f"INVERTED CLASSIFICATION: SELL printed with UpVol {up} / DnVol 0")
        if b and median_vol and fnum(b["vol"]) and fnum(b["vol"]) >= 5 * median_vol:
            row["findings"].append(
                f"VOLUME SPIKE: {fnum(b['vol'])} vs median {median_vol}")
            if fnum(b["upvol"]) == 0 and fnum(b["dnvol"]) == 0:
                row["findings"].append("SPIKE UNCLASSIFIED: UpVol 0 / DnVol 0")
        # screen vs public volume
        sv = (e.get("screen") or {}).get("screen_vol")
        pv = fnum(b["vol"]) if b else None
        if sv is not None and pv is not None and pv >= 2 * max(1, sv):
            row["findings"].append(
                f"VOLUME INFLATION: public {pv} vs screen {sv} ({pv/max(1,sv):.1f}x)")
        out.append(row)
    return {"median_vol": median_vol, "minutes": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger")
    ap.add_argument("exports", nargs="+", help="CSV exports in pull order")
    ap.add_argument("--out", default="diff.json")
    a = ap.parse_args()
    ledger = json.load(open(a.ledger))["ledger"]
    exports = [(os.path.basename(p), load_export(p)) for p in a.exports]
    diff = reconcile(ledger, exports)
    json.dump(diff, open(a.out, "w"), indent=2)
    flagged = sum(1 for m in diff["minutes"] if m["findings"])
    print(f"reconciled {len(diff['minutes'])} action minutes; {flagged} carry findings")
    for m in diff["minutes"]:
        if m["findings"]:
            print(f"  {m['minute']}: " + "; ".join(m["findings"]))


if __name__ == "__main__":
    import os
    sys.exit(main())
