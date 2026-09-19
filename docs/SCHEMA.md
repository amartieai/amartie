# AMARTIE Receipt Schema v1.0

Frozen. Breaking changes require a new major version.
Receipts generated under v1.0 verify forever.

## Mismatch object

- type: model_swap | intent_mismatch
- billed: model string billed by the request
- returned: model string returned by the response
- intent: chat | vision | embedding | audio | tool | unspecified
- session_id: session identifier or reset marker
- latency_ms: latency in milliseconds
- ts: ISO-8601 UTC timestamp

## Intent rules

- chat or unspecified → any billed ≠ returned is a swap
- vision / embedding / audio / tool → flag only if the returned model is outside the declared capability family

## Hash

`receipt_hash = SHA-256(canonical_json(mismatches))`

Canonical JSON uses sorted keys, no whitespace, and UTF-8 encoding.
