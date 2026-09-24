"""
AMARTIE Sandbox Engine (Part 2)
================================
Vault, Swarm, and Anti-Tampering components.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional


class Vault:
    """
    Encrypted tool vault. User's tools are stored encrypted at rest.
    Trojan AIs can't access them without the owner's keys.
    """
    
    def __init__(self, vault_path: str = "~/.amartie/vault"):
        self.vault_path = vault_path
        self.contents: Dict[str, bytes] = {}  # Encrypted contents
        self.key_hashes: Dict[str, str] = {}  # key hash per tool, for key check
        self.access_log: List[dict] = []
    
    def store(self, tool_name: str, tool_data: bytes, key_hash: str):
        """Store a tool in encrypted form."""
        # In production: encrypt with owner's public key
        self.contents[tool_name] = tool_data
        self.key_hashes[tool_name] = key_hash
        self._log_access("store", tool_name, key_hash)
    
    def retrieve(self, tool_name: str, key_hash: str) -> Optional[bytes]:
        """Retrieve a tool (requires correct key)."""
        if tool_name not in self.contents:
            self._log_access("retrieve-miss", tool_name, key_hash)
            return None
        
        if self.key_hashes.get(tool_name) != key_hash:
            self._log_access("retrieve-miss", tool_name, key_hash)
            return None
        
        self._log_access("retrieve-hit", tool_name, key_hash)
        return self.contents[tool_name]
    
    def delete(self, tool_name: str, key_hash: str):
        """Delete a tool from the vault (requires correct key)."""
        if tool_name not in self.contents:
            return
        if self.key_hashes.get(tool_name) != key_hash:
            self._log_access("retrieve-miss", tool_name, key_hash)
            return
        del self.contents[tool_name]
        del self.key_hashes[tool_name]
        self._log_access("delete", tool_name, key_hash)
    
    def _log_access(self, action: str, tool_name: str, key_hash: str):
        self.access_log.append({
            "action": action,
            "tool_name": tool_name,
            "key_hash": key_hash[:8] + "...",  # Truncate for security
            "timestamp": datetime.now(timezone.utc).isoformat()
        })


class SwarmTask:
    """Exact task assignment for a swarm agent."""
    
    def __init__(self, agent_id: str, task: str, path: List[str], 
                 expected_outputs: List[str], deadline: str):
        self.agent_id = agent_id
        self.task = task
        self.path = path  # Exact path the agent must follow
        self.expected_outputs = expected_outputs
        self.deadline = deadline
        self.status = "assigned"
        self.outputs: List[str] = []
        self.deviation: Optional[str] = None
    
    def check_deviation(self, actual_path: List[str]) -> bool:
        """Check if the agent deviated from its assigned path."""
        if actual_path != self.path:
            self.deviation = f"Expected {self.path}, got {actual_path}"
            self.status = "deviated"
            return True
        return False
    
    def complete(self, outputs: List[str]):
        """Mark the task as complete."""
        self.outputs = outputs
        self.status = "completed"
    
    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "task": self.task,
            "path": self.path,
            "expected_outputs": self.expected_outputs,
            "deadline": self.deadline,
            "status": self.status,
            "outputs": self.outputs,
            "deviation": self.deviation
        }


class AntiTamper:
    """Detect and prevent tampering with the system."""
    
    def __init__(self):
        self.baseline_hashes: Dict[str, str] = {}
        self.alerts: List[dict] = []
    
    def register_file(self, path: str, expected_hash: str):
        """Register a file for tamper monitoring."""
        self.baseline_hashes[path] = expected_hash
    
    def check_file(self, path: str, actual_hash: str) -> bool:
        """Check if a file has been tampered with."""
        if path not in self.baseline_hashes:
            return True  # Unknown file
        
        if self.baseline_hashes[path] != actual_hash:
            self.alerts.append({
                "path": path,
                "expected": self.baseline_hashes[path],
                "actual": actual_hash,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            return False  # Tampered!
        
        return True  # Clean
    
    def get_alerts(self) -> List[dict]:
        """Get all tamper alerts."""
        return self.alerts
    
    def clear_alerts(self):
        """Clear all alerts."""
        self.alerts = []
