"""Coordinator mode for parallel Claude worker orchestration.

Inspired by Claude Code's coordinatorMode.ts which spawns parallel
workers for complex requests. The coordinator delegates tool work
to workers while maintaining conversation with the user.

This module provides the foundation for:
- Spawning parallel Claude sessions (workers)
- Managing worker lifecycle (start, continue, stop)
- Collecting and merging worker results
- Inter-worker communication via the EventBus
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import structlog

from ..events.bus import EventBus
from .facade import ClaudeIntegration, agent_context
from .sdk_integration import ClaudeResponse, StreamUpdate

logger = structlog.get_logger()


class WorkerStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class WorkerTask:
    """A task assigned to a worker."""

    worker_id: str
    description: str
    prompt: str
    working_directory: Path
    status: WorkerStatus = WorkerStatus.PENDING
    result: Optional[ClaudeResponse] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class CoordinatorSession:
    """Manages parallel workers for a coordinator session."""

    session_id: str
    user_id: int
    workers: Dict[str, WorkerTask] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def active_workers(self) -> List[WorkerTask]:
        return [w for w in self.workers.values() if w.status == WorkerStatus.RUNNING]

    @property
    def completed_workers(self) -> List[WorkerTask]:
        return [
            w
            for w in self.workers.values()
            if w.status in (WorkerStatus.COMPLETED, WorkerStatus.FAILED)
        ]

    @property
    def all_done(self) -> bool:
        return all(
            w.status in (WorkerStatus.COMPLETED, WorkerStatus.FAILED, WorkerStatus.STOPPED)
            for w in self.workers.values()
        )


class CoordinatorManager:
    """Orchestrates parallel Claude workers.

    Usage:
        coordinator = CoordinatorManager(claude_integration, event_bus)

        # Spawn workers
        session = coordinator.create_session(user_id=123)
        coordinator.add_worker(session, "Research auth", "Investigate auth module...", path)
        coordinator.add_worker(session, "Research tests", "Find test coverage...", path)

        # Run all workers in parallel
        results = await coordinator.run_all(session)
    """

    def __init__(
        self,
        claude: ClaudeIntegration,
        event_bus: Optional[EventBus] = None,
        max_concurrent_workers: int = 3,
    ) -> None:
        self.claude = claude
        self.event_bus = event_bus
        self.max_concurrent_workers = max_concurrent_workers
        self._sessions: Dict[str, CoordinatorSession] = {}
        self._worker_counter = 0

    def create_session(self, user_id: int) -> CoordinatorSession:
        """Create a new coordinator session."""
        import uuid

        session = CoordinatorSession(
            session_id=str(uuid.uuid4())[:8],
            user_id=user_id,
        )
        self._sessions[session.session_id] = session
        logger.info(
            "Coordinator session created",
            session_id=session.session_id,
            user_id=user_id,
        )
        return session

    def add_worker(
        self,
        session: CoordinatorSession,
        description: str,
        prompt: str,
        working_directory: Path,
    ) -> WorkerTask:
        """Add a worker task to a session."""
        self._worker_counter += 1
        worker_id = f"worker-{self._worker_counter}"

        task = WorkerTask(
            worker_id=worker_id,
            description=description,
            prompt=prompt,
            working_directory=working_directory,
        )
        session.workers[worker_id] = task

        logger.info(
            "Worker added to session",
            session_id=session.session_id,
            worker_id=worker_id,
            description=description,
        )
        return task

    async def run_all(
        self,
        session: CoordinatorSession,
        on_worker_complete: Optional[Callable[[WorkerTask], None]] = None,
    ) -> List[WorkerTask]:
        """Run all pending workers in parallel (up to max_concurrent).

        Returns list of completed WorkerTasks with results.
        """
        pending = [
            w for w in session.workers.values()
            if w.status == WorkerStatus.PENDING
        ]

        # Run in batches of max_concurrent_workers
        for i in range(0, len(pending), self.max_concurrent_workers):
            batch = pending[i : i + self.max_concurrent_workers]
            await asyncio.gather(
                *(
                    self._run_worker(session, worker, on_worker_complete)
                    for worker in batch
                )
            )

        return list(session.workers.values())

    async def _run_worker(
        self,
        session: CoordinatorSession,
        worker: WorkerTask,
        on_complete: Optional[Callable[[WorkerTask], None]] = None,
    ) -> None:
        """Run a single worker with isolated context."""
        worker.status = WorkerStatus.RUNNING
        worker.started_at = datetime.now(UTC)

        # Set isolated context for this worker
        ctx = {
            "user_id": session.user_id,
            "session_id": session.session_id,
            "worker_id": worker.worker_id,
        }
        token = agent_context.set(ctx)

        try:
            response = await self.claude.run_command(
                prompt=worker.prompt,
                working_directory=worker.working_directory,
                user_id=session.user_id,
                force_new=True,  # Each worker gets a fresh session
            )
            worker.result = response
            worker.status = WorkerStatus.COMPLETED
            logger.info(
                "Worker completed",
                worker_id=worker.worker_id,
                cost=response.cost,
                duration_ms=response.duration_ms,
            )
        except Exception as e:
            worker.error = str(e)
            worker.status = WorkerStatus.FAILED
            logger.error(
                "Worker failed",
                worker_id=worker.worker_id,
                error=str(e),
            )
        finally:
            worker.completed_at = datetime.now(UTC)
            agent_context.reset(token)

            if on_complete:
                on_complete(worker)

    async def stop_worker(
        self, session: CoordinatorSession, worker_id: str
    ) -> bool:
        """Stop a running worker."""
        worker = session.workers.get(worker_id)
        if not worker or worker.status != WorkerStatus.RUNNING:
            return False
        worker.status = WorkerStatus.STOPPED
        worker.completed_at = datetime.now(UTC)
        logger.info("Worker stopped", worker_id=worker_id)
        return True

    def get_session(self, session_id: str) -> Optional[CoordinatorSession]:
        """Get a coordinator session by ID."""
        return self._sessions.get(session_id)

    def summarize_results(self, session: CoordinatorSession) -> str:
        """Produce a summary of all worker results."""
        lines = []
        for worker in session.workers.values():
            status_emoji = {
                WorkerStatus.COMPLETED: "✅",
                WorkerStatus.FAILED: "❌",
                WorkerStatus.RUNNING: "⏳",
                WorkerStatus.STOPPED: "⏹",
                WorkerStatus.PENDING: "⏸",
            }.get(worker.status, "?")

            line = f"{status_emoji} {worker.description}"
            if worker.result:
                # First 200 chars of result
                preview = worker.result.content[:200]
                if len(worker.result.content) > 200:
                    preview += "..."
                line += f"\n   {preview}"
            elif worker.error:
                line += f"\n   Error: {worker.error}"
            lines.append(line)

        return "\n\n".join(lines)
