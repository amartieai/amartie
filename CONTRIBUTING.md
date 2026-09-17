# Contributing to AMARTIE

> Thank you for helping build the world's most trustworthy AI security framework.

---

## The Two Tracks

Every contribution falls into one of two tracks:

### R — Research (Building New Things)

You're creating something that didn't exist before:
- New gate features (new judge types, new verification methods)
- New plugin types
- New product features (cockpit improvements, new scenes)
- New architecture components
- Performance improvements
- New agent swarm capabilities

**Label:** `R` (e.g., `R: Add latency budget enforcement to J9`)

### D — Defense (Securing What Exists)

You're making the system harder to attack:
- Security audits of existing code
- Bug fixes (especially security-related)
- Sandbox hardening
- Encrypted vault improvements
- Receipt chain integrity improvements
- Anti-tampering measures
- Forensic analysis of past incidents

**Label:** `D` (e.g., `D: Harden vault decryption against timing attacks`)

---

## How to Contribute

1. **Find an issue** labeled `R` or `D` in the issue tracker
2. **Comment** on the issue to claim it (prevents duplicate work)
3. **Fork** the repo
4. **Create a branch** (`R/your-feature-name` or `D/your-fix-name`)
5. **Write code** with tests
6. **Submit a PR** referencing the issue
7. **Get reviewed** by maintainers
8. **Merge** → earn shares

---

## R&D Shares

When your PR is merged, you earn shares based on:

| Factor | Weight |
|--------|--------|
| Lines of code | Medium |
| Complexity | High |
| Security impact (for D) | Very High |
| Innovation (for R) | Very High |
| Test coverage | Medium |
| Documentation | Low |

Shares are calculated transparently. The investment strategy that grows the pool is proprietary.

---

## Code Standards

- **Every function documented** (docstrings)
- **Every change tested** (pytest)
- **Every security change reviewed** (2+ maintainers)
- **No silent failures** (errors are loud)
- **No trust without verification** (receipts for everything)

---

## Code of Conduct

- Be blunt, not rude
- Verify before claiming
- Receipts, not promises
- The owner's ruling is final on architectural decisions

---

## Questions?

Open an issue with the `question` label. A maintainer will respond.

---

*Receipts, not promises.*
