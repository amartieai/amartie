# AMARTIE architecture

Version 0.1.0. This is a map of the code that exists in `amartie/` and `plugins/`, not a future design.

## One-sentence model

An owner-facing studio proposes an action; the 9-judge gate either writes a passing receipt and lets the action leave, or writes a failing receipt and refuses.

## Package layout

```
amartie/
  __init__.py          public exports, version
  gate.py              JudgeVerdict, GateReceipt, JudgeGate
  receipt.py           Receipt, ReceiptChain (standalone ledger)
  sandbox.py           Snapshot, Sandbox
  vault.py             Vault, AntiTamper
  plugin_system.py     manifest load, render/handle
  server.py            localhost cockpit HTTP server
  forensic_engine.py   session-log substitution audit
  swap_detector.py     quality-fingerprint swap verdict
  session_swap_detector.py
  judge_panel.py / judge_panel_v2.py
  backend.py / driver.py
  research_crew.py / swarm.py
plugins/
  <studio>/manifest.json
  <studio>/__init__.py
tests/
  test_gate.py test_receipt.py test_sandbox.py test_vault.py
```

`pyproject.toml` names the package `amartie`, Python ≥ 3.9, MIT.

## Gate

`JudgeGate` in `amartie/gate.py` is the policy kernel.

Canonical roster:

```
J1 TRUTH
J2 BOUNDARY-INTEGRITY
J3 LOGIC
J4 COMPLETENESS
J5 EXECUTION-AND-SIMPLICITY
J6 OWNER-INTENT
J7 RECOVERY
J8 TRADE-INTEGRITY
J9 UNITY
```

`verify_action(action_type, payload, judge_responses)`:

1. SHA-256 the sorted JSON payload.
2. Require every verdict `== "PASS"`.
3. Require each verdict `model_id` to match the seat assignment (Braid / model-lock).
4. Require each verdict to include at least two `tool_calls` (evidence floor).
5. Build a `GateReceipt` linked to the previous hash or `GENESIS`.
6. Append the receipt hash to `receipt_chain`.
7. Return `(passed, receipt)`.

Budgets currently stored on the gate object: 1200s per judge, 900s gate-wide, `round_cap = 4`. Daily rotating physical IDs come from `sha256(date + logical_id)`.

A dissent does not delete evidence. The receipt is the evidence that the action was refused.

## Receipts

Two layers exist on purpose:

- `GateReceipt` — produced by the gate, carries verdicts
- `Receipt` / `ReceiptChain` in `receipt.py` — general hash-chained ledger

Both hash sorted JSON. `verify()` recomputes. Breaking one field breaks the hash. Breaking the link between receipts breaks the chain.

v0.1 stores the gate chain in memory. Persistent replay is a Now item on the [roadmap](../ROADMAP.md).

## Plugins

`PluginManager.discover()` scans `plugins/*/manifest.json`.

Required manifest fields: `name`, `version`, `entrypoint`, `permissions`.

Optional: `api_endpoints`, `studio_type`, `platforms`.

A plugin module exposes:

- `render(**kwargs)` → UI
- `handle(action, data)` → result dict

The cockpit activates one studio at a time. Outbound side effects are supposed to call the gate before they leave. Permission strings in the manifest are the declared surface; OS enforcement is still incomplete (see SECURITY.md).

Twelve studios ship in-tree, including Jarvis, Voice, Free Providers, Suno, Luma, Runway, Leonardo, ElevenLabs, CAD, Storytelling, Video Edit, and Game Dev.

## Sandbox

`Snapshot` captures a baseline (kernel hash, filesystem hash, processes, listeners). `Sandbox` contains a run, snapshots again on exit, diffs, and flags unknowns for quarantine. Some listings are sampled. Treat it as change detection, not a proven jail.

## Vault

`Vault` stores named blobs under `~/.amartie/vault` (default). Access is keyed by `key_hash` and logged. `AntiTamper` registers file hashes and alerts on mismatch. Production public-key encryption is stubbed — do not store real secrets in the current vault expecting confidentiality.

## Forensics

Two tools sit *beside* the gate, not inside it:

- `forensic_engine.py` — directory of session JSON → identity conflicts, model changes, quality drops, hashed report
- `swap_detector.py` — scores a session on length / structure / coherence / tool use / reasoning and emits a swap verdict receipt

These detect silent substitution in logs you already have. They do not stop a provider from swapping.

## Server

```bash
python3 amartie/server.py [port]    # default 8715
```

Local endpoints include `/api/health`, `/api/providers`, `/api/chat`, `/api/jarvis`, and generation routes for speech, music, image, and video. Cockpit: `http://127.0.0.1:<port>/visuals/cockpit.html`.

Do not bind this to a public interface.

## Trust flow

```
studio handle()
    → construct payload
    → collect 9 JudgeVerdicts
    → gate.verify_action()
         fail: return receipt, do not call provider
         pass: call provider / tool, keep receipt
    → optional forensic pass on the session log
```

Anything that calls a provider *before* `verify_action` is a bug.

## Tests as specification

`tests/test_gate.py` is the readable spec for unanimous pass, dissent bounce, rubber-stamp rejection, rotation, and receipt tamper detection. If a design doc and a test disagree, the test on `main` wins until the test is deliberately changed in a Defense review.
