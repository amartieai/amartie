# Tests for AMARTIE Receipt Engine
import pytest

from amartie.receipt import Receipt, ReceiptChain


class TestReceipt:
    def test_create_receipt(self):
        r = Receipt(
            action_id="test-123",
            action_type="email-send",
            payload_hash="abc123",
            verdicts=[{"judge": "J1", "verdict": "PASS"}],
            previous_hash="GENESIS",
        )
        assert r.action_id == "test-123"
        assert r.previous_hash == "GENESIS"
        assert len(r.hash) == 64

    def test_verify(self):
        r = Receipt(
            action_id="test",
            action_type="test",
            payload_hash="test",
            verdicts=[],
            previous_hash="GENESIS",
        )
        assert r.verify() is True

    def test_tamper_detection(self):
        r = Receipt(
            action_id="test",
            action_type="test",
            payload_hash="test",
            verdicts=[],
            previous_hash="GENESIS",
        )
        r.hash = "tampered"
        assert r.verify() is False

    def test_requires_sha256_hash_algorithm(self):
        with pytest.raises(ValueError):
            Receipt(
                action_id="bad",
                action_type="test",
                payload_hash="hash",
                verdicts=[],
                hash_algorithm="sha1",
            )

    def test_from_dict_preserves_timestamp(self):
        r = Receipt(
            action_id="test",
            action_type="test",
            payload_hash="test",
            verdicts=[],
            previous_hash="GENESIS",
            timestamp="2026-09-18T12:00:00+00:00",
        )
        d = r.to_dict()
        r2 = Receipt.from_dict(d)
        assert r2.timestamp == "2026-09-18T12:00:00+00:00"
        assert r2.verify() is True
        assert r2.hash == r.hash

    def test_from_dict_defaults_timestamp(self):
        # a stored hash is REQUIRED (fail closed on missing integrity field)
        r = Receipt.from_dict({
            "action_id": "test",
            "action_type": "test",
            "payload_hash": "test",
            "hash": Receipt(
                action_id="test", action_type="test", payload_hash="test",
                verdicts=[], previous_hash="",
            ).hash,
        })
        assert r.timestamp is not None

    def test_from_dict_missing_hash_fails_closed(self):
        # review finding #5: a missing stored hash is malformed, never repaired
        with pytest.raises(ValueError, match="missing stored hash"):
            Receipt.from_dict({
                "action_id": "test",
                "action_type": "test",
                "payload_hash": "test",
            })

    def test_metadata_is_hashed_and_serialized(self):
        # review finding #1: metadata changes must break the hash
        r1 = Receipt(action_id="a", action_type="t", payload_hash="p",
                     verdicts=[], metadata={"k": "v1"})
        r2 = Receipt(action_id="a", action_type="t", payload_hash="p",
                     verdicts=[], metadata={"k": "v2"})
        assert r1.hash != r2.hash
        # metadata survives the round trip
        r3 = Receipt.from_dict(r1.to_dict())
        assert r3.metadata == {"k": "v1"}
        assert r3.verify()

    def test_metadata_tamper_detected(self):
        r = Receipt(action_id="a", action_type="t", payload_hash="p",
                    verdicts=[], metadata={"k": "v1"})
        r.metadata["k"] = "tampered"
        assert not r.verify()

    def test_chain_genesis_link_enforced(self):
        # review finding #4: first receipt must anchor to GENESIS
        r = Receipt(action_id="a", action_type="t", payload_hash="p",
                    verdicts=[], previous_hash="arbitrary-value")
        chain = ReceiptChain()
        chain.receipts.append(r)
        assert not chain.verify_chain()

    def test_payload_tamper_detectable(self):
        r = Receipt(
            action_id="test",
            action_type="test",
            payload_hash="original",
            verdicts=[],
        )
        d = r.to_dict()
        d["payload_hash"] = "modified"
        r2 = Receipt.from_dict(d)
        assert r2.verify() is False

    def test_verdict_tamper_detectable(self):
        r = Receipt(
            action_id="test",
            action_type="test",
            payload_hash="test",
            verdicts=[{"judge_id": "J1", "verdict": "PASS"}],
        )
        d = r.to_dict()
        d["verdicts"][0]["verdict"] = "DISSENT"
        r2 = Receipt.from_dict(d)
        assert r2.verify() is False

    def test_previous_hash_tamper_fails(self):
        r = Receipt(
            action_id="test",
            action_type="test",
            payload_hash="test",
            verdicts=[],
            previous_hash="GENESIS",
        )
        d = r.to_dict()
        d["previous_hash"] = "FAKE"
        r2 = Receipt.from_dict(d)
        assert r2.verify() is False


class TestReceiptChain:
    def test_create_chain(self):
        c = ReceiptChain("test-chain")
        assert c.chain_id == "test-chain"
        assert len(c.receipts) == 0

    def test_append(self):
        c = ReceiptChain("test")
        r = Receipt("1", "test", "hash", [], "GENESIS")
        c.append(r)
        assert len(c.receipts) == 1
        assert c.get_latest_hash() == r.hash

    def test_chain_integrity(self):
        c = ReceiptChain("test")
        r1 = Receipt("1", "test", "hash1", [], "GENESIS")
        r2 = Receipt("2", "test", "hash2", [], r1.hash)
        c.append(r1)
        c.append(r2)
        assert c.verify_chain() is True

    def test_tamper_detection(self):
        c = ReceiptChain("test")
        r1 = Receipt("1", "test", "hash1", [], "GENESIS")
        c.append(r1)
        r1.hash = "tampered"
        assert c.verify_chain() is False

    def test_get_receipt(self):
        c = ReceiptChain("test")
        r = Receipt("find-me", "test", "hash", [], "GENESIS")
        c.append(r)
        found = c.get_receipt("find-me")
        assert found is not None
        assert found.action_id == "find-me"

    def test_get_latest_hash_genesis(self):
        c = ReceiptChain("test")
        assert c.get_latest_hash() == "GENESIS"

    def test_chain_append_links_correctly(self):
        """Verify that appending receipts creates proper hash chain links."""
        c = ReceiptChain("link-test")
        r1 = Receipt("1", "test", "hash1", [], "GENESIS")
        r2 = Receipt("2", "test", "hash2", [])
        r3 = Receipt("3", "test", "hash3", [])
        
        c.append(r1)
        c.append(r2)
        c.append(r3)
        
        # r2 should link to r1
        assert r2.previous_hash == r1.hash
        # r3 should link to r2
        assert r3.previous_hash == r2.hash
        # Chain should be valid
        assert c.verify_chain() is True

    def test_chain_tamper_at_link_fails(self):
        """Verify that tampering with a link in the chain is detected."""
        c = ReceiptChain("tamper-test")
        r1 = Receipt("1", "test", "hash1", [], "GENESIS")
        r2 = Receipt("2", "test", "hash2", [])
        
        c.append(r1)
        c.append(r2)
        
        # Tamper with r2's previous_hash
        r2.previous_hash = "BROKEN"
        assert c.verify_chain() is False
