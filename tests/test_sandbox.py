# Tests for AMARTIE Sandbox Engine

import pytest
import os
from amartie.sandbox import Sandbox, Snapshot, sandbox


class TestSnapshot:
    def test_create_snapshot(self):
        s = Snapshot()
        assert s.kernel_hash is not None
        assert s.filesystem_hash is not None
        assert s.timestamp is not None
    
    def test_to_dict(self):
        s = Snapshot()
        d = s.to_dict()
        assert "timestamp" in d
        assert "kernel_hash" in d
        assert "process_count" in d


class TestSandbox:
    def test_create_sandbox(self):
        sb = Sandbox()
        assert sb.baseline is None
        assert len(sb.get_quarantine()) == 0
    
    def test_install(self):
        sb = Sandbox()
        sb.install()
        assert sb.baseline is not None
    
    def test_enter(self):
        sb = Sandbox()
        result = sb.enter("agent-123", "docker")
        assert result["agent_id"] == "agent-123"
        assert result["isolated"] == True
    
    def test_exit(self):
        sb = Sandbox()
        sb.install()
        sb.enter("agent-123")
        diff = sb.exit("agent-123")
        assert "agent_id" in diff
        assert "timestamp" in diff
    
    def test_quarantine(self):
        sb = Sandbox()
        item = {"id": "suspicious-1", "type": "unknown-file", "path": "/tmp/bad"}
        sb.quarantine(item)
        assert len(sb.get_quarantine()) == 1
        assert sb.get_quarantine()[0]["status"] == "pending_review"
    
    def test_review_quarantine(self):
        sb = Sandbox()
        item = {"id": "suspicious-1", "type": "unknown-file"}
        sb.quarantine(item)
        result = sb.review_quarantine("suspicious-1", "approved", "J1-TRUTH")
        assert result == True
        assert sb.get_quarantine()[0]["status"] == "approved"
    
    def test_get_quarantine(self):
        sb = Sandbox()
        item = {"id": "suspicious-1", "type": "unknown-file"}
        sb.quarantine(item)
        items = sb.get_quarantine()
        assert len(items) == 1


class TestSingleton:
    def test_singleton_exists(self):
        assert sandbox is not None
        assert isinstance(sandbox, Sandbox)
