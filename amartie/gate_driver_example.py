"""
AMARTIE Gate Driver Example
============================
Minimal wiring example showing how to route outbound actions through
JudgeGate.verify_action and handle the deny-on-dissent path.

Addresses issue #8c: demonstrate actual driver wiring without weakening
gate invariants (no push-through, no owner override, no skip-gate mode).

Usage:
    python -m amartie.gate_driver_example
"""
import json
import tempfile
import os

from amartie.gate import JudgeGate, JudgeVerdict, EvidencePackage

# ── Canonical 9-judge roster ────────────────────────────────────────────
JUDGE_IDS = [f"J{i}" for i in range(1, 10)]


def _make_pass_verdicts(gate: JudgeGate) -> list[JudgeVerdict]:
    """Build 9 PASS verdicts with valid contract fields."""
    return [
        JudgeVerdict(
            judge_id=jid,
            model_id=gate._get_assigned_model(jid),
            verdict="PASS",
            findings=[f"[{jid}] All domain criteria satisfied"],
            corrections=[],
            tool_calls=["gate_driver.verify", "gate_driver.check_contract"],
            impl_version="1.0.0",
            rationale=f"[{jid}] Action passes domain checks",
            evidence=EvidencePackage(
                [f"[{jid}] Verified action payload against criteria"],
                source_refs=["gate_driver_example.py"],
            ),
        )
        for jid in JUDGE_IDS
    ]


def _make_dissent_verdicts(gate: JudgeGate, dissent_judge: str) -> list[JudgeVerdict]:
    """Build 8 PASS + 1 DISSENT — tests deny-on-dissent path."""
    verdicts = []
    for jid in JUDGE_IDS:
        is_dissent = jid == dissent_judge
        verdicts.append(JudgeVerdict(
            judge_id=jid,
            model_id=gate._get_assigned_model(jid),
            verdict="DISSENT" if is_dissent else "PASS",
            findings=(
                [f"[{jid}] Action violates domain constraints"]
                if is_dissent
                else [f"[{jid}] Action is compliant"]
            ),
            corrections=(
                ["Remove disallowed operation", "Restrict to local scope"]
                if is_dissent
                else []
            ),
            tool_calls=["gate_driver.verify", "gate_driver.check_contract"],
            impl_version="1.0.0",
            rationale=(
                f"[{jid}] Corrective action required"
                if is_dissent
                else f"[{jid}] Action is acceptable"
            ),
            evidence=EvidencePackage(
                [f"[{jid}] {'Blocked' if is_dissent else 'Approved'} — "
                 f"details in findings"],
            ),
        ))
    return verdicts


def run_example():
    """Run a complete gate-wiring demonstration.

    Demonstrates:
      1. All-9-PASS action is admitted with a signed receipt.
      2. Action with 1 DISSENT is blocked.
      3. No invariants are weakened (no push-through, no override).
    """
    chain_dir = tempfile.mkdtemp(prefix="gate_driver_example_")
    chain_path = os.path.join(chain_dir, "receipt_chain.jsonl")
    gate = JudgeGate(mock_mode=True, receipt_chain_path=chain_path)

    action_payload = {
        "command": "echo 'hello'",
        "target": "localhost",
    }

    # ── Scenario 1: All 9 PASS — action admitted ────────────────────────
    pass_verdicts = _make_pass_verdicts(gate)
    passed, receipt = gate.verify_action(
        "execute-command", action_payload, pass_verdicts,
    )

    print("═" * 60)
    print("Gate Driver Example — Scenario 1: All-9-PASS")
    print("═" * 60)
    if passed:
        print("  ✓ Action ADMITTED — all 9 judges passed")
    else:
        print("  ✗ Action BLOCKED — unexpected rejection (bug)")
    print(f"  Receipt: {receipt.hash[:24]}...")
    print(f"  Contract: {receipt.contract_version}")
    print(f"  Roster:   {receipt.roster_snapshot['judges']}")
    assert passed, "Gate must admit a unanimous PASS action"

    # ── Scenario 2: J2 (BOUNDARY-INTEGRITY) dissents — action blocked ────
    dissent_verdicts = _make_dissent_verdicts(gate, "J2")
    passed2, receipt2 = gate.verify_action(
        "execute-command", action_payload, dissent_verdicts,
    )

    print()
    print("═" * 60)
    print("Gate Driver Example — Scenario 2: J2 DISSENT")
    print("═" * 60)
    if not passed2:
        print("  ✓ Action BLOCKED — J2 (BOUNDARY-INTEGRITY) dissented")
        print("  ✓ Gate invariants upheld: no push-through, no override")
        for v in dissent_verdicts:
            if v.verdict == "DISSENT":
                print(f"  Dissenting judge: {v.judge_id}")
                print(f"  Corrections: {v.corrections}")
    else:
        print("  ✗ Action ADMITTED despite dissent — gate invariant BROKEN")
    assert not passed2, "Gate must block a dissenting action"

    # ── Chain integrity ─────────────────────────────────────────────────
    print()
    print("═" * 60)
    print("Receipt Chain Integrity")
    print("═" * 60)
    chain_ok = gate.verify_chain_integrity()
    print(f"  Chain valid: {chain_ok}")
    print(f"  Chain length: {len(gate.receipt_chain)}")
    assert chain_ok, "Receipt chain must verify"
    assert len(gate.receipt_chain) == 2

    print()
    print("All gate invariants verified. No push-through, no override.")


if __name__ == "__main__":
    run_example()