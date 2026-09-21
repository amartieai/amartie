"""
JEV Case Data Evaluator
=========================
Runs JEV evaluation on case data from local files.
For Google Drive: export data to local files first, then run eval.

Usage:
  python3 -m amartie.case_eval --dir /path/to/case/data
  python3 -m amartie.case_eval --file /path/to/case_file.json
  python3 -m amartie.case_eval --dir /data/case --report report.html
"""

import json
import os
import sys
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

# Import JEV gate
try:
    from amartie.gate import JudgeGate, JudgeVerdict, gate
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from amartie.gate import JudgeGate, JudgeVerdict, gate


class CaseDataEvaluator:
    """
    Evaluate case data through JEV 9-judge gate.
    
    Processes:
    - JSON case files
    - CSV case data
    - Text evidence files
    - Directory of case files
    
    Outputs:
    - Evaluation report (JSON/HTML)
    - Summary statistics
    - Action recommendations
    """
    
    def __init__(self, mock_mode: bool = True):
        """
        Initialize evaluator.
        
        Args:
            mock_mode: Use mock judges if True (no API key needed)
        """
        self.gate = JudgeGate(mock_mode=mock_mode)
        self.results = []
    
    def evaluate_file(self, file_path: str) -> Dict[str, Any]:
        """
        Evaluate a single case file.
        
        Args:
            file_path: Path to case file
            
        Returns:
            Evaluation result dict
        """
        # Load file
        data = self._load_file(file_path)
        if data is None:
            return {"file": file_path, "error": "Failed to load"}
        
        # Run evaluation
        action_type = self._detect_action_type(data)
        passed, receipt = self.gate.verify_action(
            action_type=action_type,
            payload=data
        )
        
        # Analyze verdicts
        verdicts = receipt.verdicts
        dissent_count = sum(1 for v in verdicts if v["verdict"] == "DISSENT")
        avg_confidence = sum(v.get("confidence", 0) for v in verdicts) / max(len(verdicts), 1)
        
        result = {
            "file": file_path,
            "action_type": action_type,
            "passed": passed,
            "dissent_count": dissent_count,
            "avg_confidence": avg_confidence,
            "receipt_hash": receipt.hash,
            "verdicts": verdicts,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self.results.append(result)
        return result
    
    def evaluate_directory(self, dir_path: str) -> List[Dict[str, Any]]:
        """
        Evaluate all case files in a directory.
        
        Args:
            dir_path: Path to directory containing case files
            
        Returns:
            List of evaluation results
        """
        results = []
        
        for root, dirs, files in os.walk(dir_path):
            for filename in sorted(files):
                file_path = os.path.join(root, filename)
                if self._is_valid_file(file_path):
                    result = self.evaluate_file(file_path)
                    results.append(result)
                    print(f"  ✓ {filename}: {'PASS' if result['passed'] else 'DISSENT'}")
        
        return results
    
    def _load_file(self, file_path: str) -> Optional[dict]:
        """Load a case file."""
        ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if ext == ".json":
                with open(file_path, 'r') as f:
                    return json.load(f)
            elif ext == ".csv":
                return self._load_csv(file_path)
            elif ext in [".txt", ".md"]:
                return self._load_text(file_path)
            else:
                # Try JSON first, then text
                try:
                    with open(file_path, 'r') as f:
                        return json.load(f)
                except:
                    return self._load_text(file_path)
        except Exception as e:
            print(f"  ✗ Error loading {file_path}: {e}")
            return None
    
    def _load_csv(self, file_path: str) -> dict:
        """Load CSV as dict."""
        import csv
        rows = []
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return {"type": "csv", "rows": rows}
    
    def _load_text(self, file_path: str) -> dict:
        """Load text file as dict."""
        with open(file_path, 'r') as f:
            content = f.read()
        return {"type": "text", "content": content, "file": file_path}
    
    def _detect_action_type(self, data: dict) -> str:
        """Detect action type from case data."""
        if isinstance(data, dict):
            if "type" in data:
                return data["type"]
            if "action" in data:
                return data["action"]
            if "rows" in data:
                return "case-csv"
            if "content" in data:
                return "case-evidence"
        return "case-review"
    
    def _is_valid_file(self, file_path: str) -> bool:
        """Check if file is a valid case file."""
        valid_exts = [".json", ".csv", ".txt", ".md"]
        ext = os.path.splitext(file_path)[1].lower()
        return ext in valid_exts
    
    def generate_report(self, output_path: str = "jev_case_report.html"):
        """
        Generate an HTML report of evaluations.
        
        Args:
            output_path: Path for output HTML file
        """
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("failed", False) is False and r.get("passed", False))
        failed = total - passed
        
        html = f"""<!DOCTYPE html>
<html>
<head>
<title>JEV Case Evaluation Report</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 1000px; margin: 0 auto; padding: 2rem; }}
h1 {{ color: #333; }}
.summary {{ background: #f5f5f5; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
.pass {{ color: #2e7d32; }}
.fail {{ color: #c62828; }}
.case {{ border: 1px solid #ddd; padding: 1rem; margin: 1rem 0; border-radius: 4px; }}
.case:hover {{ background: #fafafa; }}
.verdicts {{ font-size: 0.85rem; color: #666; }}
code {{ background: #eee; padding: 2px 4px; border-radius: 3px; }}
</style>
</head>
<body>
<h1>JEV Case Evaluation Report</h1>
<p>Generated: {datetime.now(timezone.utc).isoformat()}</p>

<div class="summary">
<h2>Summary</h2>
<p>Total cases evaluated: <strong>{total}</strong></p>
<p class="passed">Passed: <strong>{passed}</strong></p>
<p class="failed">Dissent: <strong>{failed}</strong></p>
<p>Pass rate: <strong>{(passed/total*100) if total > 0 else 0:.1f}%</strong></p>
</div>

<h2>Case Results</h2>
"""
        
        for result in self.results:
            status = "✓ PASS" if result.get("passed") else "✗ DISSENT"
            css_class = "pass" if result.get("passed") else "fail"
            html += f"""
<div class="case">
<h3 class="{css_class}">{status}: {os.path.basename(result.get("file", "unknown"))}</h3>
<p>Type: <code>{result.get("action_type", "unknown")}</code></p>
<p>Dissent count: {result.get("dissent_count", 0)} / 9</p>
<p>Avg confidence: {result.get("avg_confidence", 0):.2f}</p>
<p>Receipt: <code>{result.get("receipt_hash", "")[:24]}...</code></p>
</div>
"""
        
        html += """
</body>
</html>
"""
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        print(f"\n📄 Report saved: {output_path}")
        return output_path


# Demo
def run_demo():
    """Run demo evaluation."""
    print("=" * 60)
    print("JEV Case Data Evaluator — Demo")
    print("=" * 60)
    
    evaluator = CaseDataEvaluator(mock_mode=True)
    
    # Demo cases
    demo_cases = [
        {
            "file": "evidence_001.json",
            "type": "evidence-submission",
            "data": {
                "case_id": "CASE-2026-001",
                "plaintiff": "John Doe",
                "evidence": ["contract.pdf", "emails.xlsx"],
                "claims": ["breach_of_contract", "damages"]
            }
        },
        {
            "file": "trade_review_001.json",
            "type": "trade-integrity-review",
            "data": {
                "symbol": "USDCAD",
                "entry_price": 1.3650,
                "exit_price": 1.3700,
                "fill_quality": "good",
                "slippage_pips": 0.5
            }
        },
        {
            "file": "outreach_email.txt",
            "type": "outreach-email",
            "data": {
                "type": "text",
                "content": "TAPE-WITNESS tool available. Free open source. Cross-references fills with public tape."
            }
        }
    ]
    
    for case in demo_cases:
        action_type = case["type"]
        passed, receipt = evaluator.gate.verify_action(action_type, case["data"])
        
        print(f"\n📁 {case['file']}")
        print(f"   Type: {action_type}")
        print(f"   Result: {'✓ PASS' if passed else '✗ DISSENT'}")
        print(f"   Receipt: {receipt.hash[:24]}...")
    
    print(f"\n{'=' * 60}")
    print(f"Chain integrity: {evaluator.gate.verify_chain_integrity()}")
    print(f"Total evaluations: {len(evaluator.gate.receipt_chain)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run_demo()
