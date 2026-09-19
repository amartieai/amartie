from pathlib import Path

from amartie.engine import check_session

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_pass_fixture_clean():
    assert check_session(FIXTURES / "pass.json") == []


def test_fail_fixture_detects_swap():
    mismatches = check_session(FIXTURES / "fail.json")
    assert len(mismatches) == 1
    mismatch = mismatches[0]
    assert mismatch["billed"] == "moonshotai/kimi-k3"
    assert mismatch["returned"] == "deepseek/deepseek-v4-flash"
    assert mismatch["latency_ms"] == 4100
    assert mismatch["session_id"] == "sess-xyz789"
