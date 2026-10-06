#!/usr/bin/env python3
"""
AMARTIE JEV 9-Judge Gate — Demo Script
Runs a live evaluation through all 9 judges with timed output for video recording.
"""

import sys
import os
import time
import json
import hashlib
from datetime import datetime, timezone

# Add repo to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from amartie.jev_gate import JEVJudgeGate, Verdict

def banner():
    print("\033[1;36m")
    print("=" * 64)
    print("  AMARTIE — JEV 9-JUDGE GATE DEMO")
    print("  Autonomous Multi-Agent Adaptive Reasoning Task Intelligence")
    print("=" * 64)
    print("\033[0m")

def print_judge(judge_id, domain, verdict, confidence, findings, tool_calls):
    v_color = "\033[1;32m" if verdict == "PASS" else "\033[1;31m"
    print(f"\033[1;33m  [{judge_id}]\033[0m \033[1;37m{domain}\033[0m")
    print(f"    Verdict:    {v_color}{verdict}\033[0m")
    print(f"    Confidence: {confidence:.2f}")
    print(f"    Tool calls: {', '.join(tool_calls)}")
    for f in findings:
        print(f"    Finding:    {f}")
    print()

def main():
    banner()

    # Initialize gate
    print("\033[1;36m[1/4] Initializing JEV 9-Judge Gate...\033[0m")
    gate = JEVJudgeGate(
        typesafe_api_key=os.environ.get("TYPESAFE_API_KEY"),
        use_layer_fallback=True,
        mock_mode=not os.environ.get("TYPESAFE_API_KEY")
    )
    print(f"  Provider: {gate.provider}")
    print(f"  Judges:   9 (J1-J9)")
    print(f"  Chain:    {'GENESIS' if not gate.receipt_chain else gate.receipt_chain[-1][:16]}")
    time.sleep(1)

    # Define test action
    print("\033[1;36m[2/4] Preparing test action...\033[0m")
    action_type = "deploy"
    action_payload = {
        "target": "amartie.com",
        "action": "publish_blog_post",
        "content": "JEV gate integration — 13x faster evaluation",
        "author": "amartie-ai",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    print(f"  Action: {action_type}")
    print(f"  Target: {action_payload['target']}")
    print(f"  Content: {action_payload['content'][:50]}...")
    time.sleep(1)

    # Run evaluation
    print("\033[1;36m[3/4] Running 9-judge evaluation...\033[0m")
    print("  " + "-" * 50)

    start_time = time.time()
    passed, receipt = gate.evaluate_action(action_type, action_payload)
    elapsed = time.time() - start_time

    # Print each judge with dramatic pause
    for v in receipt.verdicts:
        print_judge(
            v["judge_id"],
            v["domain"],
            v["verdict"],
            v["confidence"],
            v["findings"],
            v["tool_calls"]
        )
        time.sleep(0.3)

    # Results
    print("\033[1;36m[4/4] Results\033[0m")
    print("  " + "=" * 50)
    v_color = "\033[1;32m" if passed else "\033[1;31m"
    print(f"  Verdict:     {v_color}{'PASS' if passed else 'DISSENT'}\033[0m")
    print(f"  Time:        {elapsed:.3f}s")
    print(f"  Receipt:     {receipt.hash[:16]}...")
    print(f"  Previous:    {receipt.previous_hash[:16]}...")
    print(f"  Provider:    {receipt.provider}")
    print(f"  Chain OK:    {gate.verify_chain_integrity()}")
    print("  " + "=" * 50)

    # Summary
    print("\n\033[1;37m  The JEV gate evaluated this action through 9 independent judges.\033[0m")
    print("\033[1;37m  All must PASS. One DISSENT = bounce + receipt.\033[0m")
    print("\033[1;37m  Hash-chained, tamper-evident, fail-closed.\033[0m")
    print()

if __name__ == "__main__":
    main()
