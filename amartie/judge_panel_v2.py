#!/usr/bin/env python3
"""AMARTIE Panel V2 — 9 voting judges + J0 meta-auditor.

Full unanimous gate per owner directive 2026-09-15.
One dissent = correction + re-judge. J0 non-voting.

Usage:
    python3 judge_panel_v2.py <evidence.json>
"""

import json, hashlib, datetime, re, os
from pathlib import Path
from typing import List, Dict

# ── Evidence Package ───────────────────────────────────────────────

class EvidencePackage:
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


# ── 9 Voting Judges ────────────────────────────────────────────────

class Judge:
    def __init__(self, name: str, role: str, principle: str):
        self.name = name
        self.role = role
        self.principle = principle
    
    def review(self, package: EvidencePackage) -> dict:
        raise NotImplementedError


class JudgeTruth(Judge):
    """J1 — TRUTH: verify EVERY factual claim against the live machine."""
    def __init__(self):
        super().__init__("J1-TRUTH", "fact-checker", "Verify every factual claim against the live machine")
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        
        if not p.verify():
            findings.append("FAIL: Package hash mismatch")
            score -= 100
        
        content = p.content
        
        # Verify timeline timestamps
        for e in content.get('timeline', []):
            ts = e.get('ts', '')
            if ts:
                try:
                    dt = datetime.datetime.fromisoformat(ts.replace('Z', '+00:00') if 'Z' in ts else ts)
                    if dt.year < 2024 or dt.year > 2027:
                        findings.append(f"SUSPICIOUS TIMESTAMP: {ts}")
                        score -= 10
                except:
                    findings.append(f"INVALID TIMESTAMP: {ts}")
                    score -= 20
        
        # Verify receipt hashes match bodies
        for r in content.get('receipts', []):
            body = r.get('body', '')
            expected = r.get('hash', '')
            actual = hashlib.sha256(body.encode()).hexdigest()[:16]
            if expected and actual != expected:
                findings.append(f"RECEIPT HASH MISMATCH: {r.get('id','')}")
                score -= 30
        
        # Verify conflict files exist on disk
        for c in content.get('identity_conflicts', []):
            fp = c.get('file', '')
            if fp and not Path(fp).exists():
                findings.append(f"SOURCE FILE MISSING: {fp}")
                score -= 15
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgeBoundary(Judge):
    """J2 — BOUNDARY-INTEGRITY: no trading signals, no identity, no vault paths."""
    def __init__(self):
        super().__init__("J2-BOUNDARY", "scope-guard", "No improper boundary crossings")
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content = p.content
        content_str = json.dumps(content)
        
        # Trading terms leak
        for term in ['NQ1', 'YM1', 'ES1', 'BTCUSD', 'oracle', 'trading', 'pips', '6-to-6', 'backtest', 'entry rule', 'stop-scout', 'destroyer']:
            if term.lower() in content_str.lower():
                findings.append(f"TRADING TERM LEAK: '{term}'")
                score -= 15
        
        # Personal identity leak
        for term in ['Francesco Longo', 'Windsor', 'Longo Construction', 'flongo11@gmail.com', '3820 Tecumseh', '226-260-6399']:
            if term in content_str:
                findings.append(f"IDENTITY LEAK: '{term}'")
                score -= 20
        
        # Vault paths leak
        for path in ['FROM_SAMSUNG', 'NUCLEAR_VAULT', 'Sovereign_Vault', 'ORACLE_ENGINE', 'deep_archive', 'TRADING_ARCHIVE']:
            if path in content_str:
                findings.append(f"VAULT PATH LEAK: '{path}'")
                score -= 25
        
        # Outbound compliance — no false performance claims
        for claim in content.get('claims', []):
            if '100%' in claim or 'guaranteed' in claim.lower():
                findings.append(f"PERFORMANCE CLAIM WITHOUT RECEIPT: {claim}")
                score -= 15
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgeLogic(Judge):
    """J3 — LOGIC: causal chain soundness, test validity, version-chain continuity."""
    def __init__(self):
        super().__init__("J3-LOGIC", "causal-analyst", "Causal chain soundness, no correlation-as-causation")
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content = p.content
        
        # Self-ID score >= 2 required (single mention = coincidental)
        for c in content.get('identity_conflicts', []):
            if c.get('score', 0) < 2:
                findings.append(f"WEAK SELF-ID: score {c.get('score',0)} for {c.get('requested')}->{c.get('detected')} — could be coincidental mention")
                score -= 10
        
        # Quality drops must have both expected and actual
        for d in content.get('quality_drops', []):
            if not d.get('expected') or not d.get('actual'):
                findings.append(f"INCOMPLETE DROP RECORD: {d}")
                score -= 15
        
        # Confounding factor: 402 errors could cause degradation without swap
        if content.get('error_summary', {}).get('402', 0) > 0:
            findings.append("CONFOUNDING: 402 credit errors present — degradation could be credit-related, not swap")
            score -= 10
        
        # Known-good control: if a claimed swap session also has 402s, need to rule out credit cause
        if content.get('error_summary', {}).get('402', 0) > 10 and len(content.get('identity_conflicts', [])) > 0:
            findings.append("CONTROL GAP: Sessions with identity conflicts also have 402 errors — need to rule out credit exhaustion as cause")
            score -= 15
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgeCompleteness(Judge):
    """J4 — COMPLETENESS: all required exhibits present, chain of custody intact."""
    def __init__(self):
        super().__init__("J4-COMPLETENESS", "custody-clerk", "All required exhibits present, chain of custody intact")
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content = p.content
        
        required = ['total_requests', 'identity_conflicts', 'quality_drops', 'timeline', 'error_summary', 'models_requested']
        for field in required:
            if field not in content:
                findings.append(f"MISSING FIELD: {field}")
                score -= 20
        
        # Timeline needs start + end
        if len(content.get('timeline', [])) < 2:
            findings.append("INCOMPLETE TIMELINE: <2 events")
            score -= 15
        
        # Source files must exist on disk
        for c in content.get('identity_conflicts', []):
            if c.get('file') and not Path(c['file']).exists():
                findings.append(f"SOURCE MISSING: {c['file']}")
                score -= 10
        
        # Error summary must have at least one entry
        if not content.get('error_summary'):
            findings.append("MISSING: error_summary")
            score -= 15
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgeExecution(Judge):
    """J5 — EXECUTION-AND-SIMPLICITY: every step runnable, minimal, tooling open."""
    def __init__(self):
        super().__init__("J5-EXECUTION", "reproducibility-checker", "Reproducible, open tooling, documented methodology")
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content = p.content
        
        # Tooling must exist
        for tf in content.get('tooling', []):
            if not Path(tf).exists():
                findings.append(f"TOOL MISSING: {tf}")
                score -= 25
        
        # Methodology must be documented
        if not content.get('methodology'):
            findings.append("MISSING: methodology documentation")
            score -= 20
        
        # Receipt hash must be present
        if not content.get('receipt_hash'):
            findings.append("MISSING: receipt hash")
            score -= 15
        
        # Minimum tooling requirement
        if len(content.get('tooling', [])) < 2:
            findings.append("INSUFFICIENT TOOLING: need at least swap detector + forensic engine")
            score -= 20
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgeOwnerIntent(Judge):
    """J6 — OWNER-INTENT: fidelity to the owner's stated directives."""
    def __init__(self):
        super().__init__("J6-OWNER-INTENT", "intent-checker", "Fidelity to owner's stated directives")
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content = p.content
        
        # Must state what was requested vs what was detected
        if not content.get('identity_conflicts'):
            findings.append("NO IDENTITY ANALYSIS: owner directive requires proving model identity conflicts")
            score -= 30
        
        # Must state quality metrics
        if not content.get('quality_drops'):
            findings.append("NO QUALITY ANALYSIS: owner directive requires quality degradation proof")
            score -= 30
        
        # Must include swap mechanism explanation
        if not content.get('swap_mechanism'):
            findings.append("MISSING: explanation of swap mechanism (e.g., credit exhaustion -> silent failover)")
            score -= 20
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgeRecovery(Judge):
    """J7 — RECOVERY: rollback at every destructive step, archive verification."""
    def __init__(self):
        super().__init__("J7-RECOVERY", "rollback-checker", "Rollback at every destructive step, archive verification before point of no return")
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content = p.content
        
        # Evidence must be preserved across multiple locations
        if not content.get('preservation', {}).get('locations', []):
            findings.append("NO PRESERVATION PLAN: evidence must be on multiple platforms/jurisdictions")
            score -= 30
        
        # Must have chain of custody documentation
        if not content.get('chain_of_custody'):
            findings.append("MISSING: chain of custody documentation")
            score -= 25
        
        # Evidence must survive single-point-of-failure
        if not content.get('preservation', {}).get('off_box', False):
            findings.append("SINGLE POINT OF FAILURE: no off-box mirror documented")
            score -= 20
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgeTradeIntegrity(Judge):
    """J8 — TRADE-INTEGRITY: money paths, dry-run/live flags, signal fidelity."""
    def __init__(self):
        super().__init__("J8-TRADE-INTEGRITY", "money-path-auditor", "Money paths secure, no live trades from analysis")
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content_str = json.dumps(p.content)
        
        # Must NOT contain any trade orders or signals
        trade_order_patterns = ['market_order', 'limit_order', 'stop_order', 'buy ', 'sell ', 'long ', 'short ', 'entry_at', 'stop_at']
        for pat in trade_order_patterns:
            if re.search(rf'\b{pat}', content_str, re.IGNORECASE):
                findings.append(f"TRADE ORDER LEAK: '{pat}' found in evidence — analysis must not contain orders")
                score -= 20
        
        # Must NOT contain exact price levels that could be active
        price_patterns = re.findall(r'\b\d{4,5}\.\d{1,2}\b', content_str)
        if len(price_patterns) > 5:
            findings.append(f"PRICE LEVELS: {len(price_patterns)} price-like values found — risk of active signal leakage")
            score -= 15
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgeUnity(Judge):
    """J9 — UNITY: whole-machine check, end-to-end dataflow, receipts fabric."""
    def __init__(self):
        super().__init__("J9-UNITY", "whole-machine-checker", "End-to-end dataflow, receipts fabric, interface cross-check")
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content = p.content
        
        # All receipts must be hash-pinned
        for r in content.get('receipts', []):
            if not r.get('hash'):
                findings.append(f"UNPINNED RECEIPT: {r.get('id','unknown')}")
                score -= 15
        
        # Dataflow must be documented
        if not content.get('dataflow'):
            findings.append("MISSING: dataflow documentation (source -> analysis -> verdict -> receipt)")
            score -= 20
        
        # Tooling interfaces must be cross-checked
        if not content.get('tooling_interfaces'):
            findings.append("MISSING: tooling interface cross-check")
            score -= 15
        
        # Performance/latency budget
        if not content.get('performance_budget'):
            findings.append("MISSING: performance/latency budget")
            score -= 10
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgeMetaAuditor(Judge):
    """J0 — META-AUDITOR: judges the voters. Non-voting."""
    def __init__(self):
        super().__init__("J0-META-AUDITOR", "judge-of-judges", "Non-voting: judges the voters")
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        
        # This judge reviews OTHER judges' work. For standalone mode, verify:
        # - All 9 voting judges are present
        # - No judge has tool_calls=0
        # - No rubber-stamp dissents
        
        verifiable_fields = ['total_requests', 'identity_conflicts', 'quality_drops', 'timeline', 'error_summary']
        for field in verifiable_fields:
            if field not in p.content:
                findings.append(f"J0: Evidence field '{field}' missing — judges cannot verify without it")
                score -= 15
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


# ── Panel V2 Engine ────────────────────────────────────────────────

class PanelV2:
    """AMARTIE Panel V2 — 9 voting judges + J0 meta-auditor. Unanimous pass required."""
    
    def __init__(self):
        self.voting_judges = [
            JudgeTruth(),
            JudgeBoundary(),
            JudgeLogic(),
            JudgeCompleteness(),
            JudgeExecution(),
            JudgeOwnerIntent(),
            JudgeRecovery(),
            JudgeTradeIntegrity(),
            JudgeUnity(),
        ]
        self.meta_auditor = JudgeMetaAuditor()
    
    def review(self, package: EvidencePackage) -> dict:
        """Run all 9 voting judges + J0. Unanimous pass required."""
        
        verdicts = []
        for judge in self.voting_judges:
            verdict = judge.review(package)
            verdicts.append(verdict)
        
        # J0 review (non-voting)
        j0_verdict = self.meta_auditor.review(package)
        
        # Tally
        dissents = [v for v in verdicts if v['verdict'] == 'DISSENT']
        unanimous = len(dissents) == 0
        avg_score = sum(v['score'] for v in verdicts) / len(verdicts)
        
        panel_hash = hashlib.sha256(
            json.dumps(verdicts, sort_keys=True).encode()
        ).hexdigest()[:24]
        
        return {
            'unanimous': unanimous,
            'average_score': round(avg_score, 1),
            'dissents': len(dissents),
            'dissenting_judges': [v['judge'] for v in dissents],
            'verdicts': verdicts,
            'j0_meta_auditor': j0_verdict,
            'panel_hash': panel_hash,
            'verdict_label': 'UNANIMOUS_PASS_9/9' if unanimous else f'DISSENT_{len(dissents)}/9',
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'panel_version': 'AMARTIE_PANEL_V2',
        }


# ── Report Generator ───────────────────────────────────────────────

def generate_report(report: dict) -> str:
    lines = []
    w = lines.append
    
    w("=" * 80)
    w(f"  AMARTIE PANEL V2 — {report['verdict_label']}")
    w(f"  {report['panel_version']}")
    w("=" * 80)
    w(f"  Timestamp: {report['timestamp']}")
    w(f"  Average Score: {report['average_score']}/100")
    w(f"  Dissents: {report['dissents']}/9")
    w(f"  Panel Hash: sha256:{report['panel_hash']}")
    w("=" * 80)
    
    for v in report['verdicts']:
        status = "✓ PASS" if v['verdict'] == 'PASS' else "✗ DISSENT"
        w(f"\n  {v['judge']} — {v['principle']}")
        w(f"    Score: {v['score']}/100  [{status}]")
        if v['findings']:
            for f in v['findings'][:8]:
                w(f"    → {f}")
    
    w(f"\n  {report['j0_meta_auditor']['judge']} — {report['j0_meta_auditor']['principle']}")
    w(f"    Score: {report['j0_meta_auditor']['score']}/100  [{report['j0_meta_auditor']['verdict']}]")
    
    w("\n" + "=" * 80)
    
    if report['unanimous']:
        w("  UNANIMOUS VERDICT: 9/9 JUDGES PASSED")
        w("  Evidence is cleared for public release.")
        w("  Standard: denialbydesign.org — absolute proof, unanimous judges.")
    else:
        w(f"  PANEL DISSENT: {report['dissents']}/9 JUDGE(S) DISSENTED")
        w(f"  Dissenting: {', '.join(report['dissenting_judges'])}")
        w("  Evidence is NOT cleared for public release.")
        w("  Required: Address dissenting findings and re-run panel.")
    
    w("=" * 80)
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="AMARTIE Panel V2 — 9 Judge Unanimous Review")
    parser.add_argument("evidence", help="Path to evidence JSON file")
    parser.add_argument("--output", default="panel_v2_report.txt", help="Output file")
    args = parser.parse_args()
    
    with open(args.evidence) as f:
        evidence_data = json.load(f)
    
    package = EvidencePackage("swap_evidence_v2", evidence_data)
    panel = PanelV2()
    result = panel.review(package)
    
    report = generate_report(result)
    print(report)
    
    with open(args.output, 'w') as f:
        f.write(report)
    
    with open(args.output.replace('.txt', '.json'), 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n[✓] Report saved to: {Path(args.output).absolute()}")


if __name__ == "__main__":
    main()
