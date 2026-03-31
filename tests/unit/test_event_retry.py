"""Tests for dead-letter queue and retry logic."""

from datetime import UTC, datetime
from src.events.retry import DeadLetterQueue, FailedEvent
from src.events.bus import Event


def test_add_to_dlq():
    dlq = DeadLetterQueue(max_retries=3)
    event = Event(source="test")
    dlq.add(event, error="connection timeout")
    assert len(dlq) == 1
    assert dlq.pending[0].attempt_count == 1


def test_retry_increments_count():
    dlq = DeadLetterQueue(max_retries=3)
    event = Event(source="test")
    dlq.add(event, error="timeout")
    dlq.add(event, error="timeout again")
    assert len(dlq.pending) == 1
    assert dlq.pending[0].attempt_count == 2


def test_max_retries_moves_to_dead():
    dlq = DeadLetterQueue(max_retries=2)
    event = Event(source="test")
    dlq.add(event, error="e1")
    dlq.add(event, error="e2")
    assert len(dlq.pending) == 0
    assert len(dlq.dead) == 1


def test_get_retryable_events():
    dlq = DeadLetterQueue(max_retries=3, retry_delay_seconds=0)
    event = Event(source="test")
    dlq.add(event, error="timeout")
    retryable = dlq.get_retryable()
    assert len(retryable) == 1


def test_retry_delay():
    dlq = DeadLetterQueue(max_retries=3, retry_delay_seconds=3600)
    event = Event(source="test")
    dlq.add(event, error="timeout")
    retryable = dlq.get_retryable()
    assert len(retryable) == 0
