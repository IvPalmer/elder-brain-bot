"""Tests for context compaction service."""

from src.claude.compaction import CompactionService, ConversationTurn


def test_no_compaction_under_threshold():
    service = CompactionService(max_turns_before_compact=10)
    turns = [ConversationTurn(role="user", content=f"msg {i}") for i in range(5)]
    result = service.maybe_compact(turns)
    assert result == turns


def test_compaction_preserves_recent():
    service = CompactionService(
        max_turns_before_compact=5,
        recent_turns_to_keep=3,
    )
    turns = [ConversationTurn(role="user", content=f"msg {i}") for i in range(10)]
    result = service.maybe_compact(turns)
    assert len(result) == 4
    assert result[0].role == "system"
    assert result[-1].content == "msg 9"


def test_compaction_summary_contains_key_info():
    service = CompactionService(
        max_turns_before_compact=3,
        recent_turns_to_keep=1,
    )
    turns = [
        ConversationTurn(role="user", content="Please fix the auth bug in login.py"),
        ConversationTurn(role="assistant", content="I found the issue at line 42"),
        ConversationTurn(role="user", content="Great, now add tests"),
        ConversationTurn(role="assistant", content="Done, all tests pass"),
    ]
    result = service.maybe_compact(turns)
    summary = result[0].content
    assert "auth" in summary.lower() or "login" in summary.lower() or "fix" in summary.lower()
