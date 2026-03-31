"""Tests for per-tool access control lists."""

import pytest
from src.security.tool_acl import ToolACL, ToolACLManager


@pytest.fixture
def manager():
    m = ToolACLManager()
    m.add_rule(ToolACL(tool_name="Bash", denied_users={999}))
    m.add_rule(ToolACL(tool_name="Write", allowed_users={1, 2}))
    m.add_rule(ToolACL(tool_name="WebFetch", max_uses_per_session=5))
    return m


def test_allow_by_default(manager):
    allowed, _ = manager.check("Read", user_id=1)
    assert allowed is True


def test_deny_by_user(manager):
    allowed, reason = manager.check("Bash", user_id=999)
    assert allowed is False
    assert "denied" in reason


def test_allow_by_allowlist(manager):
    allowed, _ = manager.check("Write", user_id=1)
    assert allowed is True


def test_deny_not_in_allowlist(manager):
    allowed, reason = manager.check("Write", user_id=999)
    assert allowed is False
    assert "not in allowed" in reason


def test_session_limit(manager):
    for _ in range(5):
        manager.record_use("sess-1", "WebFetch")
    allowed, reason = manager.check("WebFetch", user_id=1, session_id="sess-1")
    assert allowed is False
    assert "Session limit" in reason


def test_session_limit_not_exceeded(manager):
    manager.record_use("sess-1", "WebFetch")
    allowed, _ = manager.check("WebFetch", user_id=1, session_id="sess-1")
    assert allowed is True


def test_filter_tools_for_user(manager):
    tools = ["Read", "Write", "Bash", "WebFetch"]
    filtered = manager.filter_tools_for_user(tools, user_id=999)
    assert "Read" in filtered
    assert "Write" not in filtered
    assert "Bash" not in filtered
    assert "WebFetch" in filtered


def test_cleanup_session(manager):
    manager.record_use("sess-1", "WebFetch")
    manager.cleanup_session("sess-1")
    allowed, _ = manager.check("WebFetch", user_id=1, session_id="sess-1")
    assert allowed is True
