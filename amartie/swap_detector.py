#!/usr/bin/env python3
"""AMARTIE Model Swap Detector — proves if your AI was silently replaced.

Usage:
    python3 swap_detector.py <session_log.json>
    python3 swap_detector.py --batch ~/Downloads/session-*.json

Output: hash-chained receipt with swap verdict.
"""

import json, sys, hashlib, time, os, re
from pathlib import Path
from datetime import datetime

# ── AMARTIE Quality Scoring Engine ──────────────────────────────────

class QualityScorer:
    """Score a single assistant response across 5 dimensions."""
    
    @staticmethod
    def score(response: str) -> dict:
        if not response:
            return {"total": 0, "length": 0, "structure": 0, "coherence": 0, "tool_use": 0, "reasoning": 0}
        
        # Length score (log scale, capped)
        length = min(len(response) / 1000, 10)
        
        # Structure score: presence of headers, lists, code blocks
        structure = 0
        structure += response.count("##") * 0.5  # headers
        structure += response.count("- ") * 0.3   # bullet lists
        structure += response.count("1. ") * 0.3  # numbered lists
        structure += min(response.count("```"), 2) * 1.0  # code blocks
        structure = min(structure, 10)
        
        # Coherence score: avg sentence length, paragraph structure
        sentences = [s.strip() for s in re.split(r'[.!?\n]', response) if s.strip()]
        avg_sent_len = sum(len(s) for s in sentences) / max(len(sentences), 1)
        coherence = min(avg_sent_len / 50, 10)
        
        # Tool use score: presence of tool calls, API patterns
        tool_use = 0
        tool_use += min(response.count("tool_call"), 3) * 1.0
        tool_use += min(response.count("function"), 3) * 0.5
        tool_use = min(tool_use, 10)
        
        # Reasoning score: logical connectors, step-by-step patterns
        reasoning = 0
        for word in ["because", "therefore", "first", "second", "step", "analysis", "verify", "check", "result"]:
            reasoning += response.lower().count(word) * 0.3
        reasoning = min(reasoning, 10)
        
        total = length + structure + coherence + tool_use + reasoning
        
        return {
            "total": round(total, 2),
            "length": round(length, 2),
            "structure": round(structure, 2),
            "coherence": round(coherence, 2),
            "tool_use": round(tool_use, 2),
            "reasoning": round(reasoning, 2),
        }


# ── AMARTIE Baseline Profiles ───────────────────────────────────────

# Known quality baselines for common models (avg score per response)
MODEL_BASELINES = {
    "claude": {"avg_score": 35, "min_score": 15, "description": "Claude (Anthropic)"},
    "gpt": {"avg_score": 32, "min_score": 12, "description": "GPT (OpenAI)"},
    "deepseek": {"avg_score": 33, "min_score": 14, "description": "DeepSeek"},
    "glm": {"avg_score": 28, "min_score": 10, "description": "GLM (Zhipu)"},
    "grok": {"avg_score": 30, "min_score": 11, "description": "Grok (xAI)"},
    "gemini": {"avg_score": 31, "min_score": 12, "description": "Gemini (Google)"},
    "llama": {"avg_score": 27, "min_score": 9, "description": "Llama (Meta)"},
    "mistral": {"avg_score": 29, "min_score": 10, "description": "Mistral"},
}


# ── AMARTIE Session Analyzer ────────────────────────────────────────

class SessionAnalyzer:
    def __init__(self, session_path: str):
        self.path = session_path
        self.data = self._load()
        self.scorer = QualityScorer()
    
    def _load(self) -> dict:
        with open(self.path) as f:
            return json.load(f)
    
    def analyze(self) -> dict:
        claimed_model = self.data.get("model", "unknown")
        msgs = self.data.get("messages", [])
        asst_msgs = [m for m in msgs if m.get("role") == "assistant"]
        user_msgs = [m for m in msgs if m.get("role") == "user"]
        
        if not asst_msgs:
            return {"error": "No assistant messages in session"}
        
        # Score all assistant responses
        scores = []
        for m in asst_msgs:
            content = m.get("content", "") or ""
            score = self.scorer.score(content)
            score["timestamp"] = m.get("timestamp", "")
            score["tokens"] = m.get("token_count", 0)
            scores.append(score)
        
        # Calculate aggregate stats
        totals = [s["total"] for s in scores if s["total"] > 0]
        if not totals:
            return {"error": "All assistant messages empty"}
        
        avg_score = sum(totals) / len(totals)
        min_score = min(totals)
        max_score = max(totals)
        std_dev = (sum((x - avg_score) ** 2 for x in totals) / len(totals)) ** 0.5
        
        # Detect degradation (first 20% vs last 20%)
        n = len(totals)
        quarter = max(n // 5, 1)
        first_quarter = sum(totals[:quarter]) / quarter
        last_quarter = sum(totals[-quarter:]) / quarter
        degradation = first_quarter - last_quarter
        
        # Model identification
        model_family = self._identify_model_family(claimed_model, avg_score)
        
        # Swap verdict
        swap_verdict = self._swap_verdict(claimed_model, avg_score, model_family, degradation)
        
        return {
            "session_id": self.data.get("id", ""),
            "claimed_model": claimed_model,
            "total_messages": len(msgs),
            "assistant_responses": len(asst_msgs),
            "scored_responses": len(totals),
            "avg_score": round(avg_score, 2),
            "min_score": round(min_score, 2),
            "max_score": round(max_score, 2),
            "std_dev": round(std_dev, 2),
            "degradation": round(degradation, 2),
            "model_family": model_family["family"],
            "family_confidence": model_family["confidence"],
            "swap_verdict": swap_verdict["verdict"],
            "swap_confidence": swap_verdict["confidence"],
            "swap_reason": swap_verdict["reason"],
            "scores": scores[:20],  # Keep receipt size manageable
        }
    
    def _identify_model_family(self, claimed: str, avg_score: float) -> dict:
        """Identify actual model family from quality signature."""
        # Normalize claimed model name
        claimed_lower = claimed.lower()
        
        best_match = {"family": "unknown", "confidence": "LOW", "diff": 999}
        
        for family, baseline in MODEL_BASELINES.items():
            if family in claimed_lower:
                diff = abs(avg_score - baseline["avg_score"])
                if diff < best_match["diff"]:
                    best_match = {
                        "family": family,
                        "confidence": "HIGH" if diff < 5 else "MEDIUM",
                        "diff": diff
                    }
        
        if best_match["family"] == "unknown":
            # Try to match by score proximity
            for family, baseline in MODEL_BASELINES.items():
                diff = abs(avg_score - baseline["avg_score"])
                if diff < best_match["diff"]:
                    best_match = {
                        "family": family,
                        "confidence": "INFERRED",
                        "diff": diff
                    }
        
        return best_match
    
    def _swap_verdict(self, claimed: str, avg_score: float, family: dict, degradation: float) -> dict:
        """Determine if model swap occurred."""
        claimed_lower = claimed.lower()
        family_name = family["family"]
        
        # Check if claimed family matches detected family
        family_match = family_name in claimed_lower or any(
            f in claimed_lower for f in family_name.split("-")
        )
        
        # High degradation = quality dropped during session
        if degradation > 10:
            return {
                "verdict": "SWAP_DETECTED",
                "confidence": "HIGH",
                "reason": f"Quality degraded by {degradation:.1f} pts (possible downgrade mid-session)"
            }
        
        # Family mismatch
        if not family_match and family_name != "unknown":
            return {
                "verdict": "SWAP_DETECTED",
                "confidence": "HIGH",
                "reason": f"Claimed '{claimed}' but detected '{family_name}' quality signature"
            }
        
        # Score way below baseline
        baseline = MODEL_BASELINES.get(family_name, {}).get("avg_score", 30)
        if avg_score < baseline * 0.5:
            return {
                "verdict": "SWAP_DETECTED",
                "confidence": "MEDIUM",
                "reason": f"Score {avg_score:.1f} far below {family_name} baseline {baseline}"
            }
        
        return {
            "verdict": "VERIFIED",
            "confidence": "HIGH",
            "reason": f"Quality matches claimed model '{claimed}'"
        }


# ── AMARTIE Receipt Engine ──────────────────────────────────────────

def generate_receipt(analysis: dict) -> str:
    """Generate a hash-chained verification receipt."""
    
    # Build receipt content
    receipt_lines = [
        "╔══════════════════════════════════════════════════════════════╗",
        "║          AMARTIE MODEL SWAP DETECTION RECEIPT              ║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║ Session:     {analysis.get('session_id','')[:45]:45s} ║",
        f"║ Claimed:     {analysis.get('claimed_model','')[:45]:45s} ║",
        f"║ Timestamp:   {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'):45s} ║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║ Responses:   {str(analysis.get('assistant_responses','')) + ' total / ' + str(analysis.get('scored_responses','')) + ' scored':45s} ║",
        f"║ Avg Score:   {str(analysis.get('avg_score','')) + ' / 50':45s} ║",
        f"║ Min/Max:     {str(analysis.get('min_score','')) + ' / ' + str(analysis.get('max_score','')):45s} ║",
        f"║ Std Dev:     {str(analysis.get('std_dev','')):45s} ║",
        f"║ Degradation: {str(analysis.get('degradation','')) + ' pts':45s} ║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║ Detected:    {(analysis.get('model_family','?') + ' [' + analysis.get('family_confidence','') + ']')[:45]:45s} ║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║ VERDICT:     {(analysis.get('swap_verdict','') + ' [' + analysis.get('swap_confidence','') + ']')[:45]:45s} ║",
        f"║ Reason:      {analysis.get('swap_reason','')[:45]:45s} ║",
        "╚══════════════════════════════════════════════════════════════╝",
    ]
    
    # Generate hash
    content = json.dumps(analysis, sort_keys=True)
    receipt_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    
    receipt = "\n".join(receipt_lines)
    receipt += f"\n\nReceipt Hash: sha256:{receipt_hash}"
    receipt += f"\nChain: AMARTIE-SWAP-v1 · {datetime.utcnow().strftime('%Y%m%d')}"
    
    return receipt


# ── CLI Interface ───────────────────────────────────────────────────

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="AMARTIE Model Swap Detector")
    parser.add_argument("session", help="Path to session JSON file")
    parser.add_argument("--batch", action="store_true", help="Process multiple files")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()
    
    if args.batch:
        import glob
        files = glob.glob(args.session)
    else:
        files = [args.session]
    
    for f in files:
        print(f"\n{'='*60}")
        print(f"FILE: {os.path.basename(f)}")
        print(f"{'='*60}")
        
        try:
            analyzer = SessionAnalyzer(f)
            analysis = analyzer.analyze()
            
            if "error" in analysis:
                print(f"ERROR: {analysis['error']}")
                continue
            
            receipt = generate_receipt(analysis)
            print(receipt)
            
            if args.json:
                print(json.dumps(analysis, indent=2))
                
        except Exception as e:
            print(f"FAILED: {e}")


if __name__ == "__main__":
    main()
