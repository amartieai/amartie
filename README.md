# TAPE-WITNESS — anonymous click-anomaly detector

Prove what your own screen recorded vs what the public record claims, at the
minutes YOU acted. No strategy, no predictions, no identifying data. The tool
is a ruler, not a trader.

## The anomaly patterns it grades

On a dead, boring, barely-moving asset — overnight micro futures, median
volume single digits per minute — the following cluster ONLY at the
operator's own action minutes, never in the surrounding quiet hours:

1. `inverted_classification` — market sells printing as up-volume
   (UpVol > 0, DnVol = 0 at proven sell minutes).
2. `volume_inflation` — public volume 2x+ the locally recorded screen
   volume at the same minute.
3. `volume_spike` / `spike_unclassified` — 5x+ quiet-median volume bars,
   with classification columns zeroed (UpVol 0 / DnVol 0) at execution
   minutes.
4. `reclick_signature` — paired re-clicks inside a short window (default
   30s), size change recorded but not required for the pairing.
5. `removal_proof` / `minute_absent` — bars present in early data pulls,
   absent from later pulls of the same feed (exports compared in ARGUMENT
   order, not filename order).
6. `screen_price_divergence` — the public print claims highs beyond the
   screen's recorded range by a configurable threshold. Direction is
   classified only when the action side is known.
7. `export_behavior_anomaly` — repeated empty payloads and/or forced
   logouts in the account's own export attempts (observed sequence only;
   no causal claim).

None of these alone proves intent. The tool's claim is narrower and harder:
the anomaly is CONDITIONAL ON ACTION. Quiet minutes — thousands of them —
show none of it. That asymmetry is measurable, reproducible, and it is the
whole point.

## What you need

- A continuous screen recording of your trading session (OBS or equivalent)
- Data exports of the same instrument pulled at multiple times (early pull
  = proof of existence; later pull = proof of absence)
- This repo's tools

## The pipeline

```
# 1. Extract timestamped frames from your recording
python3 witness/frames.py session.mkv --out frames/ --every 20 \
    --start-time 2026-01-05T01:58:43

# 2. Log your executions (from broker toasts visible in the recording)
#    clicks.txt: one per line  "2026-01-05T01:59:52 SELL 1 @ 105.37"
python3 witness/ledger.py frames/ clicks.txt --start 01:58:43 --interval 20 \
    --out ledger.json

# 3. Reconcile against the public export(s) — ARGUMENT ORDER = pull order
python3 witness/reconcile.py ledger.json export_early.csv export_late.csv \
    --out diff.json --export-attempts attempts.jsonl

# 4. Grade the anomaly (baseline = the most complete late export)
python3 witness/grade.py diff.json --export export_late.csv --out verdict.json
```

Every step appends a JSONL receipt — never overwritten:
- frames.py: recording SHA-256, extraction parameters, per-frame hashes
- ledger.py: invocation receipt (clicks hash, frames.jsonl hash, every
  referenced frame's hash, --start/--interval, output hash) + one receipt
  per action
- reconcile.py: hashes of ledger, every export, and the export-attempts
  file; the diff itself carries a self-contained `sources` section
- grade.py: hashes of the diff and the baseline export

The hash manifest (`python3 witness/hash.py .`) is an append-only
OBSERVATION HISTORY: a changed file gets a new dated line, so tampering
and edits are both visible. It is a LOCAL observation log, not proof the
log itself was not altered — for stronger custody, copy or sign the final
manifest to an independent location.

Receipts and HASHES.txt are deliberately gitignored so private evidence
never lands in a public repo by accident. To archive a session's custody
records, bundle them yourself: the receipts, HASHES.txt, frames.jsonl,
ledger, diff, and verdict.

## Tests

```
python3 -m unittest discover -s tests -v
```

12 tests lock down reconciliation (argument-order removal proof, minute
aggregation, no-false-positive screen matching), grading (structured
pattern IDs, actions vs minutes, unsupported patterns never counted),
hashing (idempotent, changed-file observations, correct SHA-256), and the
full E2E pipeline against `examples/`. CI runs them on every push.

## Anonymity law (read before publishing anything)

- Screenshots you publish must show ONLY the plain trading chart of the
  public platform. NEVER your prediction layers, overlays, drawings, or
  any second chart — your method is your own.
- Strip metadata from every image and video you share.
- Refer to the operator in third person ("the operator", "user A").
- The example data in `examples/` is fully synthetic — numbers that
  reproduce the pattern shapes without being anyone's real session.

## What this repo is NOT

- Not a trading strategy, signal service, or prediction tool
- Not an accusation against any named platform — it is a measurement tool
  and a reproducible method
- Not legal advice

## License

MIT. Measure everything. Keep your own records append-only. They can erase
their logs; they cannot erase yours.
