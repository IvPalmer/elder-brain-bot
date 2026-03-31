"""Dead-letter queue and retry logic for failed events.

Inspired by Claude Code's event retry with exponential backoff.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Dict, List

import structlog

from .bus import Event

logger = structlog.get_logger()


@dataclass
class FailedEvent:
    """A failed event with retry metadata."""

    event: Event
    last_error: str
    attempt_count: int = 0
    first_failure: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_attempt: datetime = field(default_factory=lambda: datetime.now(UTC))


class DeadLetterQueue:
    """Manages failed events with retry and permanent dead storage."""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_seconds: float = 60.0,
    ) -> None:
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self._pending: Dict[str, FailedEvent] = {}
        self._dead: List[FailedEvent] = []

    @property
    def pending(self) -> List[FailedEvent]:
        return list(self._pending.values())

    @property
    def dead(self) -> List[FailedEvent]:
        return list(self._dead)

    def __len__(self) -> int:
        return len(self._pending) + len(self._dead)

    def add(self, event: Event, error: str) -> None:
        """Add a failed event. Increments retry count if already pending."""
        if event.id in self._pending:
            fe = self._pending[event.id]
            fe.attempt_count += 1
            fe.last_error = error
            fe.last_attempt = datetime.now(UTC)

            if fe.attempt_count >= self.max_retries:
                self._dead.append(fe)
                del self._pending[event.id]
                logger.warning(
                    "Event moved to dead-letter queue",
                    event_id=event.id,
                    attempts=fe.attempt_count,
                    error=error,
                )
            return

        fe = FailedEvent(
            event=event,
            last_error=error,
            attempt_count=1,
        )

        if fe.attempt_count >= self.max_retries:
            self._dead.append(fe)
        else:
            self._pending[event.id] = fe

        logger.info(
            "Event added to retry queue",
            event_id=event.id,
            error=error,
        )

    def get_retryable(self) -> List[Event]:
        """Get events that are ready to retry (delay has elapsed)."""
        now = datetime.now(UTC)
        ready = []

        for fe in self._pending.values():
            backoff = self.retry_delay_seconds * (2 ** (fe.attempt_count - 1))
            next_retry = fe.last_attempt + timedelta(seconds=backoff)

            if now >= next_retry:
                ready.append(fe.event)

        return ready
