"""Tests for tool execution tracking."""

import pytest
from datetime import UTC, datetime

from src.claude.tool_execution import ToolExecution, ToolExecutionTracker


def test_tool_execution_creation():
    te = ToolExecution(
        tool_name="Read",
        start_time=datetime.now(UTC),
        duration_ms=150.0,
        success=True,
    )
    assert te.tool_name == "Read"
    assert te.success is True
    assert te.error_type is None


def test_tracker_record_and_summarize():
    tracker = ToolExecutionTracker()
    tracker.record(
        ToolExecution(
            tool_name="Read",
            start_time=datetime.now(UTC),
            duration_ms=100.0,
            success=True,
        )
    )
    tracker.record(
        ToolExecution(
            tool_name="Read",
            start_time=datetime.now(UTC),
            duration_ms=200.0,
            success=True,
        )
    )
    tracker.record(
        ToolExecution(
            tool_name="Bash",
            start_time=datetime.now(UTC),
            duration_ms=500.0,
            success=False,
            error_type="timeout",
        )
    )

    summary = tracker.summarize()
    assert summary["total_executions"] == 3
    assert summary["success_rate"] == pytest.approx(2 / 3)
    assert summary["by_tool"]["Read"]["count"] == 2
    assert summary["by_tool"]["Read"]["avg_duration_ms"] == pytest.approx(150.0)
    assert summary["by_tool"]["Bash"]["error_types"] == {"timeout": 1}


def test_tracker_empty_summarize():
    tracker = ToolExecutionTracker()
    summary = tracker.summarize()
    assert summary["total_executions"] == 0
    assert summary["success_rate"] == 1.0
    assert summary["by_tool"] == {}
