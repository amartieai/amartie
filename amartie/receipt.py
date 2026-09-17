"""
AMARTIE Receipt Engine
=======================
Hash-chained, tamper-evident receipt system.
Every action generates a receipt. Every receipt links to the previous.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import List, Optional


class Receipt:
    """A single hash-chained receipt."""
    
    def __init__(self, action_id: str, action_type: str, 
                 payload_hash: str, verdicts: List[dict], 
                 previous_hash: str = "", metadata: dict = None):
        self.action_id = action_id
        self.action_type = action_type
        self.payload_hash = payload_hash
        self.verdicts = verdicts
        self.previous_hash = previous_hash
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        content = json.dumps({
            "action_id": self.action_id,
            "action_type": self.action_type,
            "payload_hash": self.payload_hash,
            "verdicts": self.verdicts,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def verify(self) -> bool:
        """Verify this receipt's hash is correct."""
        return self.hash == self._compute_hash()
    
    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "payload_hash": self.payload_hash,
            "verdicts": self.verdicts,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "hash": self.hash
        }


class ReceiptChain:
    """Hash-chained receipt ledger. Tamper-evident."""
    
    def __init__(self, chain_id: str = "main"):
        self.chain_id = chain_id
        self.receipts: List[Receipt] = []
    
    def append(self, receipt: Receipt):
        """Add a receipt to the chain."""
        if self.receipts:
            receipt.previous_hash = self.receipts[-1].hash
        self.receipts.append(receipt)
    
    def verify_chain(self) -> bool:
        """Verify the entire chain is tamper-free."""
        for i, receipt in enumerate(self.receipts):
            if not receipt.verify():
                return False
            if i > 0:
                if receipt.previous_hash != self.receipts[i-1].hash:
                    return False
        return True
    
    def get_receipt(self, action_id: str) -> Optional[Receipt]:
        """Look up a receipt by action ID."""
        for r in self.receipts:
            if r.action_id == action_id:
                return r
        return None
    
    def get_latest_hash(self) -> str:
        """Get the latest receipt hash (anchor)."""
        if self.receipts:
            return self.receipts[-1].hash
        return "GENESIS"
    
    def to_dict(self) -> dict:
        return {
            "chain_id": self.chain_id,
            "receipts": [r.to_dict() for r in self.receipts],
            "chain_valid": self.verify_chain()
        }
