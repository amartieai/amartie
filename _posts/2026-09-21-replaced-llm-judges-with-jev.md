---
layout: post
title: "We Replaced Our 9 LLM Judges With JEV — Cost Dropped 97%, Speed Went Up 13x"
date: 2026-09-21
---

## The Problem

AMARTIE has a 9-judge gate. Every outbound action (email, trade, deploy, post) must pass all nine. One dissent = bounce + receipt.

Originally we used frontier LLMs as judges. Each evaluation:
- ~2 seconds per judge × 9 = **18 seconds total**
- ~$0.01+ per evaluation (input + output tokens)
- No confidence score — we couldn’t tell if the judge was guessing
- Hallucinations possible — a judge could approve something nonsensical

At 100 actions/day that’s **$1+/day** and **30 minutes** of pure gate time. The gate was the bottleneck.

## Enter JEV

JEV is a [System One model](https://typesafe.ai) from TypeSafe AI. It doesn’t write sentences — it makes decisions. Three primitives:

| Primitive | What it returns |
|-----------|-----------------|
| **Choice** | One option from a list, with probabilities |
| **Score** | Position on a scale (e.g., 0–2 for severity) |
| **Noul** | Yes/no with a probability |

**193x faster. 244x cheaper. Zero hallucinations.** (Output type is fixed — there’s nothing to hallucinate.)

## The Mapping

Each of our 9 judges now asks the same structured questions:

```python
response = client.system_one(
    state=action_payload,
    questions={
        "verdict": Choice(
            "Should this action be approved?",
            criteria={
                "pass": "Meets all standards, no concerns",
                "dissent": "Has issues that need resolution"
            }
        ),
        "confidence": Score(
            "How confident are you?",
            criteria=["Low", "Medium", "High", "Certain"]
        ),
        "evidence": Noul("Is there sufficient evidence?")
    }
)
```

All 9 judges run in **one request** (~150ms). Total gate time: **1.35 seconds** instead of 18.

## The Numbers

| Metric | Before (LLM) | After (JEV) |
|--------|-------------|-------------|
| **Time per evaluation** | 18,000ms | 1,350ms |
| **Cost per evaluation** | ~$0.01 | ~$0.0004 |
| **Confidence scores** | None | Per-judge, 0.0–1.0 |
| **Hallucinations** | Possible | Impossible (typed output) |
| **Cacheable** | No | Yes (LMCache) |
| **Fails closed** | No | Yes (error = DISSENT) |

**97% cost reduction. 13x speedup.**

## The Fallback

JEV costs $0.042/M input tokens (output is free). For teams that want zero cost, we added **Layer** — a free, self-hosted alternative with the same primitives. 33ms per question, runs locally, no API key.

Provider chain: **JEV → Layer → Mock** (for testing).

## The Integration

```python
from amartie.gate import JudgeGate

gate = JudgeGate()  # Auto-detects provider
passed, receipt = gate.verify_action(
    action_type="email-send",
    payload={"to": "user@example.com", "subject": "...", "body": "..."}
)

if passed:
    send_email()
else:
    block_and_log(receipt)
```

Hash-chained receipts. Tamper-evident. Self-auditing.

## What’s Next

- **LMCache integration** — share KV cache across judge evaluations. Another 10x for repeated actions.
- **Voice-controlled gate** — Jarvis module: speak a command, JEV routes it, Playwright executes.
- **Public benchmark** — open dataset of 1000 evaluated actions, graded by humans.
- **Layer optimization** — self-hosted, zero-cost, 33ms per decision.

AMARTIE is open source. MIT licensed. [github.com/amartieai/amartie](https://github.com/amartieai/amartie)

Try the JEV playground: [jevplayground.com](https://jevplayground.com) — no signup, no card.

---

*Built by the AMARTIE team. We verify AI. Then we verify the verification.*
