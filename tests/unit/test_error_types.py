"""Tests for structured error classification."""

from src.claude.error_types import ErrorCategory, classify_error, is_transient_error


def test_classify_timeout():
    from src.claude.exceptions import ClaudeTimeoutError

    err = ClaudeTimeoutError("timed out")
    assert classify_error(err) == ErrorCategory.TIMEOUT


def test_classify_mcp_error():
    from src.claude.exceptions import ClaudeMCPError

    err = ClaudeMCPError("mcp server failed")
    assert classify_error(err) == ErrorCategory.MCP


def test_classify_process_error():
    from src.claude.exceptions import ClaudeProcessError

    err = ClaudeProcessError("process crashed")
    assert classify_error(err) == ErrorCategory.PROCESS


def test_classify_permission():
    err = PermissionError("denied")
    assert classify_error(err) == ErrorCategory.PERMISSION


def test_classify_unknown():
    err = RuntimeError("something weird")
    assert classify_error(err) == ErrorCategory.UNKNOWN


def test_is_transient():
    from src.claude.exceptions import ClaudeProcessError, ClaudeTimeoutError

    assert is_transient_error(ClaudeTimeoutError("t")) is True
    assert is_transient_error(ClaudeProcessError("p")) is False
