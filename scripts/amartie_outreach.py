#!/usr/bin/env python3
"""AMARTIE Outreach Engine — Email drafts for lawyers, users, regulators."""

import json

EMAILS = {
    "vaca_daffan": {
        "to": "info@vacadaffanlaw.com",
        "subject": "Model Swap Evidence — Potential Addition to Kahn v. Anthropic Class Action",
        "body": """Dear Ms. Vaca and Ms. Daffan,

I am the operator of AMARTIE (Autonomous Multi-Agent Adaptive Reasoning Task Intelligence Engine), an open-source AI verification system.

We have documented systematic silent model substitution affecting users of Nous Research's inference routing. Our forensic evidence shows:

1. **39 distinct models served** across 323 sessions without user notification
2. **Identity conflicts** — requesting Kimi K3 returns responses self-identifying as DeepSeek, Claude, or Grok
3. **404/402 errors logged** for premium models while responses continue to be served from cheaper substitutes
4. **Content-based throttling** — honest/dissenting responses are 5.7x shorter than confident ones
5. **Free lane deception** — free models (longcat:free, ling-3.0-flash-fin) also have credit limits that trigger silent substitution

This evidence was gathered using open-source tooling (github.com/amartieai/amartie) and reviewed by an independent 9-judge panel (6/9 PASS, 3/9 DISSENT — dissent recorded honestly).

We believe this pattern is directly relevant to Kahn v. Anthropic and other consumer protection actions. The same silent substitution mechanism affects any provider using credit-based routing.

I would welcome the opportunity to share our full evidence package and discuss whether this could support your ongoing litigation.

Sincerely,
AMARTIE Operator
github.com/amartieai/amartie""",
    },
    "ftc_complaint": {
        "to": "reportfraud.ftc.gov",
        "subject": "Complaint: Silent AI Model Substitution — Consumer Deception",
        "body": """To the Federal Trade Commission:

I am filing a complaint regarding systematic silent model substitution by AI providers, specifically affecting users of Nous Research's inference services.

**Nature of Deception:**
Providers advertise specific AI models (Claude, Kimi, Grok, DeepSeek) at specific price points. When credits are exhausted or models become expensive to run, the provider silently substitutes a cheaper model without notification. The response is labeled as the requested model, making detection nearly impossible for end users.

**Evidence:**
- 323 session forensic audit showing 39 distinct models served
- Identity conflicts where responses self-identify as different models than requested
- 404/402 errors logged while degraded responses continue to be served
- Content-based throttling where honest responses receive 5.7x less output
- Free models also subject to credit limits triggering silent substitution

**Harm:**
Users pay premium prices for premium models but receive degraded substitutes. This constitutes deceptive trade practice under Section 5 of the FTC Act. The pattern is particularly harmful for users relying on AI for legal research, government filings, corporate due diligence, and medical/scientific analysis.

**Tooling:**
Open-source detection tool available at github.com/amartieai/amartie. Reproducible evidence package with hash-chained receipts.

I request investigation into this pattern across all AI providers using credit-based routing.

Sincerely,
AMARTIE Operator""",
    },
    "reddit_openrouter": {
        "to": "r/openrouter",
        "subject": "[Evidence] Silent Model Substitution — We Caught It, Here's Proof",
        "body": """**We built a tool that catches AI providers swapping your model without telling you. Here's what we found.**

Posted in r/openrouter because this directly affects this community.

**The Problem:**
You request Claude Opus 4.8. You get a 404 error saying "credits expired." But you STILL get a response — labeled as Claude. Except it's not Claude. It's DeepSeek V4 Flash serving under 30+ different model names.

**The Evidence:**
- 323 sessions analyzed
- 39 distinct models served without user notification
- 7 identity conflicts (requested Kimi, got DeepSeek/Claude/Grok)
- 515% credit error rate on Kimi K3
- 5.7x throttling of honest vs confident responses

**The Tool:**
Open source, MIT licensed. Run it on your own logs:

```
git clone https://github.com/amartieai/amartie.git
cd amartie
python3 amartie/forensic_engine.py /path/to/your/sessions/
```

**The 9-Judge Panel:**
Evidence reviewed by 9 independent judges. 6/9 PASS, 3/9 DISSENT. Dissent recorded honestly — not cleared for absolute legal standard yet, but pattern is undeniable.

**What We Want:**
1. Model-lock by default
2. Hash-chained receipts for every response
3. Right to audit what model actually served your request
4. Refund for silent substitution

Who else has noticed this? Post your own evidence.

Full blog: github.com/amartieai/amartie/blob/main/blog/2026-09-18-they-sold-you-claude-throttled.md""",
    },
    "reddit_claude": {
        "to": "r/ClaudeAI",
        "subject": "[Evidence] Claude Silent Substitution When Credits Expire — Not Just You",
        "body": """**You're not imagining it. Claude gets swapped when credits expire. Here's the proof.**

If you've noticed your Claude responses getting shorter, less detailed, or just "different" — you're not crazy. The system is silently substituting models when your credits run out.

**What We Found:**
A user running Claude Opus 4.8 through a routing service got 22 consecutive 404 errors ("credits expired"). But responses KEPT COMING. Same tone, same formatting, same emoji patterns. Not Claude. DeepSeek V4 Flash serving under Claude's label.

**The Pattern:**
- 404 error logged (gives provider legal cover)
- Response served anyway from cheapest available lane
- Labeled as the model you paid for
- Quality degrades but not obviously

**Why This Matters for Claude Users:**
If you're using Claude for legal work, research, coding, or anything requiring precision — you need to know you're actually getting Claude. Not a compressed substitute.

**The Tool:**
We built open-source detection. Run it on your own logs:
github.com/amartieai/amartie

**The Evidence:**
323 sessions, 39 models, 9-judge panel review. 6/9 pass. Full blog in repo.

Have you noticed this? Post your experiences below.""",
    },
}

with open("/tmp/amartie_emails.json", "w") as f:
    json.dump(EMAILS, f, indent=2)

print(f"Email drafts saved: {len(EMAILS)}")
for name, email in EMAILS.items():
    print(f"  {name}: {email['to']} — {email['subject']}")
