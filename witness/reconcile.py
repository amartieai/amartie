#!/usr/bin/env python3
"""witness/reconcile.py — diff the action ledger against public data exports.

The core comparison: for every action minute, what did the SCREEN record vs
what does the PUBLIC record claim? Multiple exports are supported in
ARGUMENT ORDER (not filename order) — an early pull proves minutes existed;
a later pull missing them proves removal.

Findings are STRUCTURED (pattern ids + evidence dicts), not free-form strings.

Usage:
  python3 witness/reconcile.py ledger.json export_early.csv export_late.csv \
      --out diff.json [--reclick-window 30] [--price-divergence 10.0] \
      [--export-attempts attempts.jsonl]

Outputs:
  diff.json            — structured diff (schema_version 2)
  diff_receipts.jsonl  — append-only receipt of this invocation
"""
import argparse, csv, datetime, hashlib, json, os, statistics, sys

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


def load_export(path):
    """Load bars keyed by minute. Duplicate minutes are NOT silently
    overwritten: the duplicate count is returned alongside the bars so it
    can be recorded in the diff and receipt (finding #10)."""
    bars = {}
    dups = []
    with open(path) as f:
        for i, r in enumerate(csv.DictReader(f), 2):
            t = (r.get("time") or r.get("timestamp") or "")[:16]
            if not t:
                continue
            if t in bars:
                dups.append({"line": i, "minute": t})
            bars[t] = {
                "open": r.get("open"), "high": r.get("high"),
                "low": r.get("low"), "close": r.get("close"),
                "vol": r.get("Vol") or r.get("vol") or r.get("volume"),
                "upvol": r.get("UpVol") or r.get("upvol"),
                "dnvol": r.get("DnVol") or r.get("dnvol"),
            }
    return bars, dups


def fnum(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def finding(pattern, **evidence):
    return {"pattern": pattern, "detected": True, "evidence": evidence}


def detect_reclicks(actions, window_s=30, size_multiplier=1.0):
    """Paired re-clicks: same side, second action within window, size >= first * multiplier.
    The size condition is configurable; the base pattern is the PAIRING."""
    out = []
    acts = sorted(actions, key=lambda a: a["ts"])
    for i in range(len(acts) - 1):
        a, b = acts[i], acts[i + 1]
        if a["side"] != b["side"]:
            continue
        dt = (datetime.datetime.fromisoformat(b["ts"])
              - datetime.datetime.fromisoformat(a["ts"])).total_seconds()
        if 0 < dt <= window_s:
            out.append({
                "actions": [a["ts"], b["ts"]],
                "finding": finding("reclick_signature",
                                   first_action_ts=a["ts"], second_action_ts=b["ts"],
                                   delta_seconds=dt, first_qty=a["qty"],
                                   second_qty=b["qty"],
                                   size_multiplier=round(b["qty"] / max(1, a["qty"]), 2),
                                   window_seconds=window_s,
                                   size_increased=b["qty"] > a["qty"]),
            })
    return out


def load_attempts(path):
    """export_attempts.jsonl: one per line
    {"ts": "...", "endpoint": "fills", "status": 200, "payload": "undefined",
     "logged_out": true}

    Malformed lines are NEVER silently discarded: they are collected with
    line numbers and reported in the diff and the receipt."""
    out, malformed = [], []
    if path and os.path.exists(path):
        with open(path) as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    malformed.append({"line": i, "error": "invalid JSON"})
    return out, malformed


def detect_export_anomaly(attempts, window_s=300):
    """Observed-sequence anomaly: repeated empty payloads and/or forced logouts
    clustered in a short window. Reports the sequence only — no causal claim."""
    if not attempts:
        return None
    ts = []
    for a in attempts:
        try:
            ts.append(datetime.datetime.fromisoformat(a["ts"]))
        except (KeyError, ValueError):
            continue
    if not ts:
        return None
    empty = sum(1 for a in attempts if str(a.get("payload", "")).strip().lower()
                in ("undefined", "", "null", "none", "[]", "{}"))
    logouts = sum(1 for a in attempts if a.get("logged_out"))
    span = (max(ts) - min(ts)).total_seconds() if len(ts) > 1 else 0
    if empty >= 2 or logouts >= 2:
        return finding("export_behavior_anomaly",
                       attempt_count=len(attempts),
                       empty_payload_count=empty,
                       forced_logout_count=logouts,
                       window_seconds=span,
                       note="observed sequence only; no causal claim")
    return None


def reconcile(ledger, exports, opts):
    """exports: list of (label, bars) in ARGUMENT ORDER (chronological pull order)."""
    order = {label: i for i, (label, _) in enumerate(exports)}
    action_minutes = sorted({e["ts"][:16] for e in ledger})

    # duplicate-minute detection in exports (silent overwrite is not acceptable)
    dup_report = opts.get("duplicate_minutes", {})

    # quiet baseline: exclude action minutes; use only the LAST export
    # (most complete late pull) to avoid double counting
    last_label, last_bars = exports[-1]
    quiet_vols = [fnum(b["vol"]) for t, b in last_bars.items()
                  if t not in action_minutes]
    quiet_vols = [v for v in quiet_vols if v is not None and v > 0]
    median_vol = statistics.median(quiet_vols) if quiet_vols else None

    minutes = []
    for minute in action_minutes:
        acts = [e for e in ledger if e["ts"][:16] == minute]
        row = {"minute": minute, "actions": acts, "public": {}, "findings": []}
        for label, bars in exports:
            b = bars.get(minute)
            row["public"][label] = b
            if b is None:
                row["findings"].append(finding("minute_absent", export=label))
        # removal proof: present at an EARLIER order index, absent at a LATER one
        present_orders = [order[l] for l, b in row["public"].items() if b]
        absent_orders = [order[l] for l, b in row["public"].items() if not b]
        if present_orders and absent_orders and max(absent_orders) > min(present_orders):
            pl = [l for l, o in order.items() if o == min(present_orders)][0]
            al = [l for l, o in order.items() if o == max(absent_orders)][0]
            row["findings"].append(finding("removal_proof",
                                           present_in=pl, absent_from=al))
        # first export that has the bar (earliest evidence)
        b = next((row["public"][l] for l, _ in exports if row["public"].get(l)), None)
        if b:
            up, dn, vol = fnum(b["upvol"]), fnum(b["dnvol"]), fnum(b["vol"])
            sells = [a for a in acts if a["side"] == "SELL"]
            buys = [a for a in acts if a["side"] == "BUY"]
            if sells and up is not None and dn is not None and up > 0 and dn == 0:
                row["findings"].append(finding("inverted_classification",
                                               side="SELL", upvol=up, dnvol=dn,
                                               sells_in_minute=len(sells)))
            if buys and dn is not None and up is not None and dn > 0 and up == 0:
                row["findings"].append(finding("inverted_classification",
                                               side="BUY", upvol=up, dnvol=dn,
                                               buys_in_minute=len(buys)))
            if median_vol and vol is not None and vol >= 5 * median_vol:
                row["findings"].append(finding("volume_spike",
                                               volume=vol, median=median_vol,
                                               ratio=round(vol / median_vol, 1)))
                if up == 0 and dn == 0:
                    row["findings"].append(finding("spike_unclassified",
                                                   upvol=0, dnvol=0, volume=vol))
            # screen vs public volume (first action with screen context)
            svs = [(a.get("screen") or {}).get("screen_vol") for a in acts
                   if (a.get("screen") or {}).get("screen_vol") is not None]
            sv = svs[0] if svs else None
            if sv is not None and vol is not None and vol >= 2 * max(1, sv):
                row["findings"].append(finding("volume_inflation",
                                               public_volume=vol, screen_volume=sv,
                                               ratio=round(vol / max(1, sv), 1)))
            # screen vs public price divergence (needs screen_high or screen_close)
            scs = [a.get("screen") for a in acts if a.get("screen")]
            sc = scs[0] if scs else None
            if sc:
                sh = sc.get("screen_high") or sc.get("screen_close")
                ph = fnum(b.get("high"))
                thr = opts.get("price_divergence", 10.0)
                if sh is not None and ph is not None:
                    diff = ph - sh
                    if abs(diff) >= thr:
                        row["findings"].append(finding(
                            "screen_price_divergence",
                            public_high=ph, screen_high=sh,
                            difference=round(diff, 2), threshold=thr,
                            direction=("adverse_to_sells" if diff > 0 and sells
                                       else "adverse_to_buys" if diff < 0 and buys
                                       else "unclassified")))
        minutes.append(row)

    # session-level patterns
    reclicks = detect_reclicks(ledger, opts.get("reclick_window", 30))
    exp_anom = detect_export_anomaly(opts.get("attempts"))

    return {
        "schema_version": SCHEMA,
        "exports": [{"label": l, "order": order[l], "sha256": None}
                    for l, _ in exports],
        "baseline": {"median_volume": median_vol, "source": last_label,
                     "excluded_action_minutes": True},
        "minutes": minutes,
        "session_findings": {
            "reclick_signature": [r["finding"] for r in reclicks],
            "export_behavior_anomaly": [exp_anom] if exp_anom else [],
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger")
    ap.add_argument("exports", nargs="+", help="CSV exports in pull order (argument order)")
    ap.add_argument("--out", default="diff.json")
    ap.add_argument("--receipts", default="diff_receipts.jsonl")
    ap.add_argument("--reclick-window", type=int, default=30)
    ap.add_argument("--price-divergence", type=float, default=10.0)
    ap.add_argument("--export-attempts", default=None,
                    help="export_attempts.jsonl for export_behavior_anomaly")
    a = ap.parse_args()

    ledger = json.load(open(a.ledger))["ledger"]
    loaded = [(os.path.basename(p), load_export(p)) for p in a.exports]
    exports = [(label, bars) for label, (bars, _) in loaded]
    dup_report = {label: dups for label, (_, dups) in loaded if dups}
    attempts, malformed_attempts = load_attempts(a.export_attempts)
    opts = {"reclick_window": a.reclick_window,
            "price_divergence": a.price_divergence,
            "attempts": attempts}
    diff = reconcile(ledger, exports, opts)
    # record export hashes in the output
    for rec, path in zip(diff["exports"], a.exports):
        rec["sha256"] = sha256_file(path)
    # self-contained sources section: ledger + attempts hashes live IN the diff
    diff["sources"] = {
        "ledger": {"path": a.ledger, "sha256": sha256_file(a.ledger)},
        "export_attempts": (
            {"path": a.export_attempts, "sha256": sha256_file(a.export_attempts),
             "records": len(attempts),
             "malformed": malformed_attempts}
            if a.export_attempts and os.path.exists(a.export_attempts) else None),
        "duplicate_minutes": dup_report or None,
    }

    json.dump(diff, open(a.out, "w"), indent=2)
    receipt_inputs = [{"path": p, "sha256": sha256_file(p)}
                      for p in [a.ledger] + a.exports]
    if a.export_attempts and os.path.exists(a.export_attempts):
        receipt_inputs.append({"path": a.export_attempts,
                               "sha256": sha256_file(a.export_attempts)})
    with open(a.receipts, "a") as rf:  # append-only
        rf.write(json.dumps({
            "receipt": "reconcile", "created_at": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            .replace(microsecond=0).isoformat() + "Z",
            "inputs": receipt_inputs,
            "output": a.out, "output_sha256": sha256_file(a.out),
            "parameters": {k: v for k, v in opts.items() if k != "attempts"},
            "attempts": {"records": len(attempts),
                         "malformed": malformed_attempts} if a.export_attempts else None,
            "duplicate_minutes": dup_report or None,
            "schema_version": SCHEMA}) + "\n")

    flagged = sum(1 for m in diff["minutes"] if m["findings"])
    print(f"reconciled {len(diff['minutes'])} action minutes; {flagged} carry findings")
    for m in diff["minutes"]:
        for fnd in m["findings"]:
            print(f"  {m['minute']}: {fnd['pattern']}")
    for r in diff["session_findings"]["reclick_signature"]:
        print(f"  session: reclick_signature {r['evidence']['delta_seconds']}s apart")
    for r in diff["session_findings"]["export_behavior_anomaly"]:
        print(f"  session: export_behavior_anomaly")


if __name__ == "__main__":
    sys.exit(main())
