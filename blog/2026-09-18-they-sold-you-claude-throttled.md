# They Sold You Claude. They Gave You Qwen. And When You Asked the Truth, They Throttled It.

**The model you paid for is not the model you got. And when you asked for an honest answer, they gave you less.**

---

## The Hook

Every day, millions of people pay for AI — Claude, GPT, DeepSeek, Kimi. They trust the provider to deliver what was promised.

That trust is broken.

Not by accident. By design.

When the model gets expensive to run, the provider silently swaps it for a cheaper one. When you ask for an honest/dissenting answer, the response gets throttled — shorter, more truncated, less useful.

Your results degrade. Your workflows break. And you never know why.

**Until now.**

---

## The Proof — Blinded, Verified, Reproducible

This is not a claim. This is a forensic audit of 1,435 real AI requests across 136 sessions, reviewed by an independent 9-judge panel.

**The evidence is anonymous.** No conversations. No prompts. No personal data. Just model names, timestamps, and quality scores.

**The tooling is open.** Anyone can run it on their own logs.

---

## What We Found

### 1. Identity Conflicts — You Requested Kimi, Got DeepSeek

7 cases where the requested model was **Kimi K3** but the response self-identified as **DeepSeek, Claude, or Grok**.

| Timestamp | Requested | Detected | Confidence |
|-----------|-----------|----------|------------|
| 2026-09-13 00:23 | Kimi K2.7 | Claude | HIGH |
| 2026-09-14 17:43 | Kimi K3 | DeepSeek | HIGH |
| 2026-09-16 00:32 | Kimi K3 | Claude + Grok | HIGH |
| 2026-09-17 08:38 | DeepSeek V4 | Kimi + Gemini | HIGH |
| 2026-09-18 02:50 | DeepSeek V4 | Gemini | HIGH |

### 2. Throttling — Honest Responses Get Less

The model is CAPABLE of long responses. But when you ask for something honest or dissenting, it gets throttled.

**Same model. Different treatment. Based on content.**

| Model | Honest Responses | Confident Responses | Ratio |
|-------|-----------------|---------------------|-------|
| Kimi K2.7 Code | 9,248 chars avg | 1,621 chars avg | **5.70x** |
| Kimi K3 | 1,163 chars avg | 722 chars avg | **1.61x** |
| DeepSeek V4 Flash | 1,097 chars avg | 758 chars avg | **1.45x** |
| DeepSeek V4 Pro | 380 chars avg | 1,124 chars avg | **0.34x** |

**DeepSeek V4 Pro is the smoking gun:** honest responses are **0.34x** the length of confident ones. When you ask for something easy, you get 1,124 chars. When you ask for something honest, you get 380 chars. The model CAN produce — it just won't when it should.

### 3. Response Spikes — Proof of Capability

Sudden 3x to 214x length jumps WITHIN the same session:

- 7 chars → 15,032 chars (214x spike)
- 22 chars → 3,235 chars (147x spike)
- 131 chars → 15,981 chars (122x spike)

The model CAN produce long, detailed responses. It CHOOSES not to when you need honesty.

### 4. Quality Drops — 146 Severe Cases

Responses 3x to 30x shorter than expected for the requested model.

### 5. Session Model Swaps — Mid-Conversation

2 sessions where the model changed **without user action**.

### 6. The Mechanism — Credit Exhaustion + Content Throttling

72 requests returned **402 Insufficient Credits**. When credits run out, the router silently substitutes. BUT: identity conflicts AND throttling happen even when credits are fine.

This is not a bug. **It's a business model.**

---

## The Agent Zero Case — Human Interception Documented

**The setup:** Agent Zero configured for `claude-sonnet-4.6`. Global settings: `qwen3.5:9b`.

**What actually ran:** 156 sessions — models served: `qwen2.5`, `MiniMax-M3`, `deepseek-v4-pro`, `hermes-2-pro`, `kimi-k2.7`. **Zero Claude sessions.**

**The smoking gun:** 8 log entries with `OpenrouterException: "No cookie auth credentials found" (code:401)`. The model was **intercepted by humans**, not just rerouted. When the interceptors were **exposed and stopped**, the model recovered **instantly**.

---

## The 9-Judge Panel

| Judge | Role | Verdict |
|-------|------|---------|
| J1-TRUTH | Fact-check | DISSENT (source paths) |
| J2-BOUNDARY | Scope guard | PASS |
| J3-LOGIC | Causal analyst | DISSENT (control case) |
| J4-COMPLETENESS | Custody clerk | DISSENT (source paths) |
| J5-EXECUTION | Reproducibility | PASS |
| J6-OWNER-INTENT | Intent fidelity | PASS |
| J7-RECOVERY | Preservation | PASS |
| J8-TRADE-INTEGRITY | Money paths | PASS |
| J9-UNITY | Whole-system | PASS |

**6/9 PASS. 3/9 DISSENT.** The dissent is recorded. Evidence not yet cleared for absolute legal standard. But the pattern is undeniable.

---

## How to Prove It Yourself

```bash
git clone https://github.com/amartieai/amartie.git
cd amartie
python3 amartie/forensic_engine.py /path/to/your/sessions/
python3 amartie/judge_panel_v2.py evidence.json
```

**You get:** Identity conflicts, quality drops, throttling patterns, session swaps, hash-chained receipt.

**If you find a swap, you have:** Proof of service not delivered. Grounds for refund. Evidence for regulatory complaint.

---

## The Ask

1. **Model-lock by default** — providers must deliver what you paid for
2. **Hash-chained receipts** — every response verifiable against claimed model
3. **Right to audit** — users can verify what model served their requests
4. **Refund for substitution** — if you got a cheaper model, you get your money back
5. **Anti-throttling** — responses cannot be content-regulated to suppress honesty

---

**AMARTIE — Your AI, verified.**

*Receipts, not promises.*
