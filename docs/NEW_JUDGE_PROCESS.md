---
title: NEW JUDGE PROCESS
status: draft
last_updated: 2026-09-24
---

# New Judge Process

How a new judge is proposed, tested, and admitted into the AMARTIE 9-judge gate.

---

## 1. Proposal

A new judge enters the roster as an entry in `JudgeGate.ROSTER`. Each entry requires three fields:

```python
ROSTER = {
    "J10": {
        "domain": "YOUR-DOMAIN",          # Short label, e.g. "CONFIDENCE"
        "question": "Is the action ...?",  # JEV question template
        "criteria": {
            "pass":    "Condition for PASS",    # e.g. "Confidence > 0.7"
            "dissent": "Condition for DISSENT"  # e.g. "Confidence < 0.3"
        }
    },
    # ... existing 9 judges
}
```

### Rules

- **Roster count check** — `_check_roster_integrity()` enforces exactly 9 judges. To add a 10th judge you must update `CANONICAL_ROSTER_ORDER` and the expected-count literal in `_check_roster_integrity`, or subclass `JudgeGate` with `validate_roster=False` (not recommended for production).
- **`JUDGE_CONTRACT_VERSION`** — bump only if the `JudgeVerdict` interface changes (new required field, changed field semantics, different serialisation). Adding a roster entry alone never requires a version bump.
- **`ROSTER_VERSION`** — bump when the roster composition changes (new judge, removed judge, domain rename). This value is embedded in every receipt's `roster_snapshot` so the exact roster that evaluated an action can be verified later.
- **Domain uniqueness** — each domain label should be unique across the roster. Duplicate domains confuse traceability in receipts.

### Implementation approaches

| Approach | When to use |
|---|---|
| Edit `JudgeGate.ROSTER` directly | The judge is core AMARTIE infrastructure |
| Subclass `JudgeGate` with `validate_roster=False` | The judge is project- or experiment-specific and must coexist with the canonical 9 |

If subclassing, override `ROSTER` and pass `validate_roster=False` to the constructor to bypass the 9-judge check:

```python
class ExtendedGate(JudgeGate):
    ROSTER = {**JudgeGate.ROSTER, "J10": {...}}

    def __init__(self):
        super().__init__(validate_roster=False)
```

---

## 2. Testing

Every new judge must pass a structured test battery before admission.

### 2a. Fixture verdicts

Build `JudgeVerdict` objects using the `_make_verdict` helper pattern from `tests/test_gate.py`:

```python
def _make_verdict(judge_id, model_id, verdict="PASS",
                  findings=None, corrections=None,
                  tool_calls=None, evidence_items=None):
    return JudgeVerdict(
        judge_id=judge_id,
        model_id=model_id,
        verdict=verdict,
        findings=findings or ["verified"],
        corrections=corrections or [],
        tool_calls=tool_calls or ["cmd1", "cmd2"],
        evidence=EvidencePackage(evidence_items or ["Verified evidence"]),
    )
```

Each fixture must include `EvidencePackage` with at least one `evidence_items` entry. Empty evidence is caught by `is_sufficient()` and causes the gate to fail closed.

### 2b. Feed through the gate

Pass fixture verdicts to `verify_action` via `judge_responses=`:

```python
gate = JudgeGate()
verdicts = []
for i in range(9):
    judge_id = f"J{i+1}"
    v = _make_verdict(
        judge_id=judge_id,
        model_id=gate._get_assigned_model(judge_id),
    )
    verdicts.append(v)

passed, receipt = gate.verify_action("test", {"key": "value"}, verdicts)
```

The gate validates every verdict against the contract schema, checks model-lock, tool_calls minimum (≥2), and evidence sufficiency — all before returning.

### 2c. Assert PASS

A unanimous PASS with contract-compliant verdicts must return `passed == True`:

```python
assert passed == True
assert receipt.hash is not None
assert receipt.roster_snapshot["judges"] == sorted(JudgeGate.ROSTER.keys())
```

### 2d. Assert DISSENT

Test each of these failure modes (at minimum): a test for each must exist.

| Failure mode | How to trigger |
|---|---|
| **Any judge dissents** | Set one verdict's `verdict="DISSENT"` |
| **Empty evidence** | Pass `EvidencePackage([])` to one verdict |
| **Insufficient tool_calls** | Set `tool_calls=["cmd1"]` (fewer than 2) on one verdict |
| **Wrong model_id** | Pass a `model_id` that doesn't match `_get_assigned_model(judge_id)` |

```python
def test_new_judge_dissent(self):
    gate = JudgeGate()
    verdicts = [_make_verdict(f"J{i+1}", gate._get_assigned_model(f"J{i+1}"))
                for i in range(9)]
    # J10 dissents
    verdicts[-1] = _make_verdict("J10", gate._get_assigned_model("J10"),
                                 verdict="DISSENT", corrections=["Failed domain check"])
    passed, _ = gate.verify_action("test", {"key": "value"}, verdicts)
    assert passed == False
```

---

## 3. Admission

Admission follows a two-phase gate of its own.

### Phase A — New judge fixture

1. Build all 9 judge verdicts (including the new judge) as PASS verdicts with valid evidence, tool_calls ≥ 2, and correct model_id.
2. Call `verify_action`.
3. Assert `passed == True`.
4. Assert the receipt `roster_snapshot` contains all 9 judge IDs.

### Phase B — Full regression suite

Run the entire existing test suite:

```bash
cd /home/atlas/amartie-repo
python3 -m pytest tests/test_gate.py -v
```

**All 124 existing tests must pass.** Any regression means the new judge or its supporting changes broke an invariant. Fix before proceeding.

### Promotion

Once both phases pass:

1. The judge is considered **admitted**.
2. If the roster was modified in `JudgeGate.ROSTER` (not a subclass), bump `ROSTER_VERSION`.
3. All subsequent receipts will contain the updated `roster_snapshot`.

---

## 4. Re-judge (Dissent Correction Cycle)

If during live evaluation any judge returns DISSENT, the action is **not admitted**. The corrections field of the dissenting verdict(s) guides the fix.

### Workflow

```
Action proposed
    ↓
9-judge evaluation
    ↓
Any DISSENT? ──yes──→ Read corrections from dissenting verdict(s)
    ↓                      ↓
  PASS                Fix the action / payload
    ↓                      ↓
Receipt stored       Re-run through the full 9-judge panel
                          ↓
                    Any DISSENT? ──yes──→ loop (max round_cap=4)
                          ↓
                        PASS → receipt stored
```

### Invariants (never weakened)

| Invariant | Rationale |
|---|---|
| **Unanimous verdict required** — one DISSENT is enough to block | Prevents coalitions from pushing through marginal actions |
| **Full re-panel** — re-judge re-runs all 9 judges, not just the dissenter | A fix that satisfies one judge may break another's domain |
| **Round cap** — hard limit of 4 rounds (set via `gate.round_cap`) | Prevents indefinite loops; at round 5 the action is dead |
| **Each round produces its own receipt** | Full audit trail of every attempt |

### Corrections format

A DISSENT verdict must include actionable corrections in its `corrections` list:

```python
corrections=[
    "Add source attribution for market data",
    "Reduce position size to within risk limits",
]
```

The party responsible for the action reads these corrections, adjusts the payload, and re-submits.

---

## Appendix: Checklist

- [ ] Entry added to `ROSTER` (or subclass) with domain/question/criteria
- [ ] `CANONICAL_ROSTER_ORDER` and `_check_roster_integrity` updated (if adding beyond 9)
- [ ] `ROSTER_VERSION` bumped
- [ ] `JUDGE_CONTRACT_VERSION` bumped only if JudgeVerdict interface changed
- [ ] New judge fixture tests written (PASS + each DISSENT mode)
- [ ] Full existing test suite (124 tests) passes
- [ ] Mock mode still works (no API key required for tests)
- [ ] Receipt roster_snapshot correctly includes the new judge