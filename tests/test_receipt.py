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
