#!/usr/bin/env python3
"""
AMARTIE Daily Orchestrator
===========================
The protective layer that runs every morning.

Start Phrase: "AMARTIE"

Reviews overnight changes, checks active kanban cards,
presents prioritized tasks, dispatches ready cards,
reports with solutions and implementations.

Two modes:
- EVERYDAY USER MODE: verifies actions, blocks threats, receipts everything
- CORE PROTECTIVE LAYER: boots with HALO OS — gate is first thing that loads

Usage:
    python3 amartie_daily_orchestrator.py [--json] [--dispatch] [--quiet]
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Paths ─────────────────────────────────────────────────────

HOME = Path.home()
KANBAN_DB = HOME / ".hermes" / "kanban.db"
AMARTIE_ROOT = Path(__file__).resolve().parent.parent
CRON_JOBS_FILE = HOME / ".hermes" / "cron" / "jobs.json"
REPORTS_DIR = AMARTIE_ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


# ── Colors (terminal output) ──────────────────────────────────

class C:
    R = "\033[0m"
    B = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GRN = "\033[92m"
    YLW = "\033[93m"
    BLU = "\033[94m"
    MAG = "\033[95m"
    CYN = "\033[96m"
    WHT = "\033[97m"
    GRY = "\033[90m"


def colored(text: str, color: str) -> str:
    return f"{color}{text}{C.R}"


# ── Utility ────────────────────────────────────────────────────

def now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def now_local() -> datetime.datetime:
    return datetime.datetime.now().astimezone()


def today_str() -> str:
    return now_local().strftime("%Y-%m-%d")


def time_ago(ts: int) -> str:
    if not ts:
        return "never"
    delta = time.time() - ts
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta/60)}m ago"
    if delta < 86400:
        return f"{int(delta/3600)}h ago"
    return f"{int(delta/86400)}d ago"


def run_cmd(cmd: str, timeout: int = 30) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


# ── Repo Scanner ──────────────────────────────────────────────

def scan_repo(repo_path: Path) -> Dict[str, Any]:
    """Scan a git repo for overnight changes."""
    if not (repo_path / ".git").exists():
        return {"path": str(repo_path), "git": False}

    rc, log_out, _ = run_cmd(
        "git log --since='24 hours ago' --oneline --no-merges 2>/dev/null",
        timeout=10
    )
    recent_commits = log_out.split("\n") if rc == 0 and log_out else []

    rc2, status_out, _ = run_cmd("git status --porcelain 2>/dev/null", timeout=10)
    uncommitted = [l for l in status_out.split("\n") if l.strip()] if rc2 == 0 else []

    rc3, branch_out, _ = run_cmd("git branch --show-current 2>/dev/null", timeout=10)
    branch = branch_out.strip() if rc3 == 0 else "unknown"

    rc4, remote_out, _ = run_cmd("git remote -v 2>/dev/null | head -2", timeout=10)
    remotes = remote_out.split("\n") if rc4 == 0 and remote_out else []

    # Check for untracked files
    rc5, untracked_out, _ = run_cmd("git ls-files --others --exclude-standard 2>/dev/null | head -20", timeout=10)
    untracked = untracked_out.split("\n") if rc5 == 0 and untracked_out else []

    return {
        "path": str(repo_path),
        "git": True,
        "branch": branch,
        "remotes": remotes,
        "recent_commits": recent_commits,
        "uncommitted": uncommitted,
        "untracked": untracked,
        "clean": len(uncommitted) == 0 and len(untracked) == 0,
    }


def scan_repos() -> List[Dict[str, Any]]:
    """Scan all known repos for overnight activity."""
    repos = []
    known_repos = [
        AMARTIE_ROOT,
        HOME / "HALO_DESIGN_CORE",
    ]

    # Find additional repos in home (shallow scan)
    for p in HOME.iterdir():
        if p.is_dir() and (p / ".git").exists() and p not in known_repos:
            if any(x in p.name.lower() for x in ["oracle", "denial", "halo", "amartie", "hermes"]):
                known_repos.append(p)

    for repo_path in known_repos:
        if repo_path.exists():
            repos.append(scan_repo(repo_path))

    return repos


# ── Kanban Scanner ────────────────────────────────────────────

def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(KANBAN_DB))
    conn.row_factory = sqlite3.Row
    return conn


def scan_kanban() -> Dict[str, Any]:
    """Read all active kanban cards and summarize status."""
    if not KANBAN_DB.exists():
        return {"error": "kanban.db not found"}

    conn = db_connect()
    cur = conn.cursor()

    # All non-done, non-archived cards
    cur.execute("""
        SELECT id, title, body, assignee, status, priority,
               created_at, started_at, completed_at, last_failure_error
        FROM tasks
        WHERE status NOT IN ('done', 'archived')
        ORDER BY priority DESC, created_at ASC
    """)
    active_cards = [dict(r) for r in cur.fetchall()]

    # Count by status
    cur.execute("SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status")
    status_counts = {r["status"]: r["cnt"] for r in cur.fetchall()}

    # Ready cards (can be dispatched)
    cur.execute("""
        SELECT id, title, assignee, priority
        FROM tasks
        WHERE status = 'ready'
        ORDER BY priority DESC
    """)
    ready_cards = [dict(r) for r in cur.fetchall()]

    # Running cards
    cur.execute("""
        SELECT id, title, assignee, started_at
        FROM tasks
        WHERE status = 'running'
    """)
    running_cards = [dict(r) for r in cur.fetchall()]

    # Blocked cards
    cur.execute("""
        SELECT id, title, assignee
        FROM tasks
        WHERE status = 'blocked'
    """)
    blocked_cards = [dict(r) for r in cur.fetchall()]

    # Recent completions (last 24h)
    day_ago = int(time.time()) - 86400
    cur.execute("""
        SELECT id, title, assignee, completed_at
        FROM tasks
        WHERE status = 'done' AND completed_at > ?
        ORDER BY completed_at DESC
    """, (day_ago,))
    recent_completions = [dict(r) for r in cur.fetchall()]

    # Recent failures (last 24h)
    cur.execute("""
        SELECT id, title, assignee, last_failure_error
        FROM tasks
        WHERE last_failure_error IS NOT NULL
        AND started_at > ?
        ORDER BY started_at DESC
        LIMIT 10
    """, (day_ago,))
    recent_failures = [dict(r) for r in cur.fetchall()]

    # Comments on active cards (last 24h)
    cur.execute("""
        SELECT tc.task_id, tc.body, tc.created_at
        FROM task_comments tc
        JOIN tasks t ON tc.task_id = t.id
        WHERE t.status NOT IN ('done', 'archived')
        AND tc.created_at > ?
        ORDER BY tc.created_at DESC
        LIMIT 20
    """, (day_ago,))
    recent_comments = [dict(r) for r in cur.fetchall()]

    conn.close()

    return {
        "active_count": len(active_cards),
        "status_counts": status_counts,
        "active_cards": active_cards,
        "ready_cards": ready_cards,
        "running_cards": running_cards,
        "blocked_cards": blocked_cards,
        "recent_completions": recent_completions,
        "recent_failures": recent_failures,
        "recent_comments": recent_comments,
    }


# ── Cron Health Scanner ───────────────────────────────────────

def scan_cron() -> Dict[str, Any]:
    """Check cron job health."""
    if not CRON_JOBS_FILE.exists():
        return {"error": "jobs.json not found"}

    with open(CRON_JOBS_FILE) as f:
        data = json.load(f)

    jobs = data.get("jobs", [])
    total = len(jobs)
    enabled = sum(1 for j in jobs if j.get("enabled"))
    paused = sum(1 for j in jobs if j.get("state") == "paused")
    failing = sum(1 for j in jobs if j.get("failure_streak", 0) > 3)
    overdue = 0
    critical_failing = []

    for j in jobs:
        streak = j.get("failure_streak", 0)
        last_err = j.get("last_error", "")
        if streak > 3 and j.get("enabled"):
            critical_failing.append({
                "id": j["id"],
                "name": j["name"],
                "streak": streak,
                "last_error": last_err[:120] if last_err else "",
            })

    return {
        "total": total,
        "enabled": enabled,
        "paused": paused,
        "failing_streak_3plus": failing,
        "critical_failing": critical_failing,
    }


# ── Systemd Service Scanner ───────────────────────────────────

def scan_services() -> List[Dict[str, str]]:
    """Check systemd user services."""
    rc, out, _ = run_cmd(
        "systemctl --user list-units --type=service --state=running,failed --no-pager --plain 2>/dev/null | head -30",
        timeout=10
    )
    services = []
    if rc == 0 and out:
        for line in out.split("\n")[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 4:
                services.append({
                    "unit": parts[0],
                    "load": parts[1],
                    "active": parts[2],
                    "sub": parts[3],
                    "description": " ".join(parts[4:]) if len(parts) > 4 else "",
                })
    return services


# ── Security Quick-Check ──────────────────────────────────────

def security_check() -> Dict[str, Any]:
    """Run lightweight security checks."""
    issues = []

    # Check SSH authorized_keys
    auth_keys = HOME / ".ssh" / "authorized_keys"
    if auth_keys.exists():
        rc, keys_out, _ = run_cmd(f"wc -l {auth_keys}", timeout=5)
        if rc == 0:
            n_keys = int(keys_out.split()[0])
            if n_keys > 5:
                issues.append(f"SSH: {n_keys} authorized keys (review recommended)")

    # Check for world-writable files in sensitive dirs
    rc, ww_out, _ = run_cmd(
        f"find {HOME}/.hermes -maxdepth 1 -perm -o+w -type f 2>/dev/null | head -5",
        timeout=10
    )
    if rc == 0 and ww_out:
        issues.append(f"World-writable files in .hermes: {ww_out.count(chr(10))+1}")

    # Check firewall status
    rc, fw_out, _ = run_cmd("sudo ufw status 2>/dev/null || iptables -L -n 2>/dev/null | head -5", timeout=5)
    if rc == 0 and "inactive" in fw_out.lower():
        issues.append("Firewall appears inactive")

    # Check for recent failed login attempts
    rc, login_out, _ = run_cmd(
        "lastb --since='24 hours ago' 2>/dev/null | grep -v 'btmp' | head -5",
        timeout=5
    )
    if rc == 0 and login_out:
        failed_count = len(login_out.split("\n"))
        if failed_count > 3:
            issues.append(f"Recent failed login attempts: {failed_count}")

    return {
        "issues": issues,
        "status": "ALERT" if issues else "OK",
    }


# ── Prioritizer ───────────────────────────────────────────────

def prioritize(kanban: Dict[str, Any], security: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate prioritized task list."""
    tasks = []

    # Security issues first
    if security.get("status") == "ALERT":
        for issue in security.get("issues", []):
            tasks.append({
                "priority": "P0-CRITICAL",
                "category": "security",
                "title": issue,
                "action": "review-and-fix",
            })

    # Failing cron jobs
    cron = kanban.get("_cron", {})
    for failing in cron.get("critical_failing", []):
        tasks.append({
            "priority": "P1-HIGH",
            "category": "cron",
            "title": f"Fix failing cron: {failing['name']} (streak={failing['streak']})",
            "action": "investigate",
            "meta": failing,
        })

    # Blocked cards
    for card in kanban.get("blocked_cards", []):
        tasks.append({
            "priority": "P1-HIGH",
            "category": "blocked",
            "title": f"Unblock: {card['title']}",
            "assignee": card.get("assignee", ""),
            "action": "unblock",
            "card_id": card["id"],
        })

    # Ready cards (dispatchable)
    for card in kanban.get("ready_cards", []):
        tasks.append({
            "priority": "P2-MEDIUM",
            "category": "ready",
            "title": f"Dispatch: {card['title']}",
            "assignee": card.get("assignee", ""),
            "action": "dispatch",
            "card_id": card["id"],
        })

    # Todo cards with assignees
    for card in kanban.get("active_cards", []):
        if card.get("status") == "todo" and card.get("assignee"):
            tasks.append({
                "priority": "P3-LOW",
                "category": "backlog",
                "title": card["title"],
                "assignee": card.get("assignee", ""),
                "action": "promote-to-ready",
                "card_id": card["id"],
            })

    return tasks


# ── Report Generator ──────────────────────────────────────────

def generate_report(
    repos: List[Dict],
    kanban: Dict,
    cron: Dict,
    services: List[Dict],
    security: Dict,
    tasks: List[Dict],
) -> Dict[str, Any]:
    """Generate the full daily report."""
    report = {
        "meta": {
            "version": "1.0.0",
            "generated_at": now_utc().isoformat(),
            "generated_local": now_local().isoformat(),
            "orchestrator": "AMARTIE Daily Orchestrator",
            "mode": "EVERYDAY USER MODE",
        },
        "summary": {
            "repos_scanned": len(repos),
            "active_cards": kanban.get("active_count", 0),
            "ready_to_dispatch": len(kanban.get("ready_cards", [])),
            "blocked_cards": len(kanban.get("blocked_cards", [])),
            "cron_total": cron.get("total", 0),
            "cron_failing": cron.get("failing_streak_3plus", 0),
            "security_status": security.get("status", "UNKNOWN"),
            "security_issues": len(security.get("issues", [])),
            "prioritized_tasks": len(tasks),
        },
        "repos": repos,
        "kanban": kanban,
        "cron": cron,
        "services": services,
        "security": security,
        "prioritized_tasks": tasks,
    }

    # Compute report hash
    report_json = json.dumps(report, sort_keys=True, default=str)
    report["meta"]["report_hash"] = hashlib.sha256(report_json.encode()).hexdigest()[:16]

    return report


# ── Output Formatters ─────────────────────────────────────────

def format_terminal(report: Dict[str, Any]) -> str:
    """Format report for terminal output."""
    lines = []
    s = report["summary"]
    meta = report["meta"]

    lines.append("")
    lines.append(colored("=" * 60, C.CYN))
    colored_title = colored("  AMARTIE DAILY ORCHESTRATOR", C.B + C.CYN)
    lines.append(colored_title)
    lines.append(colored(f"  {meta['generated_local']}", C.GRY))
    lines.append(colored("=" * 60, C.CYN))
    lines.append("")

    # Summary box
    lines.append(colored("  ┌─ SUMMARY ───────────────────────────────────┐", C.BLU))

    sec_color = C.RED if s["security_status"] == "ALERT" else C.GRN
    lines.append(colored("  │", C.BLU) + f" Security:     {colored(s['security_status'], sec_color)}")
    lines.append(colored("  │", C.BLU) + f" Active Cards: {colored(str(s['active_cards']), C.YLW)}")
    lines.append(colored("  │", C.BLU) + f" Ready:        {colored(str(s['ready_to_dispatch']), C.GRN)}")
    lines.append(colored("  │", C.BLU) + f" Blocked:      {colored(str(s['blocked_cards']), C.RED)}")
    lines.append(colored("  │", C.BLU) + f" Cron Failing: {colored(str(s['cron_failing']), C.RED if s['cron_failing'] else C.GRN)}")
    lines.append(colored("  │", C.BLU) + f" Repos:        {s['repos_scanned']}")
    lines.append(colored("  └─────────────────────────────────────────────┘", C.BLU))
    lines.append("")

    # Security issues
    if report["security"]["issues"]:
        lines.append(colored("  ⚠ SECURITY ALERTS:", C.RED))
        for issue in report["security"]["issues"]:
            lines.append(colored(f"    • {issue}", C.YLW))
        lines.append("")

    # Prioritized tasks
    if report["prioritized_tasks"]:
        lines.append(colored("  📋 PRIORITIZED TASK LIST:", C.B + C.WHT))
        lines.append("")
        for i, task in enumerate(report["prioritized_tasks"], 1):
            pri = task["priority"]
            if "CRITICAL" in pri:
                pri_colored = colored(pri, C.B + C.RED)
            elif "HIGH" in pri:
                pri_colored = colored(pri, C.RED)
            elif "MEDIUM" in pri:
                pri_colored = colored(pri, C.YLW)
            else:
                pri_colored = colored(pri, C.GRY)

            cat_colored = colored(f"[{task['category']}]", C.CYN)
            lines.append(f"    {i:2}. {pri_colored} {cat_colored} {task['title']}")
            if task.get("assignee"):
                lines.append(f"        → assignee: {colored(task['assignee'], C.GRN)}")
        lines.append("")

    # Repo activity
    if report["repos"]:
        lines.append(colored("  📁 REPO ACTIVITY (24h):", C.B + C.WHT))
        for repo in report["repos"]:
            path = repo.get("path", "?")
            name = Path(path).name
            if repo.get("recent_commits"):
                lines.append(f"    {colored(name, C.GRN)} ({repo.get('branch', '?')}):")
                for c in repo["recent_commits"][:5]:
                    lines.append(f"      • {c[:70]}")
            elif repo.get("git"):
                lines.append(f"    {colored(name, C.DIM)} — no recent commits")
            if repo.get("uncommitted"):
                uncommitted_count = len(repo["uncommitted"])
                lines.append(f"      {colored(f'⚠ {uncommitted_count} uncommitted', C.YLW)}")
        lines.append("")

    # Kanban status
    if report["kanban"].get("status_counts"):
        lines.append(colored("  📊 KANBAN STATUS:", C.B + C.WHT))
        for status, count in sorted(report["kanban"]["status_counts"].items()):
            if status in ("done", "archived"):
                color = C.GRY
            elif status == "running":
                color = C.YLW
            elif status == "blocked":
                color = C.RED
            else:
                color = C.WHT
            lines.append(f"    {colored(status, color)}: {count}")
        lines.append("")

    # Cron failing
    if report["cron"].get("critical_failing"):
        lines.append(colored("  🔧 CRON FAILING:", C.RED))
        for j in report["cron"]["critical_failing"]:
            lines.append(f"    • {j['name']} — streak={j['streak']}")
            if j.get("last_error"):
                lines.append(f"      err: {j['last_error'][:80]}")
        lines.append("")

    # Ready cards detail
    if report["kanban"].get("ready_cards"):
        lines.append(colored("  🚀 READY TO DISPATCH:", C.B + C.GRN))
        for card in report["kanban"]["ready_cards"]:
            lines.append(f"    • {card['title']} → {colored(card.get('assignee', 'unassigned'), C.CYN)}")
        lines.append("")

    lines.append(colored(f"  Report hash: {meta['report_hash']}", C.GRY))
    lines.append(colored("=" * 60, C.CYN))
    lines.append("")

    return "\n".join(lines)


# ── Save Report ────────────────────────────────────────────────

def save_report(report: Dict[str, Any]) -> Path:
    """Save report to disk. Purge reports older than 30 days."""
    today = today_str()
    report_path = REPORTS_DIR / f"daily_{today}_{report['meta']['report_hash']}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Purge old reports (keep 30 days)
    cutoff = time.time() - (30 * 86400)
    for f in REPORTS_DIR.glob("daily_*.json"):
        if f.stat().st_mtime < cutoff:
            f.unlink()

    return report_path


# ── Main Orchestrator ──────────────────────────────────────────

def run_orchestrator(args: argparse.Namespace) -> Dict[str, Any]:
    """Main orchestrator logic."""

    # 1. Scan repos
    repos = scan_repos()

    # 2. Scan kanban
    kanban = scan_kanban()

    # 3. Scan cron health
    cron = scan_cron()
    kanban["_cron"] = cron

    # 4. Scan systemd services
    services = scan_services()

    # 5. Security check
    security = security_check()

    # 6. Prioritize tasks
    tasks = prioritize(kanban, security)

    # 7. Generate report
    report = generate_report(repos, kanban, cron, services, security, tasks)

    # 8. Save report
    report_path = save_report(report)
    report["meta"]["saved_to"] = str(report_path)

    return report


def dispatch_ready_cards(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Dispatch ready cards via hermes kanban dispatch (requires CLI)."""
    dispatched = []
    for task in report.get("prioritized_tasks", []):
        if task.get("action") == "dispatch" and task.get("card_id"):
            card_id = task["card_id"]
            print(f"  Dispatching: {card_id} — {task['title']}")
            rc, out, err = run_cmd(f"hermes kanban dispatch {card_id}", timeout=30)
            dispatched.append({
                "card_id": card_id,
                "rc": rc,
                "output": out,
                "error": err,
            })
    return dispatched


def main():
    parser = argparse.ArgumentParser(
        description="AMARTIE Daily Orchestrator — morning protective layer"
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-essential output")
    parser.add_argument("--no-save", action="store_true", help="Don't save report to disk")
    parser.add_argument("--dispatch", action="store_true", help="Auto-dispatch ready cards via hermes kanban")
    args = parser.parse_args()

    report = run_orchestrator(args)

    if args.dispatch:
        print(colored("\n  🚀 DISPATCHING READY CARDS...\n", C.B + C.GRN))
        results = dispatch_ready_cards(report)
        report["dispatch_results"] = results
        for r in results:
            status = colored("OK", C.GRN) if r["rc"] == 0 else colored("FAIL", C.RED)
            print(f"    {r['card_id']}: {status}")

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        output = format_terminal(report)
        if not args.quiet:
            print(output)
        else:
            # Quiet mode: just the summary line
            s = report["summary"]
            sec = s["security_status"]
            print(
                f"AMARTIE {today_str()}: "
                f"security={sec} "
                f"cards={s['active_cards']} "
                f"ready={s['ready_to_dispatch']} "
                f"blocked={s['blocked_cards']} "
                f"cron_failing={s['cron_failing']} "
                f"hash={report['meta']['report_hash']}"
            )


if __name__ == "__main__":
    main()
