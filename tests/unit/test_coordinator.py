"""Tests for coordinator mode (parallel worker orchestration)."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.claude.coordinator import (
    CoordinatorManager,
    CoordinatorSession,
    WorkerStatus,
    WorkerTask,
)
from src.claude.sdk_integration import ClaudeResponse


@pytest.fixture
def mock_claude():
    claude = AsyncMock()
    claude.run_command = AsyncMock(
        return_value=ClaudeResponse(
            content="Worker result",
            session_id="test-sess",
            cost=0.01,
            duration_ms=100,
            num_turns=1,
        )
    )
    # Provide a session_manager mock
    claude.session_manager = MagicMock()
    return claude


@pytest.fixture
def coordinator(mock_claude):
    return CoordinatorManager(claude=mock_claude, max_concurrent_workers=3)


def test_create_session(coordinator):
    session = coordinator.create_session(user_id=123)
    assert session.user_id == 123
    assert session.session_id is not None
    assert len(session.workers) == 0


def test_add_worker(coordinator):
    session = coordinator.create_session(user_id=123)
    worker = coordinator.add_worker(
        session, "Research auth", "Investigate auth module", Path("/tmp")
    )
    assert worker.status == WorkerStatus.PENDING
    assert worker.worker_id in session.workers


@pytest.mark.asyncio
async def test_run_all_completes_workers(coordinator, mock_claude):
    session = coordinator.create_session(user_id=123)
    coordinator.add_worker(session, "Task A", "Do A", Path("/tmp"))
    coordinator.add_worker(session, "Task B", "Do B", Path("/tmp"))

    results = await coordinator.run_all(session)
    assert len(results) == 2
    assert all(w.status == WorkerStatus.COMPLETED for w in results)
    assert mock_claude.run_command.call_count == 2


@pytest.mark.asyncio
async def test_run_all_handles_failure(coordinator, mock_claude):
    mock_claude.run_command = AsyncMock(side_effect=RuntimeError("boom"))

    session = coordinator.create_session(user_id=123)
    coordinator.add_worker(session, "Task A", "Do A", Path("/tmp"))

    results = await coordinator.run_all(session)
    assert results[0].status == WorkerStatus.FAILED
    assert "boom" in results[0].error


def test_session_all_done(coordinator):
    session = coordinator.create_session(user_id=123)
    w1 = coordinator.add_worker(session, "A", "a", Path("/tmp"))
    w2 = coordinator.add_worker(session, "B", "b", Path("/tmp"))

    assert not session.all_done

    w1.status = WorkerStatus.COMPLETED
    w2.status = WorkerStatus.FAILED
    assert session.all_done


def test_summarize_results(coordinator):
    session = coordinator.create_session(user_id=123)
    w = coordinator.add_worker(session, "Research", "Do research", Path("/tmp"))
    w.status = WorkerStatus.COMPLETED
    w.result = ClaudeResponse(
        content="Found the bug at line 42",
        session_id="s",
        cost=0.01,
        duration_ms=100,
        num_turns=1,
    )

    summary = coordinator.summarize_results(session)
    assert "Research" in summary
    assert "Found the bug" in summary


@pytest.mark.asyncio
async def test_worker_callback(coordinator, mock_claude):
    completed = []

    session = coordinator.create_session(user_id=123)
    coordinator.add_worker(session, "Task", "Do it", Path("/tmp"))

    await coordinator.run_all(session, on_worker_complete=lambda w: completed.append(w))
    assert len(completed) == 1
    assert completed[0].status == WorkerStatus.COMPLETED
