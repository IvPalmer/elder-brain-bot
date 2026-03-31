"""Tests for session pagination."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from src.claude.session import ClaudeSession, paginate_sessions


def _make_session(session_id: str, last_used_offset: int) -> ClaudeSession:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return ClaudeSession(
        session_id=session_id,
        user_id=1,
        project_path=Path("/tmp"),
        created_at=base,
        last_used=base + timedelta(hours=last_used_offset),
    )


def test_paginate_returns_page():
    sessions = [_make_session(f"s{i}", i) for i in range(20)]
    page = paginate_sessions(sessions, page_size=5, offset=0)
    assert len(page.items) == 5
    assert page.has_more is True
    assert page.total == 20


def test_paginate_last_page():
    sessions = [_make_session(f"s{i}", i) for i in range(7)]
    page = paginate_sessions(sessions, page_size=5, offset=5)
    assert len(page.items) == 2
    assert page.has_more is False


def test_paginate_empty():
    page = paginate_sessions([], page_size=5, offset=0)
    assert len(page.items) == 0
    assert page.has_more is False
