# TAPE-WITNESS — anonymous click-anomaly detector

Prove what your own screen recorded vs what the public record claims, at the
minutes YOU acted. No strategy, no predictions, no identifying data. The tool
is a ruler, not a trader.

## The anomaly pattern it grades

On a dead, boring, barely-moving asset — overnight micro futures, median
volume single digits per minute — the following cluster ONLY at the
operator's own action minutes, never in the surrounding quiet hours:

1. INVERTED VOLUME CLASSIFICATION: market sells printing as up-volume
   (UpVol > 0, DnVol = 0 at proven sell minutes).
2. VOLUME INFLATION: public volume 2x+ the locally recorded screen volume
   at the same minute, excess classified in the direction adverse to the
   operator's position.
3. SPIKE-AND-PIN: 5x+ median volume bars with zero price follow-through on
   the local feed, and/or classification columns zeroed (UpVol 0 / DnVol 0)
   exactly at execution minutes.
4. THE 20-SECOND RE-CLICK: adverse flip within seconds of entry, operator
   re-clicks ~20s later at larger size — the frustration ladder, visible
   as paired executions.
5. THE VANISHING MINUTES: bars present in early data pulls, absent from
   later pulls of the same feed — public-record minutes removed after the
   fact, disproportionately covering action minutes.
6. SCREEN-VS-PRINT PRICE DIVERGENCE: the public print claims highs/lows
   double-digit points beyond anything the locally recorded screen showed
   in the same minute, always adverse to the open position.
7. EXPORT BLOCKING: the account's own trade/fill history export returning
   empty payloads ("undefined") with repeated forced logouts clustered
   around the download attempts.

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
# 1. Extract frames from your recording and OCR the tape + volume readouts
python3 witness/frames.py session.mkv --out frames/ --every 20

# 2. Log your executions (from broker toasts visible in the recording)
#    clicks.txt: one per line  "2026-01-05T01:59:52 SELL 1 @ 105.37"
python3 witness/ledger.py frames/ clicks.txt --out ledger.json

# 3. Reconcile against the public export(s)
python3 witness/reconcile.py ledger.json export_early.csv export_late.csv --out diff.json

# 4. Grade the anomaly (all seven patterns, with counts and severity)
python3 witness/grade.py diff.json --out verdict.json
```

Every step writes an append-only JSONL receipt. Hash everything
(`witness/hash.py .`) before showing anyone anything.

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
