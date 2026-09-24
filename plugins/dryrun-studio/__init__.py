"""
Dry-Run Studio Plugin
=====================
Example plugin studio that gates a dry-run, no-network action
through the 9-judge AMARTIE gate.

Addresses GitHub issue #6: Example plugin demonstrating gate integration.
Features:
- dryrun-check: all 9 judges PASS, action proceeds (local execution only)
- network-check: J2 (BOUNDARY-INTEGRITY) dissents, network action blocked
"""

import json
import os
import tempfile

from amartie.gate import JudgeGate, JudgeVerdict, EvidencePackage

PLUGIN_NAME = "Dry-Run Studio"
PLUGIN_VERSION = "0.1.0"
PLUGIN_DESCRIPTION = (
    "Example plugin: gates a dry-run no-network action "
    "through the 9-judge gate."
)
STUDIO_TYPE = "dryrun"

# Canonical judge roster order
JUDGE_IDS = ["J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9"]
JUDGE_DOMAINS = {
    "J1": "TRUTH",
    "J2": "BOUNDARY-INTEGRITY",
    "J3": "LOGIC",
    "J4": "COMPLETENESS",
    "J5": "EXECUTION-AND-SIMPLICITY",
    "J6": "OWNER-INTENT",
    "J7": "RECOVERY",
    "J8": "TRADE-INTEGRITY",
    "J9": "UNITY",
}


def _get_gate():
    """Return a JudgeGate instance in mock_mode with tmp receipt chain."""
    tmp_dir = tempfile.mkdtemp(prefix="dryrun_studio_")
    chain_path = os.path.join(tmp_dir, "receipt_chain.jsonl")
    return JudgeGate(mock_mode=True, receipt_chain_path=chain_path)


def _build_verdicts(
    judge_ids, model_id, verdict, findings, corrections,
    tool_calls, evidence_items, source_refs=None,
):
    """Build a list of JudgeVerdict objects for the given judges."""
    verdicts = []
    for jid in judge_ids:
        domain = JUDGE_DOMAINS.get(jid, "UNKNOWN")
        specific_findings = [
            f"[{jid}/{domain}] {f}" for f in findings
        ]
        specific_corrections = [
            f"[{jid}/{domain}] {c}" for c in corrections
        ]
        v = JudgeVerdict(
            judge_id=jid,
            model_id=model_id,
            verdict=verdict,
            findings=specific_findings,
            corrections=specific_corrections,
            tool_calls=list(tool_calls),
            evidence=EvidencePackage(
                evidence_items=list(evidence_items),
                source_refs=source_refs or [],
            ),
        )
        verdicts.append(v)
    return verdicts


def render(config=None):
    """Render plugin metadata and basic HTML."""
    return {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "type": STUDIO_TYPE,
        "html": _get_studio_html(),
        "config": config or {},
    }


def handle(action, data):
    """
    Handle cockpit actions.

    Actions:
      - dryrun-check:   All 9 judges PASS. Evidence shows local filesystem
                        reads and writes with no network activity.
      - network-check:  J2 (BOUNDARY-INTEGRITY) dissents on network access.
                        All other judges PASS. Action is blocked.
    """
    gate = _get_gate()

    if action == "dryrun-check":
        return _handle_dryrun_check(gate, data)
    elif action == "network-check":
        return _handle_network_check(gate, data)
    else:
        return {"error": f"Unknown action: {action}"}


def _handle_dryrun_check(gate, data):
    """All 9 judges PASS — local dry-run proceeds."""
    verdicts = _build_verdicts(
        judge_ids=JUDGE_IDS,
        model_id="mock-model",
        verdict="PASS",
        findings=["Executing local file read", "Writing to /tmp/output",
                   "No network access detected"],
        corrections=[],
        tool_calls=["read_local_file", "write_tmp_file",
                     "verify_no_network"],
        evidence_items=["Local file /tmp/dryrun_test exists",
                        "Output written to /tmp/dryrun_result",
                        "Network interfaces are down"],
        source_refs=["/tmp/dryrun_test", "/tmp/dryrun_result"],
    )

    passed, receipt = gate.verify_action("dryrun", data, verdicts)
    return {
        "action": "dryrun-check",
        "passed": passed,
        "receipt_hash": receipt.hash,
        "verdict_count": len(verdicts),
        "verdict_summary": _summarize_verdicts(verdicts),
    }


def _handle_network_check(gate, data):
    """J2 (BOUNDARY-INTEGRITY) dissents — network action blocked."""
    verdicts = []

    for jid in JUDGE_IDS:
        domain = JUDGE_DOMAINS.get(jid, "UNKNOWN")

        if jid == "J2":
            # J2 dissents: network access violates boundary integrity
            v = JudgeVerdict(
                judge_id=jid,
                model_id="mock-model",
                verdict="DISSENT",
                findings=[
                    f"[{jid}/{domain}] Remote host is outside authorized scope",
                    f"[{jid}/{domain}] Action requires network access",
                ],
                corrections=[
                    f"[{jid}/{domain}] Block network egress",
                    f"[{jid}/{domain}] Restrict to local execution only",
                ],
                tool_calls=["resolve_hostname", "check_network_state",
                             "block_egress"],
                evidence=EvidencePackage(
                    evidence_items=[
                        f"[{jid}/{domain}] Network egress denied — "
                        f"target 198.51.100.42 is external",
                        "No outbound connectivity in dry-run mode",
                    ],
                    source_refs=["policy/boundary-integrity.md"],
                ),
            )
        else:
            v = JudgeVerdict(
                judge_id=jid,
                model_id="mock-model",
                verdict="PASS",
                findings=[
                    f"[{jid}/{domain}] Local execution scope respected",
                ],
                corrections=[],
                tool_calls=["read_local_file", "verify_local_scope",
                             "log_verdict"],
                evidence=EvidencePackage(
                    evidence_items=[
                        f"[{jid}/{domain}] Action is local and contained",
                    ],
                ),
            )
        verdicts.append(v)

    passed, receipt = gate.verify_action("network-check", data, verdicts)
    return {
        "action": "network-check",
        "passed": passed,
        "receipt_hash": receipt.hash,
        "verdict_count": len(verdicts),
        "verdict_summary": _summarize_verdicts(verdicts),
    }


def _summarize_verdicts(verdicts):
    """Summarize each judge's verdict for the response."""
    return [
        {
            "judge_id": v.judge_id,
            "domain": JUDGE_DOMAINS.get(v.judge_id, "UNKNOWN"),
            "verdict": v.verdict,
            "tool_call_count": len(v.tool_calls),
            "evidence_count": len(v.evidence.evidence_items),
        }
        for v in verdicts
    ]


def _get_studio_html():
    return """
<div class="studio-dryrun">
  <h2>Dry-Run Studio</h2>
  <p class="muted">Gate-gated dry-run: no-network actions only</p>
  <div class="row">
    <button onclick="studioDryRun()">Run Dry-Run Check</button>
    <button onclick="studioNetworkCheck()">Run Network Check</button>
  </div>
  <div id="studio-status"></div>
  <div id="studio-details" class="muted"></div>
</div>
<script>
async function studioDryRun() {
  const res = await cockpit.pluginAction('dryrun-studio', 'dryrun-check', {});
  document.getElementById('studio-status').textContent =
    res.passed ? 'PASSED — dry-run action approved' : 'BLOCKED — gate rejected';
  document.getElementById('studio-details').textContent =
    'Receipt: ' + (res.receipt_hash || 'N/A');
}
async function studioNetworkCheck() {
  const res = await cockpit.pluginAction('dryrun-studio', 'network-check', {});
  document.getElementById('studio-status').textContent =
    res.passed ? 'PASSED — network action approved' : 'BLOCKED — network access denied by J2';
  document.getElementById('studio-details').textContent =
    'Receipt: ' + (res.receipt_hash || 'N/A');
}
</script>
"""


def demo():
    """Run both checks and print results to stdout."""
    print("=" * 60)
    print("Dry-Run Studio Demo")
    print("=" * 60)
    print()

    data = {"reason": "demo invocation"}

    # --- Dry-run check ---
    print("--- dryrun-check ---")
    dry_result = handle("dryrun-check", data)
    dry_passed = dry_result["passed"]
    print(f"  Passed: {dry_passed}")
    for s in dry_result["verdict_summary"]:
        status = "PASS" if s["verdict"] == "PASS" else "DISSENT"
        print(f"  {s['judge_id']} ({s['domain']}): {status}")
    print(f"  Receipt: {dry_result['receipt_hash'][:16]}...")
    assert dry_passed is True, "dryrun-check should pass!"
    print()

    # --- Network check ---
    print("--- network-check ---")
    net_result = handle("network-check", data)
    net_passed = net_result["passed"]
    print(f"  Passed: {net_passed}")
    for s in net_result["verdict_summary"]:
        status = "PASS" if s["verdict"] == "PASS" else "DISSENT"
        print(f"  {s['judge_id']} ({s['domain']}): {status}")
    print(f"  Receipt: {net_result['receipt_hash'][:16]}...")
    assert net_passed is False, "network-check should be blocked!"
    print()

    print("All demo assertions passed.")


if __name__ == "__main__":
    demo()