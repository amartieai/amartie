# AMARTIE repository instructions

AMARTIE is a Python 3.9+ local-first AI verification framework. Nine judges verify every outbound action. Unanimous PASS or the action bounces.

## Before making changes

1. Read `README.md` for the project positioning and alpha limitations.
2. Read `docs/ARCHITECTURE.md` for the code map and trust flow.
3. Read `SECURITY.md` when handling security, credentials, networking, plugins, vaults, or the gate.
4. Run the smallest relevant tests: `python -m pytest tests/ -q`.
5. Preserve unanimous PASS, model-lock, the evidence floor, fail-closed behavior, and receipt integrity.
6. Never bind the cockpit publicly. Default is 127.0.0.1:8715.
7. Never store secrets in source, logs, receipts, fixtures, or review artifacts.
8. Do not claim alpha functionality is production security.
9. For pull requests, report test failures by exact test name. Distinguish baseline failures from regressions.
10. Open a pull request for code changes. Do not merge automatically.

## The nine judges

| ID | Judge | Question |
|----|-------|----------|
| J1 | TRUTH | Are claims checkable against the live machine? |
| J2 | BOUNDARY-INTEGRITY | Does this stay inside the declared perimeter? |
| J3 | LOGIC | Is the plan internally consistent and ordered? |
| J4 | COMPLETENESS | What critical omission did the others miss? |
| J5 | EXECUTION-AND-SIMPLICITY | Is every step a literal, runnable procedure? |
| J6 | OWNER-INTENT | Does this map to what the owner actually directed? |
| J7 | RECOVERY | Is there a rollback path before anything destructive? |
| J8 | TRADE-INTEGRITY | Is a money or exchange action financially sound? |
| J9 | UNITY | Does the whole machine still hold end to end? |

## Current alpha limitations (v0.1.0)

- Vault public-key encryption is stubbed.
- Receipt chain is in-memory only.
- Sandbox listings are sampled, not complete.
- Plugin permissions are declared in manifest but not OS-enforced.
- Server must remain localhost-only.

If a P0 item lands, update the README in/out table and SECURITY.md in the same change.
