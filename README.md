# AMARTIE

> **Receipts, not promises.**
>
> AMARTIE is an open-source, local-first AI action gate: an owner-facing studio proposes an action, nine judges verify it, and the action either produces a receipt and proceeds or produces a dissent receipt and refuses.

## What it is—and is not

AMARTIE is an alpha verification and audit layer for AI tool actions. It verifies before execution, fails closed, model-locks judge seats, enforces an evidence floor, and records hash-linked receipts.

It is **not** a hosted security service, a guarantee that a provider cannot swap a model, a sandbox proven to contain every side effect, or production cryptography for secrets. Vault public-key encryption, persistent receipt replay, and complete OS-level permission enforcement are not finished in v0.1.

## A real use case: Trade Witness

AMARTIE's witness engine, pointed at the trading floor first — an always-on, hash-chained recorder that catches vanishing bars, volume spikes, and fill-time divergence, so any trader can see whether each execution was actually kosher. [Try Trade Witness](https://github.com/amartieai/trade-witness) → its own repo, one-command install.

## Try it

For PowerShell and Command Prompt instructions, including virtual-environment activation and firewall guidance, see the [Windows setup guide](docs/WINDOWS_SETUP.md).

```bash
git clone https://github.com/amartieai/amartie.git
cd amartie
python -m pip install -e .
pytest tests -v
python amartie/server.py 8715
```

Open <http://127.0.0.1:8715/visuals/cockpit.html>. Keep the server bound to localhost; do not expose it publicly.

## Start here

1. Read the [architecture map](docs/ARCHITECTURE.md).
2. Read the [security boundaries](SECURITY.md).
3. Run the tests and try the local cockpit.
4. Choose a labeled issue that matches your level.
5. Comment on it to claim the work, then follow [CONTRIBUTING.md](CONTRIBUTING.md).

## v0.1: in and out

**In:** gate protocol, nine-judge verification, unanimous PASS, seat-locked model assignments, evidence floor, dissent receipts, hash calculation, forensic audit tools, local cockpit, and tests.

**Not yet in:** durable receipt-chain replay, production vault encryption, complete permission enforcement, a proven jail, hosted money or mail actions, or a public-bind deployment model.

If a P0 item lands, update this table and the security documentation in the same change.

## Current community priorities

- **P0 — [Persist and replay `receipt_chain`](https://github.com/amartieai/amartie/issues/5)**
- **P1 — [Build the dry-run example plugin](https://github.com/amartieai/amartie/issues/6)**
- **P1 — [Document Windows installation](https://github.com/amartieai/amartie/issues/7)**
- **P1 — [Self-auditing nine-judge gate](https://github.com/amartieai/amartie/issues/8)**

## Contributor ladder

- **Docs:** Windows setup, examples, architecture clarifications.
- **Plugins:** safe, no-network studios and test fixtures.
- **Gate and receipts:** contracts, roster validation, evidence, replay, and fail-closed behavior.
- **Security review:** threat modeling, tamper tests, policy review, and independent audit.

See the [triage process](docs/TRIAGE.md) and [30-day plan](docs/30_DAY_PLAN.md) for how work is prioritized.

## The nine-judge contract

Every outbound action must pass all nine seats. One dissent refuses the action and preserves the receipt as evidence. There is no majority override and no hidden judge swap.

The current roster is documented in [ARCHITECTURE.md](docs/ARCHITECTURE.md). Tests are the executable specification for unanimous pass, dissent bounce, evidence requirements, model-lock, and receipt tamper detection.

## Status

AMARTIE is **v0.1.0 alpha**. Audit the implementation, reproduce the tests, and treat the documented limitations as real. Do not put real secrets in the current vault or bind the cockpit to a public interface.

MIT licensed. Contributions and security reviews are welcome.
