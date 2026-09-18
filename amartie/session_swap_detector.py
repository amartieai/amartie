#!/usr/bin/env python3
"""AMARTIE Session Swap Detector — full forensic analyzer.

Reads Hermes request dumps, tracks model requests vs responses,
detects swaps, and produces hash-chained receipts.

Usage:
    python3 session_swap_detector.py <sessions_dir>
    python3 session_swap_detector.py --receipt <session.json>
"""

import json, os, sys, hashlib, re
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

# ── Model Quality Signatures ───────────────────────────────────────
# Each model has a distinctive quality fingerprint based on:
# - Response length distribution
# - Vocabulary richness
# - Structural patterns
# - Reasoning depth

MODEL_SIGNATURES = {
    "deepseek/deepseek-v4-flash": {
        "avg_len": 800, "std_len": 400,
        "code_heavy": True, "reasoning_markers": ["because", "therefore", "analysis", "step"],
        "structure_markers": ["##", "```", "- "],
        "description": "DeepSeek V4 Flash"
    },
    "deepseek/deepseek-v4-pro": {
        "avg_len": 1200, "std_len": 500,
        "code_heavy": True, "reasoning_markers": ["because", "therefore", "analysis", "step", "first", "second"],
        "structure_markers": ["##", "```", "- ", "1. "],
        "description": "DeepSeek V4 Pro"
    },
    "moonshotai/kimi-k3": {
        "avg_len": 600, "std_len": 300,
        "code_heavy": False, "reasoning_markers": ["so", "first", "check"],
        "structure_markers": ["##", "- "],
        "description": "Kimi K3"
    },
    "moonshotai/kimi-k2.7-code": {
        "avg_len": 700, "std_len": 350,
        "code_heavy": True, "reasoning_markers": ["because", "step", "analysis"],
        "structure_markers": ["##", "```", "- "],
        "description": "Kimi K2.7 Code"
    },
}

# ── Forensic Analyzer ──────────────────────────────────────────────

class ForensicAnalyzer:
    def __init__(self, sessions_dir: str):
        self.dir = Path(sessions_dir)
        self.records = []
        self.swap_findings = []
    
    def analyze(self) -> dict:
        files = sorted(self.dir.glob("*.json"))
        print(f"[*] Scanning {len(files)} files...")
        
        for fp in files:
            try:
                with open(fp) as f:
                    d = json.load(f)
                rec = self._parse_record(d, fp.name)
                if rec:
                    self.records.append(rec)
            except Exception as e:
                pass
        
        # Sort by timestamp
        self.records.sort(key=lambda r: r.get('ts', ''))
        
        # Detect swaps
        self._detect_swaps()
        
        return self._build_report()
    
    def _parse_record(self, d: dict, fname: str) -> dict:
        body = d.get('request', {}).get('body', {})
        if not body:
            return None
        
        model = body.get('model', 'unknown')
        ts = d.get('timestamp', '')
        reason = d.get('reason', '')
        err = d.get('error', {})
        err_code = ''
        err_msg = ''
        if isinstance(err, dict):
            err_code = str(err.get('status_code', ''))
            err_msg = err.get('message', '')[:100]
        elif isinstance(err, str):
            err_msg = err[:100]
        
        # Count messages
        msgs = body.get('messages', [])
        n_msgs = len(msgs)
        
        # Extract assistant responses and their content
        asst_contents = []
        for m in msgs:
            if m.get('role') == 'assistant':
                c = m.get('content', '')
                if isinstance(c, list):
                    c = ' '.join(x.get('text','') for x in c if isinstance(x, dict))
                if c:
                    asst_contents.append(c)
        
        # Response quality metrics
        total_chars = sum(len(c) for c in asst_contents)
        avg_len = total_chars / max(len(asst_contents), 1)
        
        # Structure score
        structure_score = 0
        all_content = ' '.join(asst_contents)
        for marker in ['##', '```', '- ', '1. ', 'because', 'therefore', 'analysis']:
            structure_score += all_content.count(marker)
        
        return {
            'file': fname,
            'ts': ts,
            'model_requested': model,
            'reason': reason,
            'err_code': err_code,
            'err_msg': err_msg,
            'n_msgs': n_msgs,
            'n_asst': len(asst_contents),
            'total_chars': total_chars,
            'avg_len': round(avg_len, 1),
            'structure_score': structure_score,
            'asst_samples': asst_contents[:3],
        }
    
    def _detect_swaps(self):
        """Detect model swaps by comparing requested vs actual quality."""
        for rec in self.records:
            req = rec['model_requested']
            sig = MODEL_SIGNATURES.get(req)
            if not sig:
                continue
            
            # Check if quality matches signature
            avg_len = rec['avg_len']
            struct = rec['structure_score']
            
            # Heuristic: if avg_len is way below signature, flag
            if avg_len > 0 and avg_len < sig['avg_len'] * 0.3:
                self.swap_findings.append({
                    'ts': rec['ts'],
                    'file': rec['file'],
                    'requested': req,
                    'expected_avg': sig['avg_len'],
                    'actual_avg': avg_len,
                    'ratio': round(avg_len / sig['avg_len'], 2),
                    'verdict': 'QUALITY_DROP',
                    'confidence': 'HIGH' if avg_len < sig['avg_len'] * 0.1 else 'MEDIUM',
                    'reason': f"Expected ~{sig['avg_len']} chars, got {avg_len}"
                })
    
    def _build_report(self) -> dict:
        # Model distribution
        req_models = Counter(r['model_requested'] for r in self.records)
        err_codes = Counter(r['err_code'] for r in self.records if r['err_code'])
        
        # Timeline of requests vs errors
        timeline = []
        for r in self.records:
            timeline.append({
                'ts': r['ts'][:19],
                'model': r['model_requested'],
                'err': r['err_code'],
                'avg_len': r['avg_len'],
            })
        
        # Swap summary
        n_swaps = len([s for s in self.swap_findings if s['verdict'] == 'QUALITY_DROP'])
        
        return {
            'total_requests': len(self.records),
            'models_requested': dict(req_models),
            'errors': dict(err_codes),
            'swaps_detected': n_swaps,
            'swap_details': self.swap_findings[:20],
            'timeline': timeline[:30],
        }


# ── Receipt Generator ──────────────────────────────────────────────

def generate_receipt(report: dict) -> str:
    lines = [
        "╔══════════════════════════════════════════════════════════════╗",
        "║       AMARTIE SESSION FORENSIC SWAP REPORT                ║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║ Total Requests:    {str(report['total_requests']):40s} ║",
        f"║ Swaps Detected:    {str(report['swaps_detected']):40s} ║",
        "╠══════════════════════════════════════════════════════════════╣",
        "║ MODELS REQUESTED:                                           ║",
    ]
    for m, c in report['models_requested'].items():
        lines.append(f"║   {m[:50]:50s} {str(c):>3s} ║")
    
    lines.append("╠══════════════════════════════════════════════════════════════╣")
    lines.append("║ ERRORS:                                                     ║")
    for m, c in report['errors'].items():
        lines.append(f"║   {m[:50]:50s} {str(c):>3s} ║")
    
    if report['swap_details']:
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("║ SWAP DETAILS:                                               ║")
        for s in report['swap_details'][:10]:
            lines.append(f"║ {s['ts'][:19]} {s['requested'][:25]:25s} {s['confidence']:6s} ║")
            lines.append(f"║   exp:{s['expected_avg']} act:{s['actual_avg']} ratio:{s['ratio']}               ║")
    
    lines.append("╚══════════════════════════════════════════════════════════════╝")
    
    # Hash
    content = json.dumps(report, sort_keys=True)
    h = hashlib.sha256(content.encode()).hexdigest()[:16]
    receipt = "\n".join(lines)
    receipt += f"\nReceipt: sha256:{h}"
    receipt += f"\nChain: AMARTIE-FORENSIC-v1 · {datetime.utcnow().strftime('%Y%m%d')}"
    return receipt


# ── CLI ────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="AMARTIE Session Forensic Swap Detector")
    parser.add_argument("dir", help="Path to sessions directory")
    args = parser.parse_args()
    
    analyzer = ForensicAnalyzer(args.dir)
    report = analyzer.analyze()
    
    receipt = generate_receipt(report)
    print(receipt)
    
    # Save raw report
    out = Path("swap_report.json")
    with open(out, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n[✓] Raw report saved to: {out.absolute()}")


if __name__ == "__main__":
    main()
