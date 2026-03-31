"""Notification delivery tracking.

Inspired by Claude Code's delivery status tracking (sent, read, failed).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger()


class DeliveryStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"


@dataclass
class DeliveryRecord:
    """Record of a notification delivery attempt."""

    event_id: str
    chat_id: int
    status: DeliveryStatus
    message_id: Optional[int] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class DeliveryTracker:
    """Tracks notification delivery status."""

    def __init__(self, max_records: int = 10000) -> None:
        self.max_records = max_records
        self._records: Dict[Tuple[str, int], DeliveryRecord] = {}
        self._order: List[Tuple[str, int]] = []

    def record_sent(self, event_id: str, chat_id: int, message_id: int) -> None:
        """Record a successful delivery."""
        self._add(
            DeliveryRecord(
                event_id=event_id,
                chat_id=chat_id,
                status=DeliveryStatus.SENT,
                message_id=message_id,
            )
        )

    def record_failed(self, event_id: str, chat_id: int, error: str) -> None:
        """Record a failed delivery."""
        self._add(
            DeliveryRecord(
                event_id=event_id,
                chat_id=chat_id,
                status=DeliveryStatus.FAILED,
                error=error,
            )
        )

    def get(self, event_id: str, chat_id: int) -> Optional[DeliveryRecord]:
        """Get delivery record."""
        return self._records.get((event_id, chat_id))

    def stats(self) -> Dict[str, Any]:
        """Get delivery statistics."""
        total = len(self._records)
        sent = sum(
            1 for r in self._records.values() if r.status == DeliveryStatus.SENT
        )
        failed = total - sent
        return {
            "total": total,
            "sent": sent,
            "failed": failed,
            "success_rate": sent / total if total > 0 else 1.0,
        }

    def _add(self, record: DeliveryRecord) -> None:
        key = (record.event_id, record.chat_id)
        self._records[key] = record
        self._order.append(key)

        while len(self._records) > self.max_records:
            old_key = self._order.pop(0)
            self._records.pop(old_key, None)
