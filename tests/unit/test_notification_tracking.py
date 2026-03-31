"""Tests for notification delivery tracking."""

from src.notifications.tracking import DeliveryTracker, DeliveryStatus


def test_record_sent():
    tracker = DeliveryTracker()
    tracker.record_sent(event_id="evt-1", chat_id=123, message_id=456)
    record = tracker.get(event_id="evt-1", chat_id=123)
    assert record is not None
    assert record.status == DeliveryStatus.SENT
    assert record.message_id == 456


def test_record_failed():
    tracker = DeliveryTracker()
    tracker.record_failed(event_id="evt-1", chat_id=123, error="Telegram 403: bot blocked")
    record = tracker.get(event_id="evt-1", chat_id=123)
    assert record is not None
    assert record.status == DeliveryStatus.FAILED
    assert "403" in record.error


def test_stats():
    tracker = DeliveryTracker()
    tracker.record_sent("e1", 100, 1)
    tracker.record_sent("e2", 100, 2)
    tracker.record_failed("e3", 100, error="timeout")

    stats = tracker.stats()
    assert stats["total"] == 3
    assert stats["sent"] == 2
    assert stats["failed"] == 1
