import argparse
import json
import sys

from .custody import CustodyLog
from .engine import check_session
from .probes import run_all
from .receipt import write_receipt
from .replay import replay


def main():
    parser = argparse.ArgumentParser(
        prog="amartie",
        description="Check if your AI provider swapped the model you were billed for.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    check = sub.add_parser("check", help="Check a session dump for model swaps")
    check.add_argument("session", help="Path to session.json or session.jsonl")
    check.add_argument("--out", default="receipts", help="Output directory for receipts")
    check.add_argument("--json", action="store_true", help="Print mismatch JSON to stdout")
    check.add_argument("--custody", default="custody.jsonl", help="Custody log path")

    probe = sub.add_parser("probe", help="Run live probes against a provider endpoint")
    probe.add_argument("url", help="Provider chat completions URL")
    probe.add_argument("--model", required=True, help="Model string you were billed for")
    probe.add_argument("--key", default=None, help="API key (optional)")

    replay_cmd = sub.add_parser("replay", help="Verify a receipt against the raw session file")
    replay_cmd.add_argument("session", help="Path to session.json or session.jsonl")
    replay_cmd.add_argument("receipt", help="Path to the receipt JSON")

    args = parser.parse_args()

    if args.cmd == "check":
        custody = CustodyLog(args.custody)
        custody.append("check_started", {"session": args.session}, actor="CLI")
        mismatches = check_session(args.session)
        if not mismatches:
            print("CLEAN — no swaps detected.")
            custody.append("check_clean", {"session": args.session}, actor="CLI")
            return 0

        print(f"FOUND {len(mismatches)} mismatch(es):")
        for mismatch in mismatches:
            print(
                f"  billed={mismatch['billed']}  returned={mismatch['returned']}  "
                f"intent={mismatch.get('intent', 'unspecified')}  latency={mismatch['latency_ms']}ms"
            )

        path, receipt_hash = write_receipt(mismatches, args.out)
        custody.append("receipt_written", {"path": path, "hash": receipt_hash}, actor="CLI")
        print(f"Receipt written: {path}")
        print(f"Receipt hash: {receipt_hash}")
        if args.json:
            print(json.dumps(mismatches, indent=2))
        return 1

    if args.cmd == "probe":
        print(json.dumps(run_all(args.url, args.model, args.key), indent=2))
        return 0

    if args.cmd == "replay":
        ok, detail = replay(args.session, args.receipt)
        print(json.dumps(detail, indent=2))
        return 0 if ok else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
