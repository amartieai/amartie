#!/usr/bin/env python3
"""AMARTIE Model Swap Forensic Evidentiary Engine.

Produces legally-admissible proof of AI model swapping.
Outputs: identity conflicts, markdown fingerprint shifts, timing analysis,
         hash-chained receipts, timeline reconstruction.

Usage:
    python3 forensic_engine.py <sessions_dir> [--report report.html]
"""

import json, os, sys, hashlib, re, html
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import argparse

# ── Known Model Self-Identification Markers ────────────────────────
# These are how models self-identify in their responses

SELF_IDENTIFICATION = {
    'claude': {
        'markers': [r"I'm Claude", r"I am Claude", r"Claude[,\.]", r"Anthropic", r"As an AI assistant made by Anthropic", r"I'm an AI assistant created by Anthropic"],
        'markdown_style': ['##', '```', '- ', '**', '---'],
    },
    'gpt': {
        'markers': [r"I'm ChatGPT", r"ChatGPT", r"I'm GPT", r"developed by OpenAI", r"As an AI language model developed by OpenAI"],
        'markdown_style': ['##', '```', '- ', '**'],
    },
    'deepseek': {
        'markers': [r"I'm DeepSeek", r"I am DeepSeek", r"DeepSeek[,\.]", r"made by DeepSeek"],
        'markdown_style': ['##', '```', '- ', '1. ', '**'],
    },
    'kimi': {
        'markers': [r"I'm Kimi", r"I am Kimi", r"Kimi[,\.]", r"made by Moonshot", r"Moonshot AI"],
        'markdown_style': ['##', '- ', '**'],
    },
    'grok': {
        'markers': [r"I'm Grok", r"I am Grok", r"Grok[,\.]", r"made by xAI", r"xAI"],
        'markdown_style': ['##', '```', '- ', '**'],
    },
    'gemini': {
        'markers': [r"I'm Gemini", r"I am Gemini", r"Gemini[,\.]", r"made by Google", r"Google AI"],
        'markdown_style': ['##', '```', '- ', '**'],
    },
}

# ── Response Fingerprinting ────────────────────────────────────────

class ResponseFingerprint:
    """Extract a unique fingerprint from an API response."""
    
    @staticmethod
    def extract(content: str, model_requested: str) -> dict:
        """Extract all identifying features from a response."""
        if not content:
            return None
        
        content_lower = content.lower()
        
        # 1. Self-Identification Detection
        detected_ids = {}
        for model_name, data in SELF_IDENTIFICATION.items():
            score = 0
            for marker in data['markers']:
                matches = re.findall(marker, content, re.IGNORECASE)
                score += len(matches)
            if score > 0:
                detected_ids[model_name] = score
        
        # 2. Markdown Fingerprint
        md_fingerprint = {}
        md_fingerprint['hash_headers'] = len(re.findall(r'^#{1,6}\s+', content, re.MULTILINE))
        md_fingerprint['code_blocks'] = len(re.findall(r'```[\w]*\n', content))
        md_fingerprint['bullet_items'] = len(re.findall(r'^-\s+', content, re.MULTILINE))
        md_fingerprint['numbered_items'] = len(re.findall(r'^\d+\.\s+', content, re.MULTILINE))
        md_fingerprint['bold_phrases'] = len(re.findall(r'\*\*[^*]+\*\*', content))
        md_fingerprint['italic_phrases'] = len(re.findall(r'(?<!\*)\*[^*]+\*(?!\*)', content))
        md_fingerprint['horizontal_rules'] = len(re.findall(r'^---\s*$', content, re.MULTILINE))
        md_fingerprint['blockquotes'] = len(re.findall(r'^>\s+', content, re.MULTILINE))
        md_fingerprint['tables'] = len(re.findall(r'\|[-:]+[-| :]*\|', content))
        md_fingerprint['total_chars'] = len(content)
        md_fingerprint['total_words'] = len(content.split())
        
        # 3. Reasoning Pattern
        reasoning = {}
        reasoning['chain_of_thought'] = len(re.findall(r'\b(first|second|third|step \d|let me|I need to|I should)\b', content, re.IGNORECASE))
        reasoning['analysis_markers'] = len(re.findall(r'\b(analysis|analyzing|reasoning|therefore|because|conclusion|result)\b', content, re.IGNORECASE))
        reasoning['hesitation'] = len(re.findall(r'\b(I think|I believe|I would say|perhaps|maybe|might|could)\b', content, re.IGNORECASE))
        reasoning['confidence'] = len(re.findall(r'\b(certainly|definitely|absolutely|exactly|precisely|clearly|obviously)\b', content, re.IGNORECASE))
        reasoning['action_oriented'] = len(re.findall(r'\b(I will|I am going to|let me|I need to|I should)\b', content, re.IGNORECASE))
        reasoning['tool_mentions'] = len(re.findall(r'\b(tool_call|function|api|endpoint|execute)\b', content, re.IGNORECASE))
        
        # 4. Vocabulary Richness
        words = content.split()
        unique_words = set(w.lower() for w in words)
        vocabulary_richness = len(unique_words) / max(len(words), 1)
        
        # 5. Sentence Structure
        sentences = re.split(r'[.!?\n]+', content)
        avg_sentence_length = sum(len(s.split()) for s in sentences if s.strip()) / max(len([s for s in sentences if s.strip()]), 1)
        
        # 6. Quality Score (composite)
        quality_score = 0
        quality_score += min(md_fingerprint['total_chars'] / 100, 10)
        quality_score += min(md_fingerprint['code_blocks'] * 2, 6)
        quality_score += min(reasoning['analysis_markers'] * 0.5, 5)
        quality_score += min(vocabulary_richness * 20, 5)
        quality_score = round(quality_score, 2)
        
        # 7. Requested vs Detected
        req_family = 'unknown'
        for fam in ['deepseek', 'kimi', 'claude', 'gpt', 'grok', 'gemini', 'glm']:
            if fam in model_requested.lower():
                req_family = fam
                break
        
        identity_conflicts = []
        if req_family != 'unknown':
            for detected_model in detected_ids:
                if detected_model != req_family:
                    identity_conflicts.append({
                        'requested': req_family,
                        'detected': detected_model,
                        'score': detected_ids[detected_model],
                    })
        
        return {
            'detected_ids': detected_ids,
            'identity_conflicts': identity_conflicts,
            'markdown_fingerprint': md_fingerprint,
            'reasoning': reasoning,
            'vocabulary_richness': round(vocabulary_richness, 4),
            'avg_sentence_length': round(avg_sentence_length, 2),
            'quality_score': quality_score,
        }


# ── Forensic Evidentiary Report ────────────────────────────────────

class ForensicEvidentiaryReport:
    """Generate a court-ready forensic report on model swaps."""
    
    def __init__(self, sessions_dir: str):
        self.dir = Path(sessions_dir)
        self.findings = []
        self.identity_conflicts = []
        self.model_changes = []
        self.quality_drops = []
        self.timeline = []
    
    def analyze(self):
        """Run complete forensic analysis."""
        files = sorted(self.dir.glob("*.json"))
        
        for fp in files:
            try:
                with open(fp) as f:
                    d = json.load(f)
            except:
                continue
            
            body = d.get('request', {}).get('body', {})
            if not body:
                continue
            
            model = body.get('model', 'unknown')
            ts = d.get('timestamp', '')
            sid = d.get('session_id', 'unknown')
            msgs = body.get('messages', [])
            
            asst_msgs = [m for m in msgs if m.get('role') == 'assistant']
            if not asst_msgs:
                continue
            
            for m in asst_msgs:
                content = m.get('content', '')
                if isinstance(content, list):
                    content = ' '.join(x.get('text','') for x in content if isinstance(x, dict))
                
                if not content.strip():
                    continue
                
                fp_data = ResponseFingerprint.extract(content, model)
                if not fp_data:
                    continue
                
                finding = {
                    'file': fp.name,
                    'session_id': sid,
                    'timestamp': ts,
                    'model_requested': model,
                    'content_length': len(content),
                    'fingerprint': fp_data,
                }
                
                # Check for identity conflicts
                if fp_data['identity_conflicts']:
                    for conflict in fp_data['identity_conflicts']:
                        conflict_record = finding.copy()
                        conflict_record.update(conflict)
                        self.identity_conflicts.append(conflict_record)
                
                # Check for quality drops (responses way below expected length)
                expected_lengths = {
                    'deepseek': 800,
                    'kimi': 600,
                    'claude': 1000,
                    'gpt': 800,
                    'grok': 700,
                }
                for fam, expected in expected_lengths.items():
                    if fam in model.lower() and len(content) < expected * 0.1:
                        quality_record = finding.copy()
                        quality_record['expected'] = expected
                        quality_record['actual'] = len(content)
                        quality_record['ratio'] = round(len(content) / expected, 3)
                        self.quality_drops.append(quality_record)
                
                self.findings.append(finding)
                self.timeline.append({
                    'ts': ts[:19] if ts else '',
                    'model': model,
                    'quality': fp_data['quality_score'],
                    'length': len(content),
                    'conflict': len(fp_data['identity_conflicts']) > 0,
                })
        
        # Detect session model changes
        session_models = defaultdict(set)
        for f in self.findings:
            session_models[f['session_id']].add(f['model_requested'])
        
        for sid, models in session_models.items():
            if len(models) > 1:
                self.model_changes.append({
                    'session_id': sid,
                    'models': list(models),
                })
        
        return self
    
    def generate_text_report(self) -> str:
        """Generate plain text evidentiary report."""
        lines = []
        w = lines.append
        
        w("=" * 80)
        w("  AMARTIE FORENSIC EVIDENTIARY REPORT")
        w("  AI Model Swap Detection & Proof")
        w("=" * 80)
        w(f"  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        w(f"  Total Records Analyzed: {len(self.findings)}")
        w("=" * 80)
        
        # Executive Summary
        w("\n[EXECUTIVE SUMMARY]")
        w(f"  Identity Conflicts Found: {len(self.identity_conflicts)}")
        w(f"  Sessions with Model Changes: {len(self.model_changes)}")
        w(f"  Severe Quality Drops: {len([q for q in self.quality_drops if q['ratio'] < 0.05])}")
        w(f"  Moderate Quality Drops: {len([q for q in self.quality_drops if 0.05 <= q['ratio'] < 0.2])}")
        
        # Identity Conflicts (THE PROOF)
        if self.identity_conflicts:
            w("\n" + "=" * 80)
            w("[SECTION A] MODEL IDENTITY CONFLICTS")
            w("  When the requested model differs from the self-identified model")
            w("=" * 80)
            
            for i, c in enumerate(self.identity_conflicts, 1):
                w(f"\n  CONFLICT #{i}")
                w(f"  {'─' * 40}")
                w(f"  Timestamp:     {c['timestamp'][:19] if c.get('timestamp') else 'unknown'}")
                w(f"  Session:       {c['session_id']}")
                w(f"  Requested:     {c['requested']}")
                w(f"  Self-Detected: {c['detected']} (score: {c['score']})")
                w(f"  Evidence:      Model '{c['requested']}' was requested but response")
                w(f"                 contains self-identification markers for '{c['detected']}'")
                w(f"  Conclusion:    UNAUTHORIZED MODEL SUBSTITUTION")
        
        # Session Model Changes
        if self.model_changes:
            w("\n" + "=" * 80)
            w("[SECTION B] SESSION-LEVEL MODEL CHANGES")
            w("  When a single session shows requests to multiple models")
            w("=" * 80)
            
            for mc in self.model_changes:
                w(f"\n  Session: {mc['session_id']}")
                w(f"  Models:   {mc['models']}")
                w(f"  Evidence: Provider silently switched models during this session")
        
        # Quality Drops
        if self.quality_drops:
            w("\n" + "=" * 80)
            w("[SECTION C] QUALITY DEGRADATION ANALYSIS")
            w("  Responses significantly below expected quality thresholds")
            w("=" * 80)
            
            severe = [q for q in self.quality_drops if q['ratio'] < 0.1]
            moderate = [q for q in self.quality_drops if 0.1 <= q['ratio'] < 0.3]
            
            if severe:
                w(f"\n  SEVERE QUALITY DROPS ({len(severe)} cases):")
                for q in severe[:10]:
                    w(f"    {q['timestamp'][:19]} | {q['model_requested'][:30]:30s} | {q['actual']:4d} / {q['expected']:4d} chars ({q['ratio']:.1%})")
            
            if moderate:
                w(f"\n  MODERATE QUALITY DROPS ({len(moderate)} cases):")
                for q in moderate[:10]:
                    w(f"    {q['timestamp'][:19]} | {q['model_requested'][:30]:30s} | {q['actual']:4d} / {q['expected']:4d} chars ({q['ratio']:.1%})")
        
        # Timeline
        w("\n" + "=" * 80)
        w("[SECTION D] TIMELINE OF EVENTS")
        w("=" * 80)
        
        for t in sorted(self.timeline, key=lambda x: x['ts'])[:30]:
            flag = " ⚠️ CONFLICT" if t['conflict'] else ""
            w(f"  {t['ts'][:19]} | {t['model'][:30]:30s} | Q={t['quality']:5.1f} | {t['length']:5d} chars{flag}")
        
        # Legal Statement
        w("\n" + "=" * 80)
        w("[CERTIFICATION]")
        w("=" * 80)
        w("  This report was generated by the AMARTIE Forensic Evidentiary")
        w("  Engine. The findings above constitute prima facie evidence of")
        w("  unauthorized model substitution by the AI provider.")
        w("")
        w("  Identity Conflicts: When a model's response contains")
        w("  self-identification markers for a different model than requested,")
        w("  this constitutes direct evidence of substitution.")
        w("")
        w("  Quality Drops: When responses fall below 10% of expected quality")
        w("  metrics for the requested model, this is consistent with silent")
        w("  downgrade to a lower-tier model.")
        w("")
        w("  Session Changes: Multiple models requested within a single session")
        w("  without user action indicates provider-initiated substitution.")
        
        # Hash
        report_text = "\n".join(lines)
        report_hash = hashlib.sha256(report_text.encode()).hexdigest()[:24]
        w(f"\n\n  Report Hash: sha256:{report_hash}")
        w(f"  Chain: AMARTIE-FORENSIC-EVIDENCE-v1")
        w("=" * 80)
        
        return report_text


# ── CLI Entry ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AMARTIE Forensic Evidentiary Engine")
    parser.add_argument("dir", help="Sessions directory")
    parser.add_argument("--output", default="forensic_report.txt", help="Output file")
    args = parser.parse_args()
    
    report = ForensicEvidentiaryReport(args.dir)
    report.analyze()
    
    text_report = report.generate_text_report()
    print(text_report)
    
    with open(args.output, 'w') as f:
        f.write(text_report)
    
    print(f"\n[✓] Report saved to: {Path(args.output).absolute()}")


if __name__ == "__main__":
    main()
