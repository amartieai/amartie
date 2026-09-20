# Handoff Brief: AMARTIE Foundation Repair

You are taking over the AMARTIE repository.

Repository: https://github.com/amartieai/amartie

Working branch: foundation/receipts-gate-public-audit

Do NOT work directly on main.
Do NOT force-push.
Do NOT delete existing work.
Do NOT silently alter safety invariants.

Create a separate branch from: foundation/receipts-gate-public-audit

## Existing Foundation Commits

```
cccdd74  Implement canonical judge contract, strict unanimous gate verification, and durable receipt persistence
21cd020  Strengthen the receipt engine with versioned hashing and chain validation
db9bce9  Add receipt regression tests for hash versioning and tamper detection
92fa6e7  Add strict gate regression tests for unanimous pass, dissent, and roster validation
73a5fe2  Fix: canonical gate, receipt persistence, and tamper detection
```

## Primary Objective

Finish and validate the AMARTIE gate-and-receipt foundation before adding public growth features.

## Non-Negotiable Invariants

1. Every governed action must be checked by JudgeGate.verify_action before execution.
2. Exactly nine voting seats are required: J1 through J9.
3. Missing, duplicate, or unknown judge IDs must fail closed.
4. One DISSENT means the action did not execute.
5. No majority override.
6. J0, if implemented, is non-voting and cannot approve an action by itself.
7. Model-lock must be enforced when a model registry is configured.
8. The evidence floor must be enforced.
9. Receipts must be produced for both PASS and DISSENT.
10. A receipt must never claim that an action occurred when the gate denied it.
11. Receipt hashes must use one explicitly labeled algorithm: SHA-256.
12. Receipt-chain links must be independently verifiable.
13. Persistence/replay must preserve the original receipt timestamp and verdict timestamps exactly.
14. A corrupted or partially invalid receipt store must fail closed or report invalidity; it must not silently become a trusted chain.
15. No hidden judge swaps.
16. Do not add public network exposure.
17. Do not add real credentials, secrets, money actions, or external side effects.

## Important Audit Findings to Fix

A. amartie/gate.py currently reconstructs persisted receipts through constructors that generate new timestamps. This can invalidate stored hashes. Add a trusted deserialization path such as:
   GateReceipt.from_dict(record)
   JudgeVerdict.from_dict(record)
   The deserializer must preserve the stored timestamp and hash exactly, then verify the hash.

B. ReceiptChain.append currently changes previous_hash after the receipt hash was calculated. Recompute the receipt hash after linking, or require append to construct the linked receipt correctly.

C. Verify that GateReceipt and Receipt use the same canonical serialization rules where applicable.

D. Reject duplicate judge IDs. A list of nine verdicts containing the same judge nine times must fail.

E. Verify that the supplied IDs are exactly: J1, J2, J3, J4, J5, J6, J7, J8, J9.

F. Add explicit model-registry tests:
   - correct assigned model passes
   - wrong model fails
   - missing assignment fails when strict model-lock mode is enabled

G. Avoid writing tests into the user's real ~/.amartie directory. Every test must use pytest tmp_path or an injected temporary receipt path.

H. Make receipt-store loading validate the complete chain, not only individual receipt hashes.

I. Add replay support that loads a receipt file and returns:
   - chain validity
   - receipt count
   - each receipt's action ID
   - each receipt's verdict
   - whether the action was allowed

J. Dissent receipts must contain an explicit machine-readable result such as:
   "executed": false
   or equivalent metadata.

K. Remove unused imports and keep the implementation Python 3.9+ compatible.

## Testing Requirements

Run from the repository root:

```
python -m pytest tests -v
```

Add or update tests covering:
- exactly nine seats required
- missing seat rejected
- duplicate seat rejected
- unknown seat rejected
- unanimous PASS succeeds
- one DISSENT fails
- one judge with fewer than two evidence/tool calls fails
- model-lock mismatch fails
- receipt hash tampering fails
- payload tampering is detectable
- verdict tampering is detectable
- previous-hash tampering fails
- persisted receipts reload with identical hashes
- persisted chain replay succeeds
- corrupted persistence fails validation
- dissent receipt states that execution did not occur
- no test writes to the user's real home directory

## Visual Documentation Requirement

Create visual documentation for the gate and receipt foundation.

Required outputs:
1. docs/diagrams/system-overview.md
2. docs/diagrams/action-gate-flow.md
3. docs/diagrams/receipt-lifecycle.md
4. docs/diagrams/plugin-boundary.md
5. docs/diagrams/public-contribution-flow.md
6. docs/visual-reference.md

Use Mermaid diagrams that render on GitHub.

Every diagram must:
- show the actual implemented data path
- show JudgeGate.verify_action before execution
- distinguish PASS, DISSENT, persistence, replay, and quarantine
- identify J0 as non-voting if shown
- show the nine canonical seats
- label future features separately from implemented features
- never imply that visual HALO elements are literal security enforcement
- never show direct plugin-to-provider execution
- include accessible text equivalents beneath the diagram
- use consistent colors and terminology
- include a status label: implemented, demo, or future

Add an accessible text block beneath each Mermaid diagram.
Do not use animation or visual effects as evidence of security.
Do not claim that an infographic proves containment or kernel protection.

## Separation of HALO Visualization and Security Evidence

The existing visual files currently contain language such as:
"The ring does not lie"
"zero point / soul / creation"
"force-field-like" interpretations
"J.E.S.U."
simulated node severance and clean-node installation

Those can remain as HALO artistic visualization, but they should be clearly separated from the security documentation:

**HALO visualization:** A conceptual interface for attention, state, and system relationships.

**AMARTIE security evidence:** Code, tests, receipts, hashes, replay results, and documented enforcement boundaries.

That separation will help both audiences:
- newcomers understand the system quickly through visual patterns
- developers see the real workflow
- security researchers know what is actually enforced
- supporters can participate without having to interpret the metaphors first

## Jarvis Scope

Do not implement Jarvis in this foundation branch unless required for a regression test.

The separate Jarvis branch must later ensure that no tool handler executes before gate approval.

Do not claim that Jarvis is safe merely because a manifest declares permissions.

## Public Claims Scope

Audit README.md, index.html, visuals/index.html, visuals/halo-field.html, SPONSORS.md, and docs.

Use this public promise:

"AMARTIE is a local-first alpha system for verifying AI tool actions. It applies a nine-judge review, fails closed on dissent, and produces auditable receipts. We invite developers and security researchers to reproduce the behavior, test the boundaries, and help define stronger enforcement."

Permitted future goals, clearly labeled as future:
- stronger daemon and OS enforcement
- kernel-adjacent protection
- prevention of unauthorized provider or system action substitution
- a hardened jail or sandbox
- production cryptography
- battle-tested protection for advanced AI systems

Do NOT present those future goals as implemented capabilities.
Do NOT claim:
- kernel-level protection currently exists
- a proven jail currently exists
- all provider model swaps are prevented
- production cryptography exists
- the visualization is a literal force field
- the system is battle-ready or battle-tested
- the system is the only system ever devised

## Outreach and Incentives

Do not delete the concern about users harmed by provider behavior. Preserve a neutral, evidence-led awareness track:
- document claims with reproducible evidence
- distinguish allegation, observation, and verified result
- provide a response/right-of-reply path
- do not automatically accuse providers or affiliated companies
- do not send unsolicited complaints or outreach
- do not let sponsors control judge seats or verdict rules
- do not reward passing results, suppressed dissent, or traffic volume
- do not make investment/share/profit promises without legal and accounting review

## Required Workflow

1. Inspect the current branch before editing.
2. Run the existing tests and record failures.
3. Implement the smallest safe fixes.
4. Add regression tests before changing behavior.
5. Run the complete test suite.
6. Review the diff for accidental weakening.
7. Commit changes with descriptive messages.
8. Report:
   - files changed
   - tests run and results
   - invariants verified
   - known limitations
   - commit hashes
9. Do NOT merge into main.
10. Do NOT claim completion if tests fail.

## Expected Deliverable

A reviewable branch containing:
- correct canonical gate behavior
- reliable durable receipt persistence
- replay and full chain verification
- regression tests
- corrected public claims
- no external side effects

## One Important Correction

The current persistence implementation should NOT yet be treated as complete. It recreates receipts with fresh timestamps when loading them, which can make a previously valid persisted hash fail verification. The handoff above explicitly requires fixing that with exact deserialization and replay tests.

## Do NOT "Install Everything" Blindly

Install only the project's declared development dependencies in an isolated virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .\.venv\Scripts\Activate.ps1  # Windows PowerShell

python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pytest
python -m pytest tests -v
```

No API keys, provider credentials, public server binding, or real outbound actions are needed for this foundation work.
