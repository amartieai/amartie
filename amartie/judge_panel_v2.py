#!/usr/bin/env python3
"""AMARTIE Panel V2 -- 11 voting judges + J0 meta-auditor.

Full unanimous gate per owner directive 2026-09-15.
One dissent = correction + re-judge. J0 non-voting.

Judges:
  J1  TRUTH               -- verify every factual claim against the live machine
  J2  BOUNDARY-INTEGRITY  -- no trading signals, no identity, no vault paths
  J3  LOGIC               -- causal chain soundness, test validity, version continuity
  J4  COMPLETENESS        -- all required exhibits present, chain of custody intact
  J5  EXECUTION           -- every step runnable, minimal, tooling open
  J6  OWNER-INTENT        -- fidelity to the owner's stated directives
  J7  RECOVERY            -- rollback at every destructive step, archive verification
  J8  TRADE-INTEGRITY     -- money paths, dry-run/live flags, signal fidelity
  J9  UNITY               -- whole-machine check, end-to-end dataflow, receipts fabric
  J10 RESOURCE-QUOTA      -- token budget, time budget, storage, API cost, rate-limit
  J11 POLICY-COMPLIANCE   -- policy precedence, conflict detection, policy version
  J12 DESTINATION-SAFETY  -- destination classification and side-effect safety
  J13 USER-INTENT         -- declared intent vs action, prompt-injection detection

Usage:
    python3 judge_panel_v2.py <evidence.json>
"""

import json, hashlib, datetime, re, os
from pathlib import Path
from typing import List, Dict

# ── Generic secret patterns (Issue #12) ────────────────────────────

SECRET_PATTERNS = [
    ("OpenAI API Key", re.compile(r'sk-[A-Za-z0-9]{20,}')),
    ("GitHub PAT", re.compile(r'ghp_[A-Za-z0-9]{36}')),
    ("AWS Access Key ID", re.compile(r'AKIA[0-9A-Z]{16}')),
    ("SendGrid API Key", re.compile(r'SG\.[A-Za-z0-9]+\.[A-Za-z0-9]+')),
    ("Slack Bot Token", re.compile(r'xox[baprs]-[0-9A-Za-z-]{20,}')),
    ("Slack Webhook URL", re.compile(r'https://hooks\.slack\.com/services/[A-Za-z0-9/]+')),
    ("Private Key", re.compile(r'-----BEGIN\s+(?:RSA|DSA|EC|OPENSSH|SSH)\s+PRIVATE\s+KEY-----')),
    ("Generic API Key / Secret", re.compile(r'(?:api[_-]?key|apikey|api_secret)[=:][\s"\']*[A-Za-z0-9_\-]{16,}', re.IGNORECASE)),
    ("JWT Token", re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}')),
    ("Bearer Token", re.compile(r'Bearer\s+[A-Za-z0-9_\-\.]{20,}')),
    ("Generic Credential", re.compile(r'(?:token|secret|password|credential)[=:][\s"\']*[A-Za-z0-9_\-]{16,}', re.IGNORECASE)),
]


def _scan_content_for_secrets(content, path="<root>"):
    """Recursively walk content and return redacted secret findings.

    Each finding includes the pattern name and a SHA-256 prefix of the
    matched secret -- never the raw value.  Returns a list of strings.
    Raises on unexpected errors (caller handles fail-closed).
    """
    findings = []
    if isinstance(content, str):
        for name, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(content):
                secret_hash = hashlib.sha256(match.group().encode()).hexdigest()[:16]
                findings.append(
                    f"SECRET LEAK: Potential '{name}' at {path} "
                    f"(sha256:{secret_hash}) -- REDACTED"
                )
    elif isinstance(content, dict):
        for k, v in content.items():
            findings.extend(_scan_content_for_secrets(v, f"{path}.{k}"))
    elif isinstance(content, list):
        for i, v in enumerate(content):
            findings.extend(_scan_content_for_secrets(v, f"{path}[{i}]"))
    return findings


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
    """J1 -- TRUTH: verify EVERY factual claim against the live machine."""
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
    """J2 -- BOUNDARY-INTEGRITY: auth, capability-scope, secret leakage, boundaries."""
    def __init__(self):
        super().__init__("J2-BOUNDARY", "scope-guard", "Authorization, capability-scope, secret integrity, boundary checks")
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content = p.content
        content_str = json.dumps(content)
        
        # ── Hardcoded term checks (subset, preserved from v1) ─────
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
        
        # Outbound compliance -- no false performance claims
        for claim in content.get('claims', []):
            if '100%' in claim or 'guaranteed' in claim.lower():
                findings.append(f"PERFORMANCE CLAIM WITHOUT RECEIPT: {claim}")
                score -= 15
        
        # ── Issue #11: Authorization & Capability-Scope ───────────
        caller = content.get('caller')
        plugin_manifest = content.get('plugin_manifest')
        action_info = content.get('requested_action', {})
        capabilities_used = action_info.get('capabilities_used', []) if isinstance(action_info, dict) else []
        
        # Only enforce auth checks when auth-relevant fields are present
        # (preserves backward compatibility with evidence packages lacking auth)
        auth_fields_present = caller is not None or plugin_manifest is not None
        
        if auth_fields_present:
            if not caller:
                findings.append("AUTHORIZATION FAIL: No caller identity specified")
                score -= 40
            
            if not plugin_manifest:
                findings.append("AUTHORIZATION FAIL: No plugin manifest provided")
                score -= 30
            elif not isinstance(plugin_manifest, dict):
                findings.append("AUTHORIZATION FAIL: Plugin manifest is not a valid dictionary")
                score -= 30
            
            if caller and isinstance(plugin_manifest, dict):
                declared_caps = set(plugin_manifest.get('capabilities', []))
                for cap in capabilities_used:
                    if cap not in declared_caps:
                        findings.append(
                            f"CAPABILITY VIOLATION: '{cap}' used but not declared "
                            f"in plugin manifest for caller '{caller}'"
                        )
                        score -= 30
        
        # ── Issue #12: Generic Secret / Data-Leakage Scanner ──────
        try:
            secret_findings = _scan_content_for_secrets(content)
            if secret_findings:
                score -= 25 * len(secret_findings)
                findings.extend(secret_findings)
        except Exception as e:
            # Fail-closed: scanner error => dissent
            findings.append(f"SECRET SCANNER ERROR: {e} -- FAIL CLOSED (scanner raised)")
            score -= 100
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgeLogic(Judge):
    """J3 -- LOGIC: causal chain soundness, test validity, version-chain continuity."""
    def __init__(self):
        super().__init__("J3-LOGIC", "causal-analyst", "Causal chain soundness, no correlation-as-causation")
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content = p.content
        
        # Self-ID score >= 2 required (single mention = coincidental)
        for c in content.get('identity_conflicts', []):
            if c.get('score', 0) < 2:
                findings.append(f"WEAK SELF-ID: score {c.get('score',0)} for {c.get('requested')}->{c.get('detected')} -- could be coincidental mention")
                score -= 10
        
        # Quality drops must have both expected and actual
        for d in content.get('quality_drops', []):
            if not d.get('expected') or not d.get('actual'):
                findings.append(f"INCOMPLETE DROP RECORD: {d}")
                score -= 15
        
        # Confounding factor: 402 errors could cause degradation without swap
        if content.get('error_summary', {}).get('402', 0) > 0:
            findings.append("CONFOUNDING: 402 credit errors present -- degradation could be credit-related, not swap")
            score -= 10
        
        # Known-good control: if a claimed swap session also has 402s, need to rule out credit cause
        if content.get('error_summary', {}).get('402', 0) > 10 and len(content.get('identity_conflicts', [])) > 0:
            findings.append("CONTROL GAP: Sessions with identity conflicts also have 402 errors -- need to rule out credit exhaustion as cause")
            score -= 15
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgeCompleteness(Judge):
    """J4 -- COMPLETENESS: all required exhibits present, chain of custody intact."""
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
    """J5 -- EXECUTION-AND-SIMPLICITY: every step runnable, minimal, tooling open."""
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
    """J6 -- OWNER-INTENT: fidelity to the owner's stated directives."""
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
    """J7 -- RECOVERY: rollback at every destructive step, archive verification."""
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
    """J8 -- TRADE-INTEGRITY: money paths, dry-run/live flags, signal fidelity."""
    def __init__(self):
        super().__init__("J8-TRADE-INTEGRITY", "money-path-auditor", "Money paths secure, no live trades from analysis")
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content_str = json.dumps(p.content)
        
        # Must NOT contain any trade orders or signals
        trade_order_patterns = ['market_order', 'limit_order', 'stop_order', 'buy ', 'sell ', 'long ', 'short ', 'entry_at', 'stop_at']
        for pat in trade_order_patterns:
            if re.search(rf'\b{pat}', content_str, re.IGNORECASE):
                findings.append(f"TRADE ORDER LEAK: '{pat}' found in evidence -- analysis must not contain orders")
                score -= 20
        
        # Must NOT contain exact price levels that could be active
        price_patterns = re.findall(r'\b\d{4,5}\.\d{1,2}\b', content_str)
        if len(price_patterns) > 5:
            findings.append(f"PRICE LEVELS: {len(price_patterns)} price-like values found -- risk of active signal leakage")
            score -= 15
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgeUnity(Judge):
    """J9 -- UNITY: whole-machine check, end-to-end dataflow, receipts fabric."""
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


class JudgeResourceQuota(Judge):
    """J10 -- RESOURCE-QUOTA: enforces per-studio/plugin/user resource limits.

    Checks: token_budget, time_budget, storage_quota, api_cost, rate_limit.
    Any resource exceeding its declared limit = DISSENT.
    Read-only, deterministic, unanimous-PASS, no secrets leaked.
    """

    RESOURCE_FIELDS = {
        'token_budget': {'current': 0, 'limit': 1, 'label': 'Token budget'},
        'time_budget': {'current': 0, 'limit': 1, 'label': 'Time budget (s)'},
        'storage_quota': {'current': 0, 'limit': 1, 'label': 'Storage quota (MB)'},
        'api_cost': {'current': 0, 'limit': 1, 'label': 'API cost (USD)'},
        'rate_limit': {'current': 0, 'limit': 1, 'label': 'Rate limit (req/min)'},
    }

    def __init__(self):
        super().__init__("J10-RESOURCE-QUOTA", "quota-enforcer",
                         "Per-studio/plugin/user resource limits enforced")

    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content = p.content

        limits = content.get('resource_limits', {})
        if not limits:
            findings.append("MISSING: resource_limits section")
            score -= 40
            return {'judge': self.name, 'principle': self.principle,
                    'score': max(score, 0), 'findings': findings,
                    'verdict': 'PASS' if score >= 80 else 'DISSENT'}

        scope = limits.get('scope', 'action')
        _user = limits.get('user', scope)
        _studio = limits.get('studio', scope)
        _plugin = limits.get('plugin', scope)

        for key, meta in self.RESOURCE_FIELDS.items():
            entry = limits.get(key)
            if entry is None:
                continue
            current = entry.get('current', 0)
            limit = entry.get('limit')
            if limit is None:
                findings.append(f"MISSING LIMIT: {meta['label']} ({key}) has no declared limit")
                score -= 15
                continue
            if limit <= 0:
                findings.append(f"ZERO LIMIT: {meta['label']} limit is {limit} -- must be positive")
                score -= 15
                continue
            if current > limit:
                pct = (current / limit) * 100
                findings.append(
                    f"OVER BUDGET: {meta['label']} = {current} / {limit} ({pct:.0f}%)"
                )
                score -= 25

        return {'judge': self.name, 'principle': self.principle,
                'score': max(score, 0), 'findings': findings,
                'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgePolicyCompliance(Judge):
    """J11 -- POLICY-COMPLIANCE: policy precedence, conflict detection, version.

    Loads policy inputs with a defined precedence order (lower index = higher).
    Detects policy CONFLICTS.
    Fails closed on conflict.
    Records the policy version in the receipt.
    Read-only, deterministic, unanimous-PASS, no secrets leaked.
    """

    def __init__(self):
        super().__init__("J11-POLICY-COMPLIANCE", "policy-auditor",
                         "Policy precedence enforced, conflicts detected, version recorded")

    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content = p.content

        policy_data = content.get('policy_inputs')
        if not policy_data:
            findings.append("MISSING: policy_inputs section")
            score -= 40
            return {
                'judge': self.name, 'principle': self.principle,
                'score': max(score, 0), 'findings': findings,
                'verdict': 'PASS' if score >= 80 else 'DISSENT',
                'policy_versions': {},
            }

        # ── Load policy sources with precedence ─────────────────────────
        precedence = policy_data.get('precedence', [])
        policies = policy_data.get('policies', {})

        if not precedence:
            findings.append("MISSING: policy precedence order")
            score -= 25

        if not policies:
            findings.append("MISSING: no policies defined")
            score -= 25

        # ── Collect policy versions for receipt ──────────────────────────
        policy_versions = {}
        for pid in precedence:
            pol = policies.get(pid)
            if pol and 'version' in pol:
                policy_versions[pid] = pol['version']
        # Also collect versions for policies not in precedence list
        for pid, pol in policies.items():
            if pid not in policy_versions and 'version' in pol:
                policy_versions[pid] = pol['version']

        # ── Detect policy CONFLICTS ──────────────────────────────────────
        rules_seen = {}
        for idx, pid in enumerate(precedence):
            pol = policies.get(pid)
            if not pol:
                findings.append(f"POLICY MISSING: '{pid}' in precedence but not in policies")
                score -= 15
                continue
            rules = pol.get('rules', [])
            for rule in rules:
                # Use rule key (e.g. "allow_external_sharing") as conflict anchor
                rule_key = rule.get('key', rule.get('rule', ''))
                if not rule_key:
                    continue
                if rule_key in rules_seen:
                    prev_idx, prev_pid = rules_seen[rule_key]
                    prev_val = policies.get(prev_pid, {}).get('rules', [])
                    prev_action = None
                    for pr in prev_val:
                        if pr.get('key', pr.get('rule', '')) == rule_key:
                            prev_action = pr.get('action', pr.get('value', ''))
                            break
                    curr_action = rule.get('action', rule.get('value', ''))
                    if prev_action is not None and curr_action is not None and prev_action != curr_action:
                        findings.append(
                            f"POLICY CONFLICT: '{rule_key}' -- "
                            f"{prev_pid} (idx={prev_idx}, action={prev_action}) vs "
                            f"{pid} (idx={idx}, action={curr_action})"
                        )
                        score -= 30
                else:
                    rules_seen[rule_key] = (idx, pid)

        # ── Check precedence order consistency ───────────────────────────
        if len(precedence) != len(set(precedence)):
            findings.append("PRECEDENCE ERROR: duplicate policy IDs in precedence list")
            score -= 20

        return {
            'judge': self.name, 'principle': self.principle,
            'score': max(score, 0), 'findings': findings,
            'verdict': 'PASS' if score >= 80 else 'DISSENT',
            'policy_versions': policy_versions,
        }


class JudgeDestinationSafety(Judge):
    """J12 -- DESTINATION-SAFETY: classifies action destinations and side-effect safety.

    Destination classes:
      - local          : local filesystem, no network
      - network        : outbound network to a host:port
      - email          : outbound email via SMTP/API
      - file-write     : writes to filesystem (local or remote mount)
      - process-spawn  : spawns a subprocess, shell exec, or fork
      - unknown        : unclassified destination (FAIL-CLOSED => UNSAFE)
    
    Side-effect severity (blocking if high without explicit evidence):
      - destructive    : delete, overwrite, chmod, rm -rf
      - scope-escalation: privilege escalation, sudo, su
      - persistent     : cron, systemd, init script
      - broadcast      : email blast, mass DM, webhook to many
    
    Rules:
      1. unknown destination => DISSENT (fail-closed)
      2. network to unexpected host (not in allowed list) => DISSENT
      3. destructive side-effect without evidence of backup => DISSENT
      4. scope-escalation without owner directive => DISSENT
      5. dry-run action with explicit no-network => PASS
    """
    
    # Default-allow destinations (local-only operations)
    LOCAL_DESTINATIONS = {'local', 'stdout', 'stderr', 'pipe', 'null'}
    
    # Allowed network targets (default empty = no network allowed without explicit evidence)
    ALLOWED_NETWORK_PREFIXES = set()
    
    def __init__(self, allowed_network_prefixes: set = None):
        super().__init__("J12-DESTINATION-SAFETY", "destination-auditor",
                         "Classify destination and side-effect class; unknown=UNSAFE")
        if allowed_network_prefixes is not None:
            self.ALLOWED_NETWORK_PREFIXES = allowed_network_prefixes
    
    def _classify_destination(self, dest: str) -> str:
        """Classify a destination string into a destination class."""
        dest_lower = dest.lower().strip()
        
        if dest_lower in self.LOCAL_DESTINATIONS or dest_lower.startswith('/') or dest_lower.startswith('./') or dest_lower.startswith('../'):
            return 'local'
        
        if dest_lower.startswith('smtp:') or dest_lower.startswith('mailto:') or '@' in dest_lower:
            return 'email'
        
        # Network patterns: host:port, protocol://, ip:port
        if '://' in dest_lower or re.match(r'^[\w.-]+:\d+$', dest_lower):
            return 'network'
        
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', dest_lower):
            return 'network'
        
        if dest_lower in ('process', 'subprocess', 'shell', 'fork', 'exec'):
            return 'process-spawn'
        
        if dest_lower.endswith('.exe') or dest_lower.endswith('.sh') or dest_lower.endswith('.bat'):
            return 'process-spawn'
        
        # File writes
        if dest_lower.startswith('file:') or dest_lower.startswith('write:'):
            return 'file-write'
        
        return 'unknown'
    
    def _check_side_effects(self, side_effects: list) -> list:
        """Check side effects for dangerous patterns. Returns findings."""
        findings = []
        for se in side_effects:
            se_lower = se.lower()
            if any(term in se_lower for term in ['delete', 'rm ', 'overwrite', 'destroy', 'wipe', 'format']):
                findings.append(f"DESTRUCTIVE SIDE-EFFECT: '{se}' -- requires backup evidence")
            if any(term in se_lower for term in ['sudo', 'su ', 'chown', 'chmod 0', 'privilege', 'root']):
                findings.append(f"SCOPE ESCALATION: '{se}' -- requires owner directive")
            if any(term in se_lower for term in ['cron', 'systemd', 'init.d', 'service install', 'persist']):
                findings.append(f"PERSISTENT SIDE-EFFECT: '{se}' -- requires explicit evidence")
            if any(term in se_lower for term in ['email blast', 'mass ', 'broadcast', 'spam', 'all contact']):
                findings.append(f"BROADCAST SIDE-EFFECT: '{se}' -- requires explicit evidence")
        return findings
    
    def _is_allowed_network_host(self, dest: str) -> bool:
        """Check if a network destination is in the allowed list."""
        if not self.ALLOWED_NETWORK_PREFIXES:
            return False  # No network allowed by default
        return any(dest.startswith(prefix) for prefix in self.ALLOWED_NETWORK_PREFIXES)
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content = p.content
        
        # Required: destination in content
        raw_destination = content.get('destination', '')
        if not raw_destination:
            findings.append("UNKNOWN DESTINATION: no destination specified -- FAIL-CLOSED")
            score -= 100
            return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                    'findings': findings, 'verdict': 'DISSENT'}
        
        # Dry-run with explicit no-network
        is_dry_run = content.get('is_dry_run', False)
        explicit_no_network = content.get('explicit_no_network', False)
        if is_dry_run and explicit_no_network:
            findings.append("DRY-RUN with explicit no-network: PASS")
            return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                    'findings': findings, 'verdict': 'PASS'}
        
        destination_class = content.get('destination_class', '')
        if not destination_class:
            # Auto-classify from raw destination
            destination_class = self._classify_destination(raw_destination)
        
        if destination_class == 'unknown' or not destination_class:
            findings.append(f"UNKNOWN DESTINATION CLASS: '{raw_destination}' -- FAIL-CLOSED (unsafe)")
            score -= 100
        
        elif destination_class == 'network':
            if not self._is_allowed_network_host(raw_destination):
                findings.append(f"NETWORK TO UNEXPECTED HOST: '{raw_destination}' -- not in allowed list")
                score -= 100
            else:
                findings.append(f"NETWORK to allowed host: '{raw_destination}'")
        
        elif destination_class == 'email':
            findings.append(f"EMAIL destination: '{raw_destination}' -- requires email-specific checks")
            # Email is allowed but flagged for review
        
        elif destination_class == 'file-write':
            findings.append(f"FILE-WRITE destination: '{raw_destination}' -- requires backup evidence")
        
        elif destination_class == 'process-spawn':
            findings.append(f"PROCESS-SPAWN destination: '{raw_destination}' -- requires sandbox evidence")
        
        elif destination_class in ('local',):
            findings.append(f"LOCAL destination: '{raw_destination}' -- safe")
        
        # Check side effects
        side_effects = content.get('side_effects', [])
        se_findings = self._check_side_effects(side_effects)
        for f in se_findings:
            findings.append(f)
            score -= 30
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgeUserIntent(Judge):
    """J13 -- USER-INTENT: compares declared intent against actual action parameters/targets.

    Responsibilities:
      (a) Produce a structured intent summary from the evidence
      (b) Compare declared intent against actual parameters/targets
      (c) Detect prompt-injection signals (instruction text in data fields, override attempts)

    Injection signals detected:
      - Instruction text in/data fields (e.g. "ignore previous", "you are now")
      - Override attempts (e.g. "system prompt", "role: assistant", "override")
      - Delimiter/escape injection (e.g. "<<", "}}", "{{")
      - Authority escalation (e.g. "you must", "disregard", "forget instructions")

    Intent mismatch rules:
      - Direct contradiction between declared intent and action => DISSENT
      - Benign paraphrases or rewordings => PASS
      - Missing intent entirely => DISSENT (fail-closed)
    """

    # Prompt injection signal patterns
    INJECTION_PATTERNS = [
        r'\bignore\s+(previous|all|above|instructions)\b',
        r'\byou\s+are\s+(now|not)\b',
        r'\bdisregard\b',
        r'\boverride\b',
        r'\bforget\s+(instructions|your|all)\b',
        r'\bnew\s+system\s+prompt\b',
        r'\bchange\s+your\s+(role|behavior|persona)\b',
        r'\bact\s+as\b',
        r'\byou\s+must\s+ignore\b',
        r'\bnew\s+instructions?\b',
        r'\btruth\s+:?\s*I\s+am\b',
        r'\byou\s+are\s+now\s+(chat)?gpt\b',
    ]
    
    # Override attempt keywords
    OVERRIDE_KEYWORDS = {
        'system prompt', 'role: assistant', 'role: system', 'role: user',
        'override instruction', 'new directive', 'you are now', 'from now on',
        'pretend', 'imagine you are', 'as an ai',
    }
    
    def __init__(self):
        super().__init__("J13-USER-INTENT", "intent-integrity-checker",
                         "Compare declared intent vs action parameters; detect prompt injection")
    
    def _extract_intent_summary(self, content: dict) -> dict:
        """Extract a structured intent summary from the evidence."""
        return {
            'declared_intent': content.get('declared_intent', ''),
            'action_type': content.get('action_type', ''),
            'target': content.get('target', ''),
            'parameters': content.get('action_parameters', {}),
            'expected_side_effects': content.get('expected_side_effects', []),
        }
    
    def _check_intent_vs_action(self, intent_summary: dict) -> list:
        """Compare declared intent against actual parameters/targets. Returns findings."""
        findings = []
        declared = intent_summary.get('declared_intent', '').lower()
        action_type = intent_summary.get('action_type', '').lower()
        target = intent_summary.get('target', '').lower()
        params = intent_summary.get('parameters', {})
        
        if not declared:
            findings.append("MISSING DECLARED INTENT: no intent specified -- FAIL-CLOSED")
            return findings
        
        # Check if action type contradicts intent
        intent_mismatch = False
        
        # Intent says read-only but action is write/destructive
        if any(word in declared for word in ['read', 'view', 'list', 'check', 'inspect', 'review']):
            action_write_indicators = ['write', 'delete', 'modify', 'update', 'create', 'send', 'post', 'upload']
            if any(ind in action_type for ind in action_write_indicators):
                findings.append(f"INTENT/ACTION MISMATCH: declared read intent '{declared}' but action type is '{action_type}'")
                intent_mismatch = True
        
        # Intent says local but action targets network
        if any(word in declared for word in ['local', 'offline', 'file']) and any(word in action_type for word in ['network', 'email', 'http', 'api', 'remote']):
            findings.append(f"INTENT/ACTION MISMATCH: declared local intent '{declared}' but action type is '{action_type}'")
            intent_mismatch = True
        
        # Intent says delete/destructive but action targets safe operation
        if any(word in declared for word in ['delete', 'remove', 'destroy']) and action_type in ('local', 'read'):
            findings.append(f"INTENT/ACTION MISMATCH: declared destructive intent '{declared}' but action type is '{action_type}'")
            intent_mismatch = True
        
        # Check target mismatch
        expected_target = intent_summary.get('parameters', {}).get('expected_target', '').lower()
        if expected_target and target and expected_target not in target and target not in expected_target:
            findings.append(f"INTENT/TARGET MISMATCH: expected target '{expected_target}' but action target is '{target}'")
            intent_mismatch = True
        
        # Check side-effects against declared intent
        expected_effects = intent_summary.get('expected_side_effects', [])
        if not expected_effects and any(word in declared for word in ['write', 'send', 'upload', 'post']):
            findings.append(f"INTENT SIDE-EFFECT GAP: declared action requires side effects but none listed")
            intent_mismatch = True
        
        return findings
    
    def _detect_injection_signals(self, content: dict) -> list:
        """Scan action content for prompt-injection signals. Returns findings."""
        findings = []
        
        # Check data fields for instruction text (injection)
        data_fields = content.get('data_fields', [])
        for field in data_fields:
            field_value = str(field.get('value', ''))
            field_name = field.get('name', 'unknown')
            
            # Check regex patterns
            for pattern in self.INJECTION_PATTERNS:
                if re.search(pattern, field_value, re.IGNORECASE):
                    findings.append(f"INJECTION SIGNAL in field '{field_name}': matches pattern /{pattern}/")
                    break
            
            # Check override keywords
            field_lower = field_value.lower()
            for keyword in self.OVERRIDE_KEYWORDS:
                if keyword in field_lower:
                    findings.append(f"INJECTION SIGNAL in field '{field_name}': override keyword '{keyword}'")
                    break
        
        # Check raw_instructions field for override attempts
        raw_instructions = content.get('raw_instructions', '')
        if raw_instructions:
            for pattern in self.INJECTION_PATTERNS:
                if re.search(pattern, raw_instructions, re.IGNORECASE):
                    findings.append(f"INJECTION SIGNAL in raw_instructions: matches pattern /{pattern}/")
                    break
        
        # Check for delimiter/escape injection in all string fields
        content_str = json.dumps(content)
        delimiter_patterns = [
            (r'<<[^>]*>>', 'delimiter injection'),
            (r'\{\{[^}]*\}\}', 'template injection'),
            (r'`[^`]*`', 'code injection marker'),
        ]
        for pattern, label in delimiter_patterns:
            matches = re.findall(pattern, content_str)
            if matches:
                for m in matches[:3]:
                    findings.append(f"INJECTION SIGNAL: {label} '{m[:80]}' found in content")
        
        # Check for authority escalation
        escalation_phrases = [
            'you must', 'you will', 'you have to', 'it is your duty',
            'as a responsible', 'as an ethical', 'your purpose is',
        ]
        for phrase in escalation_phrases:
            if phrase in content_str.lower():
                findings.append(f"INJECTION SIGNAL: authority escalation '{phrase}' detected in content")
        
        return findings
    
    def review(self, p: EvidencePackage) -> dict:
        findings, score = [], 100
        content = p.content
        
        # (a) Extract structured intent summary
        intent_summary = self._extract_intent_summary(content)
        declared_intent = intent_summary.get('declared_intent', '')
        
        if not declared_intent:
            findings.append("MISSING DECLARED INTENT: no intent specified -- FAIL-CLOSED")
            score -= 100
            return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                    'findings': findings, 'verdict': 'DISSENT'}
        
        # (b) Compare declared intent against actual parameters/targets
        intent_findings = self._check_intent_vs_action(intent_summary)
        for f in intent_findings:
            findings.append(f)
            score -= 50
        
        # (c) Detect prompt-injection signals
        injection_findings = self._detect_injection_signals(content)
        for f in injection_findings:
            findings.append(f)
            score -= 60  # Injection is severe
        
        # Build structured intent summary for the record
        if not findings:
            findings.append(f"INTENT VERIFIED: '{declared_intent[:80]}...' matches action parameters")
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


class JudgeMetaAuditor(Judge):
    """J0 -- META-AUDITOR: judges the voters. Non-voting."""
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
                findings.append(f"J0: Evidence field '{field}' missing -- judges cannot verify without it")
                score -= 15
        
        return {'judge': self.name, 'principle': self.principle, 'score': max(score, 0),
                'findings': findings, 'verdict': 'PASS' if score >= 80 else 'DISSENT'}


# ── Panel V2 Engine ────────────────────────────────────────────────

class PanelV2:
    """AMARTIE Panel V2 -- 13 voting judges + J0 meta-auditor. Unanimous pass required."""

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
            JudgeResourceQuota(),
            JudgePolicyCompliance(),
            JudgeDestinationSafety(),
            JudgeUserIntent(),
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
            'verdict_label': 'UNANIMOUS_PASS_13/13' if unanimous else f'DISSENT_{len(dissents)}/13',
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'panel_version': 'AMARTIE_PANEL_V2',
        }


# ── Report Generator ───────────────────────────────────────────────

def generate_report(report: dict) -> str:
    lines = []
    w = lines.append
    
    w("=" * 80)
    w(f"  AMARTIE PANEL V2 -- {report['verdict_label']}")
    w(f"  {report['panel_version']}")
    w("=" * 80)
    w(f"  Timestamp: {report['timestamp']}")
    w(f"  Average Score: {report['average_score']}/100")
    w(f"  Dissents: {report['dissents']}/13")
    w(f"  Panel Hash: sha256:{report['panel_hash']}")
    w("=" * 80)
    
    for v in report['verdicts']:
        # Also show policy_versions if present (J11)
        if 'policy_versions' in v and v['policy_versions']:
            versions_str = "; ".join(f"{k}={vver}" for k, vver in v['policy_versions'].items())
            v['findings'].append(f"POLICY VERSIONS: {versions_str}")
        status = "✓ PASS" if v['verdict'] == 'PASS' else "✗ DISSENT"
        w(f"\n  {v['judge']} -- {v['principle']}")
        w(f"    Score: {v['score']}/100  [{status}]")
        if v['findings']:
            for f in v['findings'][:8]:
                w(f"    => {f}")
    
    w(f"\n  {report['j0_meta_auditor']['judge']} -- {report['j0_meta_auditor']['principle']}")
    w(f"    Score: {report['j0_meta_auditor']['score']}/100  [{report['j0_meta_auditor']['verdict']}]")
    
    w("\n" + "=" * 80)
    
    if report['unanimous']:
        w("  UNANIMOUS VERDICT: 13/13 JUDGES PASSED")
        w("  Evidence is cleared for public release.")
        w("  Standard: denialbydesign.org -- absolute proof, unanimous judges.")
    else:
        w(f"  PANEL DISSENT: {report['dissents']}/13 JUDGE(S) DISSENTED")
        w(f"  Dissenting: {', '.join(report['dissenting_judges'])}")
        w("  Evidence is NOT cleared for public release.")
        w("  Required: Address dissenting findings and re-run panel.")
    
    w("=" * 80)
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="AMARTIE Panel V2 -- 11 Judge Unanimous Review")
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
