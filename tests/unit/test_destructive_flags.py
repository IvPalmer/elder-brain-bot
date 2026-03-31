"""Tests for destructive tool use detection."""

from src.claude.monitor import is_destructive_tool_use


def test_rm_is_destructive():
    assert is_destructive_tool_use("Bash", {"command": "rm -rf /tmp/test"}) is True


def test_write_is_destructive():
    assert is_destructive_tool_use("Write", {"file_path": "/tmp/test.py", "content": "x"}) is True


def test_read_is_not_destructive():
    assert is_destructive_tool_use("Read", {"file_path": "/tmp/test.py"}) is False


def test_grep_is_not_destructive():
    assert is_destructive_tool_use("Grep", {"pattern": "foo"}) is False


def test_edit_is_destructive():
    assert is_destructive_tool_use("Edit", {"file_path": "/tmp/test.py"}) is True


def test_ls_bash_is_not_destructive():
    assert is_destructive_tool_use("Bash", {"command": "ls -la"}) is False


def test_git_push_is_destructive():
    assert is_destructive_tool_use("Bash", {"command": "git push origin main"}) is True
