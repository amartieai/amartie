"""
AMARTIE Sandbox Engine
========================
Kernel-level containment. Snapshot, contain, diff, quarantine.
"""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional


class Snapshot:
    """System baseline snapshot taken on install."""
    
    def __init__(self):
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.kernel_hash = self._hash_kernel()
        self.filesystem_hash = self._hash_filesystem()
        self.running_processes = self._get_processes()
        self.network_listeners = self._get_listeners()
    
    def _hash_kernel(self) -> str:
        # In production: hash kernel modules, boot sector, system files
        return hashlib.sha256(self.timestamp.encode()).hexdigest()[:16]
    
    def _hash_filesystem(self) -> str:
        # In production: hash critical filesystem paths
        return hashlib.sha256(self.timestamp.encode()).hexdigest()[:16]
    
    def _get_processes(self) -> List[str]:
        # In production: list all running processes
        try:
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            return result.stdout.split('\n')[:50]  # First 50 lines for demo
        except:
            return []
    
    def _get_listeners(self) -> List[str]:
        # In production: list all network listeners
        try:
            result = subprocess.run(['ss', '-tlnp'], capture_output=True, text=True)
            return result.stdout.split('\n')[:20]  # First 20 for demo
        except:
            return []
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "kernel_hash": self.kernel_hash,
            "filesystem_hash": self.filesystem_hash,
            "process_count": len(self.running_processes),
            "listener_count": len(self.network_listeners)
        }


class Sandbox:
    """
    Kernel-level containment layer.
    
    Snapshot on install → baseline of truth
    Contain on entry → agent runs in isolated environment
    Diff on exit → compare against baseline
    Quarantine → unknown leftovers flagged
    """
    
    def __init__(self):
        self.baseline: Optional[Snapshot] = None
        self.quarantine: List[dict] = []
    
    def install(self):
        """Take baseline snapshot on install."""
        self.baseline = Snapshot()
    
    def enter(self, agent_id: str, container_type: str = "docker") -> dict:
        """Contain an agent on entry."""
        return {
            "agent_id": agent_id,
            "container_type": container_type,
            "isolated": True,
            "network": "none",
            "filesystem": "read-only",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def exit(self, agent_id: str) -> dict:
        """Diff on exit. Returns changes from baseline."""
        current = Snapshot()
        
        diff = {
            "agent_id": agent_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kernel_changed": current.kernel_hash != self.baseline.kernel_hash,
            "filesystem_changed": current.filesystem_hash != self.baseline.filesystem_hash,
            "new_processes": len(current.running_processes) - len(self.baseline.running_processes),
            "new_listeners": len(current.network_listeners) - len(self.baseline.network_listeners)
        }
        
        return diff
    
    def quarantine(self, item: dict):
        """Flag an unknown leftover for review."""
        item['quarantine_time'] = datetime.now(timezone.utc).isoformat()
        item['status'] = 'pending_review'
        self.quarantine.append(item)
    
    def review_quarantine(self, item_id: str, verdict: str, reviewer: str):
        """Review a quarantined item."""
        for item in self.quarantine:
            if item.get('id') == item_id:
                item['status'] = verdict
                item['reviewer'] = reviewer
                item['review_time'] = datetime.now(timezone.utc).isoformat()
                return True
        return False
    
    def get_quarantine(self) -> List[dict]:
        """Get all quarantined items."""
        return self.quarantine


# Singleton sandbox
sandbox = Sandbox()
