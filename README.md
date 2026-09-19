# AMARTIE

AMARTIE is a forensic engine that proves whether an AI provider silently swapped the model you were billed for. It reads session dumps, compares the billed model to the returned model, and writes a hash-chained receipt a stranger can replay.

## Trust model

No trust required. Clone the repo, run the verifier, and verify the receipt hash against the original session dump.

## Install

```bash
python3 -m pip install -e .
amartie check fixtures/fail.json
```

## CLI

```bash
amartie check session.json
amartie probe https://example.com/v1/chat/completions --model moonshotai/kimi-k3
amartie replay session.json receipts/2026-09-18T20:01:00Z.json
```

## Stability Promise

The receipt schema is frozen at v1.0.

- Breaking changes require a new major version
- Receipts generated under v1.0 continue to verify forever
- New fields may be added only in a new schema version

## Architecture

1. Ingest — reads the session dump
2. Detect — compares billed vs returned model, intent-aware
3. Receipt — writes a content-addressed hash-chained JSON receipt
4. Custody — append-only chain of actions
5. Replay — recomputes and compares against the stored receipt
6. Probes — identity, capability, billing checks
7. Gate — eBPF egress monitor and bypass blocking

## Why it matters

Providers can bill for premium models and silently route to cheaper ones. The engine provides provenance, transparency, and a public, replayable audit trail.
