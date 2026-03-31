"""Tests for tool filtering before sending to Claude."""

from src.claude.sdk_integration import filter_denied_tools


def test_filter_denied_tools_removes_disallowed():
    allowed = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
    disallowed = ["Bash", "Write"]
    result = filter_denied_tools(allowed, disallowed)
    assert result == ["Read", "Edit", "Glob", "Grep"]


def test_filter_denied_tools_empty_disallowed():
    allowed = ["Read", "Write"]
    result = filter_denied_tools(allowed, [])
    assert result == ["Read", "Write"]


def test_filter_denied_tools_none_disallowed():
    allowed = ["Read", "Write"]
    result = filter_denied_tools(allowed, None)
    assert result == ["Read", "Write"]


def test_filter_denied_tools_all_disallowed():
    allowed = ["Read"]
    disallowed = ["Read"]
    result = filter_denied_tools(allowed, disallowed)
    assert result == []
