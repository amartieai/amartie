# Public Contribution Flow

> **Status:** IMPLEMENTED IN ALPHA

## Visual Flow

```mermaid
flowchart TD
    V["Visitor"] --> R["Run Local Demo"]
    R --> T["Read PASS and DISSENT Receipts"]
    T --> B["Test a Boundary Case"]
    B --> I["Open Reproducible Issue"]
    I --> C["Claim Bounded Contribution"]
    C --> PR["Submit Tested Pull Request"]
    PR --> REV["Independent Review"]
    REV --> M["Merge and Publish Receipt"]

    style V fill:#4A90D9,color:#fff
    style R fill:#7ED321,color:#fff
    style T fill:#7ED321,color:#fff
    style B fill:#F5A623,color:#fff
    style I fill:#F5A623,color:#fff
    style C fill:#F5A623,color:#fff
    style PR fill:#BD10E0,color:#fff
    style REV fill:#BD10E0,color:#fff
    style M fill:#7ED321,color:#fff
```

## Accessible Text Description

A visitor runs the local demo. They read PASS and DISSENT receipts to understand the system. They test a boundary case. They open a reproducible issue. They claim a bounded contribution. They submit a tested pull request. The request is independently reviewed. On merge, a receipt is published.

## Public Call to Action

| Action | Description |
|--------|-------------|
| **RUN** | Reproduce the local gate |
| **TEST** | Try to find a bypass |
| **BUILD** | Submit a bounded, tested improvement |

## Contribution Ladder

1. **Docs** — Improve setup docs for Windows or Linux
2. **Plugins** — Add a safe, no-network studio
3. **Gate/Receipts** — Contracts, roster validation, evidence, replay
4. **Security review** — Threat modeling, tamper tests, policy review

## Incentives

- Security-researcher bounties for verified gate escapes
- Contributor credits and public acknowledgments
- Sponsored pilot integrations for startups
- Grants or paid contracts for building judges, replay fixtures, observability

**No rewards for:** raw traffic volume, unanimous PASS rates, or suppressed dissent.
