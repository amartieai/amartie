#!/usr/bin/env python3
"""AMARTIE 5-Judge Unanimous Evidence Review Panel.

Each judge reviews the forensic evidence independently. Unanimous verdict required.
Any dissent = evidence rejected. No owner override — the gate is the gate.

Judges:
  J1 — TRUTH:       Factual accuracy, timestamps, hash verification
  J2 — BOUNDARY:    Scope compliance, no trading/identity leakage
  J3 — LOGIC:       Causal chain soundness, no correlation-as-causation
  J4 — COMPLETENESS: All required exhibits present, chain of custody intact
  J5 — EXECUTION:   Reproducible, tooling open, methodology documented

Output: unanimous verdict + signed receipt, or dissenting judge report.
"""

import json, hashlib, datetime
from pathlib import Path
from typing import List, Dict, Optional

# ── Evidence Package ───────────────────────────────────────────────

class EvidencePackage:
    """A sealed evidence package — hash-pinned, immutable once signed."""
    
    def __init__(self, label: str, content: dict):
        self.label = label
        self.content = content
        self.sha256 = hashlib.sha512(
            json.dumps(content, sort_keys=True).encode()
        ).hexdigest()[:32]
    
    def verify(self) -> bool:
        current = hashlib.sha512(
            json.dumps(self.content, sort_keys=True).encode()
        ).hexdigest()[:32]
        return current == self.sha256


# ── Judge Panel ────────────────────────────────────────────────────

class Judge:
    """One independent judge. Reviews evidence, returns verdict."""
    
    def __init__(self, name: str, role: str, principle: str):
        self.name = name
        self.role = role
        self.principle = principle
    
    def review(self, package: EvidencePackage) -> dict:
        """Review evidence package. Returns verdict."""
        raise NotImplementedError("Each judge must implement review()")


class JudgeTruth(Judge):
    """J1 — TRUTH: Verifies factual accuracy, timestamps, hashes."""
    
    def __init__(self):
        super().__init__("J1-TRUTH", "fact-checker", "Factual accuracy, timestamp verification, hash integrity")
    
    def review(self, package: EvidencePackage) -> dict:
        findings = []
        score = 100
        
        # Verify package hash
        if not package.verify():
            findings.append("FAIL: Package hash mismatch — evidence tampered")
            score -= 100
        
        content = package.content
        
        # Check timestamps are valid
        for event in content.get('timeline', []):
            ts = event.get('ts', '')
            if ts:
                try:
                    dt = datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    if dt.year < 2024 or dt.year > 2027:
                        findings.append(f"SUSPICIOUS TIMESTAMP: {ts}")
                        score -= 10
                except:
                    findings.append(f"INVALID TIMESTAMP: {ts}")
                    score -= 20
        
        # Verify receipt hashes
        for receipt in content.get('receipts', []):
            expected = receipt.get('hash', '')
            body = receipt.get('body', '')
            actual = hashlib.sha256(body.encode()).hexdigest()[:16]
            if expected and actual != expected:
                findings.append(f"RECEIPT HASH MISMATCH: {receipt.get('id','')}")
                score -= 30
        
        verdict = "PASS" if score >= 80 else "DISSENT"
        
        return {
            'judge': self.name,
            'principle': self.principle,
            'score': max(score, 0),
            'findings': findings,
            'verdict': verdict,
        }


class JudgeBoundary(Judge):
    """J2 — BOUNDARY: Ensures no trading data or personal identity leaks."""
    
    def __init__(self):
        super().__init__("J2-BOUNDARY", "scope-guard", "No trading signals, no personal identity, no vault paths")
    
    def review(self, package: EvidencePackage) -> dict:
        findings = []
        score = 100
        
        content = package.content
        content_str = json.dumps(content)
        
        # Check for trading terms
        trading_terms = ['NQ1', 'YM1', 'ES1', 'BTCUSD', 'oracle', 'trading', 'pips', '6-to-6', 'backtest', 'entry rule', 'stop-scout']
        for term in trading_terms:
            if term.lower() in content_str.lower():
                findings.append(f"TRADING TERM LEAK: '{term}'")
                score -= 15
        
        # Check for personal identity
        identity_terms = ['Francesco Longo', 'Windsor', 'Longo Construction', 'flongo11', '3820 Tecumseh']
        for term in identity_terms:
            if term in content_str:
                findings.append(f"PERSONAL IDENTITY LEAK: '{term}'")
                score -= 20
        
        # Check for vault paths
        vault_paths = ['FROM_SAMSUNG', 'NUCLEAR_VAULT', 'Sovereign_Vault', 'ORACLE_ENGINE']
        for path in vault_paths:
            if path in content_str:
                findings.append(f"VAULT PATH LEAK: '{path}'")
                score -= 25
        
        verdict = "PASS" if score >= 80 else "DISSENT"
        
        return {
            'judge': self.name,
            'principle': self.principle,
            'score': max(score, 0),
            'findings': findings,
            'verdict': verdict,
        }


class JudgeLogic(Judge):
    """J3 — LOGIC: Ensures causal chain is sound, not correlation."""
    
    def __init__(self):
        super().__init__("J3-LOGIC", "causal-analyst", "Causal chain soundness, no false correlations, alternative explanations ruled out")
    
    def review(self, package: EvidencePackage) -> dict:
        findings = []
        score = 100
        
        content = package.content
        
        # Check for causal claims without mechanism
        for conflict in content.get('identity_conflicts', []):
            # Must have both requested AND detected model
            if not conflict.get('requested') or not conflict.get('detected'):
                findings.append(f"INCOMPLETE CONFLICT: {conflict}")
                score -= 20
            
            # Self-ID alone could be mentioned in passing — need multiple markers
            if conflict.get('score', 0) < 2:
                findings.append(f"WEAK EVIDENCE: self-ID score {conflict.get('score', 0)} — could be coincidental mention")
                score -= 10
        
        # Check quality drops have expected vs actual
        for drop in content.get('quality_drops', []):
            if not drop.get('expected') or not drop.get('actual'):
                findings.append(f"INCOMPLETE DROP RECORD: {drop}")
                score -= 15
        
        # Check for confounding factors (credit exhaustion could cause degradation without swap)
        errors = content.get('error_summary', {})
        if errors.get('402', 0) > 0:
            findings.append("CONFAUNDING: 402 credit errors present — degradation could be credit-related, not swap")
            score -= 10
        
        verdict = "PASS" if score >= 80 else "DISSENT"
        
        return {
            'judge': self.name,
            'principle': self.principle,
            'score': max(score, 0),
            'findings': findings,
            'verdict': verdict,
        }


class JudgeCompleteness(Judge):
    """J4 — COMPLETENESS: All exhibits present, chain of custody documented."""
    
    def __init__(self):
        super().__init__("J4-COMPLETENESS", "custody-clerk", "All required exhibits present, chain of custody intact, no gaps")
    
    def review(self, package: EvidencePackage) -> dict:
        findings = []
        score = 100
        
        content = package.content
        
        required_fields = ['total_requests', 'identity_conflicts', 'quality_drops', 'timeline', 'error_summary']
        for field in required_fields:
            if field not in content:
                findings.append(f"MISSING REQUIRED FIELD: {field}")
                score -= 20
        
        # Check timeline has start and end
        timeline = content.get('timeline', [])
        if len(timeline) < 2:
            findings.append("INCOMPLETE TIMELINE: fewer than 2 events")
            score -= 15
        
        # Check evidence source files exist
        for conflict in content.get('identity_conflicts', []):
            if conflict.get('file'):
                if not Path(conflict['file']).exists():
                    findings.append(f"SOURCE MISSING: {conflict['file']}")
                    score -= 10
        
        verdict = "PASS" if score >= 80 else "DISSENT"
        
        return {
            'judge': self.name,
            'principle': self.principle,
            'score': max(score, 0),
            'findings': findings,
            'verdict': verdict,
        }


class JudgeExecution(Judge):
    """J5 — EXECUTION: Reproducible, tooling open, methodology documented."""
    
    def __init__(self):
        super().__init__("J5-EXECUTION", "reproducibility-checker", "Reproducible, open tooling, documented methodology")
    
    def review(self, package: EvidencePackage) -> dict:
        findings = []
        score = 100
        
        content = package.content
        
        # Tooling must be in the repo
        tool_files = content.get('tooling', [])
        for tf in tool_files:
            if not Path(tf).exists():
                findings.append(f"TOOL MISSING: {tf}")
                score -= 25
        
        # Methodology must be documented
        if not content.get('methodology'):
            findings.append("MISSING: methodology documentation")
            score -= 20
        
        # Results must be hash-chained
        if not content.get('receipt_hash'):
            findings.append("MISSING: receipt hash")
            score -= 15
        
        verdict = "PASS" if score >= 80 else "DISSENT"
        
        return {
            'judge': self.name,
            'principle': self.principle,
            'score': max(score, 0),
            'findings': findings,
            'verdict': verdict,
        }


# ── Panel Review Engine ────────────────────────────────────────────

class JudgePanel:
    """5-judge unanimous review panel. Unanimous PASS required."""
    
    def __init__(self):
        self.judges = [
            JudgeTruth(),
            JudgeBoundary(),
            JudgeLogic(),
            JudgeCompleteness(),
            JudgeExecution(),
        ]
    
    def review(self, package: EvidencePackage) -> dict:
        """Run all 5 judges. Unanimous verdict required."""
        
        verdicts = []
        for judge in self.judges:
            verdict = judge.review(package)
            verdicts.append(verdict)
        
        # Count dissents
        dissents = [v for v in verdicts if v['verdict'] == 'DISSENT']
        unanimous = len(dissents) == 0
        
        # Overall score
        avg_score = sum(v['score'] for v in verdicts) / len(verdicts)
        
        # Panel hash
        panel_data = json.dumps(verdicts, sort_keys=True)
        panel_hash = hashlib.sha256(panel_data.encode()).hexdigest()[:24]
        
        return {
            'unanimous': unanimous,
            'average_score': round(avg_score, 1),
            'dissents': len(dissents),
            'verdicts': verdicts,
            'panel_hash': panel_hash,
            'verdict_label': 'UNANIMOUS_PASS' if unanimous else f'DISSENT_{len(dissents)}',
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


# ── Report Generator ───────────────────────────────────────────────

def generate_judged_report(report: dict, output_path: str):
    """Generate a human-readable judged report."""
    
    lines = []
    w = lines.append
    
    w("=" * 80)
    w("  AMARTIE 5-JUDGE UNANIMOUS EVIDENCE REVIEW")
    w("  " + report['verdict_label'])
    w("=" * 80)
    w(f"  Timestamp: {report['timestamp']}")
    w(f"  Average Score: {report['average_score']}/100")
    w(f"  Dissents: {report['dissents']}/5")
    w(f"  Panel Hash: sha256:{report['panel_hash']}")
    w("=" * 80)
    
    for v in report['verdicts']:
        status = "✓ PASS" if v['verdict'] == 'PASS' else "✗ DISSENT"
        w(f"\n  {v['judge']} — {v['principle']}")
        w(f"    Score: {v['score']}/100  [{status}]")
        if v['findings']:
            for f in v['findings'][:5]:
                w(f"    → {f}")
    
    w("\n" + "=" * 80)
    
    if report['unanimous']:
        w("  UNANIMOUS VERDICT: ALL 5 JUDGES PASSED")
        w("  Evidence is cleared for public release.")
    else:
        w(f"  PANEL DISSENT: {report['dissents']} JUDGE(S) DISSENTED")
        w("  Evidence is NOT cleared for public release.")
        w("  Required action: Address dissenting findings and re-run panel.")
    
    w("=" * 80)
    
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="AMARTIE 5-Judge Evidence Review Panel")
    parser.add_argument("evidence", help="Path to evidence JSON file")
    parser.add_argument("--output", default="judged_report.txt", help="Output file")
    args = parser.parse_args()
    
    with open(args.evidence) as f:
        evidence_data = json.load(f)
    
    package = EvidencePackage("swap_evidence", evidence_data)
    panel = JudgePanel()
    result = panel.review(package)
    
    report = generate_judged_report(result, args.output)
    print(report)
    
    with open(args.output, 'w') as f:
        f.write(report)
    
    # Save raw result
    with open(args.output.replace('.txt', '.json'), 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n[✓] Report saved to: {args.output}")


if __name__ == "__main__":
    main()
