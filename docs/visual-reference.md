# Visual Reference

This document explains how to read AMARTIE's visual documentation.

## Status Labels

Every diagram begins with one of these labels:

| Label | Meaning |
|-------|---------|
| **IMPLEMENTED IN ALPHA** | This feature exists in v0.1 and is tested |
| **DEMO / SIMULATION** | This is a demonstration, not a security guarantee |
| **PROPOSED FUTURE ARCHITECTURE** | This is planned but not yet implemented |

## Color Legend

| Color | Meaning |
|-------|---------|
| **BLUE** | User or plugin input |
| **GOLD** | AMARTIE validation/control |
| **GREEN** | Unanimous approval |
| **RED** | Dissent, rejection, or quarantine |
| **PURPLE** | Audit, replay, or evidence |
| **GRAY** | Future capability (not in v0.1) |

## Arrow Styles

| Style | Meaning |
|-------|---------|
| **Solid arrow** | Implemented data path |
| **Dashed arrow** | Proposed/future path |
| **Lock icon** | Enforced boundary |
| **Document icon** | Receipt or evidence artifact |

## Diagram Files

| File | Description |
|------|-------------|
| `docs/diagrams/system-overview.md` | High-level system architecture |
| `docs/diagrams/action-gate-flow.md` | How actions pass through the gate |
| `docs/diagrams/receipt-lifecycle.md` | How receipts are created and verified |
| `docs/diagrams/plugin-boundary.md` | How plugins are contained |
| `docs/diagrams/public-contribution-flow.md` | How to contribute |

## HALO Visualization vs Security Evidence

| HALO Visualization | AMARTIE Security Evidence |
|--------------------|---------------------------|
| A conceptual interface for attention, state, and system relationships | Code, tests, receipts, hashes, replay results, and documented enforcement boundaries |
| Artistic representation of the 3-6-9 toroidal field | Actual judge roster (J1-J9) with contract validation |
| Visual metaphor for system health | Actual receipt hashes and chain integrity checks |
| Simulated node severance animation | Actual dissent receipts with `executed: false` |

**The visualization is not proof of security.** Only the code, tests, and receipts are.

## Accessible Text Equivalents

Every Mermaid diagram includes an accessible text block beneath it. This ensures the information is available to screen readers and text-only browsers.
