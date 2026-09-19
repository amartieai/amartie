# AMARTIE Architecture

1. Ingest — reads the session dump
2. Detect — compares billed vs returned, intent-aware
3. Receipt — writes a hash-chained JSON receipt
4. Custody — append-only action log
5. Replay — recomputes and compares against the stored receipt
6. Probes — tests live provider identity and billing behavior
7. Gate — eBPF egress monitor and bypass blocking

Trust model: no trust in the author. Run the verifier, compare the hash, and replay the receipt.
