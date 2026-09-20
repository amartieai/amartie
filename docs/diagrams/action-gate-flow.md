# Action Gate Flow

> **Status:** IMPLEMENTED IN ALPHA

## Visual Flow

```mermaid
flowchart TD
    A["Canonical Payload"] --> B["Input Digest"]
    B --> J1["J1 Truth"]
    B --> J2["J2 Boundary"]
    B --> J3["J3 Logic"]
    B --> J4["J4 Completeness"]
    B --> J5["J5 Execution"]
    B --> J6["J6 Owner Intent"]
    B --> J7["J7 Recovery"]
    B --> J8["J8 Trade Integrity"]
    B --> J9["J9 Unity"]

    J1 --> T["Contract Validation"]
    J2 --> T
    J3 --> T
    J4 --> T
    J5 --> T
    J6 --> T
    J7 --> T
    J8 --> T
    J9 --> T

    T --> C{"Exactly 9 valid seats?"}
    C -->|"No"| D["DISSENT"]
    C -->|"Yes"| M{"Model-lock and evidence floor valid?"}
    M -->|"No"| D
    M -->|"Yes"| P{"Every verdict is PASS?"}
    P -->|"No"| D
    P -->|"Yes"| PASS["UNANIMOUS PASS"]

    style A fill:#4A90D9,color:#fff
    style B fill:#F5A623,color:#fff
    style J1 fill:#F5A623,color:#fff
    style J2 fill:#F5A623,color:#fff
    style J3 fill:#F5A623,color:#fff
    style J4 fill:#F5A623,color:#fff
    style J5 fill:#F5A623,color:#fff
    style J6 fill:#F5A623,color:#fff
    style J7 fill:#F5A623,color:#fff
    style J8 fill:#F5A623,color:#fff
    style J9 fill:#F5A623,color:#fff
    style T fill:#F5A623,color:#fff
    style C fill:#F5A623,color:#fff
    style M fill:#F5A623,color:#fff
    style P fill:#F5A623,color:#fff
    style D fill:#D0021B,color:#fff
    style PASS fill:#7ED321,color:#fff
```

## J0 Meta-Auditor

```mermaid
flowchart LR
    J0["J0 META-AUDITOR"] -.->|"Reviews evidence"| R["Receipt Records"]
    J0 -.->|"Non-voting"| G["Cannot Override Dissent"]

    style J0 fill:#BD10E0,color:#fff
    style R fill:#BD10E0,color:#fff
    style G fill:#D0021B,color:#fff
```

**J0 is non-voting.** It reviews the judges and receipt evidence but cannot approve an action by itself. It cannot override a dissent.

## Accessible Text Description

A canonical payload is hashed to create an input digest. The digest is reviewed by nine judges (J1-J9). Each judge validates the contract. The system checks: exactly 9 valid seats? Model-lock and evidence floor valid? Every verdict PASS? If all checks pass, the action is unanimously approved. If any check fails, the action is refused.

## Validation Checks

| Check | Description |
|-------|-------------|
| **Exactly 9 seats** | No more, no less |
| **No duplicates** | Each judge ID must be unique |
| **No unknown IDs** | Only J1-J9 accepted |
| **Model-lock** | Judge must use assigned model (if configured) |
| **Evidence floor** | At least 2 tool calls per judge |
| **Unanimous PASS** | All 9 must return PASS |

## What Happens on Dissent

1. A DISSENT receipt is produced
2. The action is **not** executed
3. The receipt is persisted for audit
4. The caller receives the refusal reason
