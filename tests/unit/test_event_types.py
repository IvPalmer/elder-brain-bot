"""Tests for richer event types."""

from src.events.types import (
    ToolExecutedEvent,
    FileChangedEvent,
    SessionStartEvent,
    SessionEndEvent,
    TaskCreatedEvent,
    TaskCompletedEvent,
)


def test_tool_executed_event():
    e = ToolExecutedEvent(
        tool_name="Read",
        duration_ms=150.0,
        success=True,
        user_id=1,
    )
    assert e.event_type == "ToolExecutedEvent"
    assert e.tool_name == "Read"


def test_file_changed_event():
    e = FileChangedEvent(
        file_path="/tmp/test.py",
        change_type="edit",
        user_id=1,
    )
    assert e.change_type == "edit"


def test_session_events():
    start = SessionStartEvent(user_id=1, session_id="s1")
    end = SessionEndEvent(user_id=1, session_id="s1", total_cost=0.5)
    assert start.session_id == "s1"
    assert end.total_cost == 0.5


def test_task_events():
    created = TaskCreatedEvent(task_id="t1", task_name="fix bug")
    completed = TaskCompletedEvent(task_id="t1", success=True)
    assert created.task_name == "fix bug"
    assert completed.success is True
