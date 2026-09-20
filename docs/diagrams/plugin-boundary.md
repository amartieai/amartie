# Plugin Boundary

> **Status:** IMPLEMENTED IN ALPHA (manifest check)
> **Future:** OS-level enforcement (not in v0.1)

## Visual Boundary

```mermaid
flowchart LR
    P["Plugin Request"] --> M["Manifest Permission Check"]
    M -->|"Undeclared capability"| R["Reject + Receipt"]
    M -->|"Declared capability"| D["Dry Run / Canonical Payload"]
    D --> G["JudgeGate.verify_action"]
    G -->|"Dissent"| R
    G -->|"Pass"| A["Capability Adapter"]
    A --> E["External or Local Effect"]
    E --> Q["Result Receipt"]

    style P fill:#4A90D9,color:#fff
    style M fill:#F5A623,color:#fff
    style D fill:#F5A623,color:#fff
    style G fill:#F5A623,color:#fff
    style R fill:#D0021B,color:#fff
    style A fill:#7ED321,color:#fff
    style E fill:#7ED321,color:#fff
    style Q fill:#BD10E0,color:#fff
```

## Accessible Text Description

A plugin makes a request. The system checks the plugin's manifest to see if the capability is declared. If not declared, the request is rejected and a receipt is produced. If declared, a dry-run canonical payload is created and sent to `JudgeGate.verify_action`. If the gate returns dissent, the request is rejected. If the gate passes, the capability adapter executes the action and produces a result receipt.

## Boundary Labels (Red = Restricted)

| Boundary | Status | Description |
|----------|--------|-------------|
| **Network access** | Declared in manifest | Plugin must declare network access |
| **Subprocess execution** | Declared in manifest | Plugin must declare subprocess use |
| **Filesystem write** | Declared in manifest | Plugin must declare write access |
| **Credentials** | Declared in manifest | Plugin must declare credential use |
| **External APIs** | Declared in manifest | Plugin must declare API access |
| **Mail/money/messaging** | Declared in manifest | Plugin must declare sensitive actions |

## Important Distinction

**A manifest is not OS enforcement.** It declares intent. The adapter and platform boundary must enforce it. Future versions may add kernel-level enforcement (see "Proposed Future Architecture" below).

## Proposed Future Architecture

```mermaid
flowchart LR
    P["Plugin"] -->|"syscall"| K["Kernel eBPF Gate"]
    K -->|"allowed"| OS["OS Execution"]
    K -->|"blocked"| R["Reject + Receipt"]

    style K fill:#9B9B9B,color:#fff
    style OS fill:#9B9B9B,color:#fff
    style R fill:#D0021B,color:#fff
```

> **Status:** PROPOSED FUTURE ARCHITECTURE
> Current v0.1 does not provide kernel-level enforcement.
