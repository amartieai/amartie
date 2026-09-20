# AMARTIE security policy

## Scope

This repository is an alpha verification framework for local-first AI tool actions. The code and docs are intended for development, audit, and local testing only. Nothing in this project should be treated as production-grade security for real-world secrets, money movement, or public deployment.

## Reporting vulnerabilities

Please report security issues privately and do not open public issues for vulnerability details.

Use one of the following channels:

- A private security report through the repository's security advisory flow if enabled.
- Contact the maintainers through the official repository contact mechanism before disclosing details publicly.

When reporting:

- include the affected version or commit,
- describe the conditions under which the issue reproduces,
- include steps to verify the issue,
- redact secrets, credentials, tokens, and live payloads.

## Security expectations

- The cockpit server must remain bound to localhost only.
- The default bind target is `127.0.0.1:8715`.
- No secrets should be stored in source, logs, receipts, fixtures, or review artifacts.
- The gate should fail closed: if a judge verdict is missing, invalid, or non-unanimous, the action is refused.
- The receipt is evidence of refusal or approval; it must not be silently discarded.
- Any security-sensitive change should be reviewed against the nine-judge invariants and the alpha limitations documented in the README.

## Alpha limitations

AMARTIE v0.1.0 is not production security. Known limitations include:

- vault public-key encryption is stubbed,
- receipt chain is in-memory only,
- sandbox listings are sampled rather than complete,
- plugin permissions are declared in manifests but not OS-enforced,
- the local server remains localhost-only and must not be exposed publicly.

## Safe use

- Use local-only testing and local-only services.
- Treat the receipt chain as evidence for audit, not as a full security boundary.
- Ensure model-lock, evidence floors, and judge seat checks are preserved during changes.
- Do not deploy AMARTIE with live secrets or public network exposure.

## Disclosure timing

The maintainers aim to acknowledge security reports promptly and to work on a fix without further public disclosure until there is a safe remediation path.
