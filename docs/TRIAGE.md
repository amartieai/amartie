# Community triage

This repository is an alpha project. Triage should make the next safe contribution obvious, not create a large planning ceremony.

## Labels

Use these labels consistently:

- `P0`, `P1`, `P2` — urgency and release priority
- `R` — research/building new capability
- `D` — defense/hardening existing behavior
- `good first issue` — bounded work with a clear acceptance test
- `help wanted` — maintainer help is welcome
- `documentation`, `plugin`, `security`, `testing`

Priority is not a promise of immediate implementation. A P0 issue protects a core safety or integrity invariant.

## Board columns

Use this order in the project board:

`Triage` → `Now/P0` → `Next/P1` → `Later/P2` → `In progress` → `Review` → `Done`

An issue should have one priority, one work track where applicable, and a concrete acceptance condition before it leaves Triage.

## Weekly 15-minute triage

1. Check new issues and remove duplicates.
2. Confirm the issue has a reproducible goal and acceptance criteria.
3. Verify that security-sensitive work is routed through `SECURITY.md`.
4. Move only the highest-value bounded items into `Now/P0` or `Next/P1`.
5. Check claimed issues and stale work.
6. Add a short progress note to anything in progress.

## Current priority

- P0: [persist and replay `receipt_chain`](https://github.com/amartieai/amartie/issues/5)
- P1: [dry-run plugin](https://github.com/amartieai/amartie/issues/6)
- P1: [Windows install notes](https://github.com/amartieai/amartie/issues/7)
- P1: [self-auditing nine-judge gate](https://github.com/amartieai/amartie/issues/8)

## Definition of ready

An issue is ready when a contributor can identify the files to inspect, the safety invariant to preserve, the test or documentation expected, and what “done” means without guessing.

## Definition of done

A change is done when tests or documentation checks pass, the relevant receipt/security behavior is covered, limitations are documented, and the issue is linked from the pull request.
