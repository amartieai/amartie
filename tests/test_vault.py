# Tests for AMARTIE Vault Engine

import pytest
from amartie.vault import Vault, SwarmTask, AntiTamper


class TestVault:
    def test_create_vault(self):
        v = Vault("/tmp/test-vault")
        assert v.vault_path == "/tmp/test-vault"
        assert len(v.contents) == 0
    
    def test_store_and_retrieve(self):
        v = Vault("/tmp/test-vault")
        v.store("tool1", b"secret data", "keyhash123")
        result = v.retrieve("tool1", "keyhash123")
        assert result == b"secret data"
    
    def test_retrieve_wrong_key(self):
        v = Vault("/tmp/test-vault")
        v.store("tool1", b"secret data", "keyhash123")
        result = v.retrieve("tool1", "wrongkey")
        assert result is None
    
    def test_delete(self):
        v = Vault("/tmp/test-vault")
        v.store("tool1", b"secret data", "keyhash123")
        v.delete("tool1", "keyhash123")
        assert v.retrieve("tool1", "keyhash123") is None
    
    def test_access_log(self):
        v = Vault("/tmp/test-vault")
        v.store("tool1", b"data", "keyhash123")
        v.retrieve("tool1", "keyhash123")
        assert len(v.access_log) == 2


class TestSwarmTask:
    def test_create_task(self):
        t = SwarmTask(
            agent_id="agent-1",
            task="Build feature X",
            path=["step1", "step2", "step3"],
            expected_outputs=["output1"],
            deadline="2026-09-18T00:00:00Z"
        )
        assert t.agent_id == "agent-1"
        assert t.status == "assigned"
    
    def test_check_deviation(self):
        t = SwarmTask(
            agent_id="agent-1",
            task="Build feature X",
            path=["step1", "step2", "step3"],
            expected_outputs=["output1"],
            deadline="2026-09-18T00:00:00Z"
        )
        # Follow correct path
        assert t.check_deviation(["step1", "step2", "step3"]) == False
        # Deviate
        assert t.check_deviation(["step1", "step2", "wrong_step"]) == True
    
    def test_complete(self):
        t = SwarmTask(
            agent_id="agent-1",
            task="Build feature X",
            path=["step1", "step2"],
            expected_outputs=["output1"],
            deadline="2026-09-18T00:00:00Z"
        )
        t.complete(["output1"])
        assert t.status == "completed"
        assert t.outputs == ["output1"]


class TestAntiTamper:
    def test_create(self):
        at = AntiTamper()
        assert len(at.baseline_hashes) == 0
    
    def test_register_and_check(self):
        at = AntiTamper()
        at.register_file("/etc/passwd", "abc123")
        assert at.check_file("/etc/passwd", "abc123") == True
    
    def test_tamper_detection(self):
        at = AntiTamper()
        at.register_file("/etc/passwd", "abc123")
        assert at.check_file("/etc/passwd", "tampered") == False
    
    def test_get_alerts(self):
        at = AntiTamper()
        at.register_file("/etc/passwd", "abc123")
        at.check_file("/etc/passwd", "tampered")
        alerts = at.get_alerts()
        assert len(alerts) == 1
        assert alerts[0]["path"] == "/etc/passwd"
