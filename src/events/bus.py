"""Central async event bus.

Decouples event sources (Telegram, webhooks, cron) from handlers
(agent execution, notifications). All inputs become typed events
routed to registered handlers.

Enhanced with dead-letter queue (DLQ) for failed events and
pre/post hook support, inspired by Claude Code patterns.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional, Type

import structlog

logger = structlog.get_logger()


@dataclass
class Event:
    """Base event class. All events carry an ID, timestamp, and source."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = "unknown"

    @property
    def event_type(self) -> str:
        return type(self).__name__


EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Async event bus with typed subscriptions.

    Handlers subscribe to specific event types and are called
    concurrently when a matching event is published.

    Enhanced with optional DLQ and hook support.
    """

    def __init__(self) -> None:
        self._handlers: Dict[Type[Event], List[EventHandler]] = {}
        self._global_handlers: List[EventHandler] = []
        self._running = False
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._processor_task: Optional[asyncio.Task[None]] = None
        self._retry_task: Optional[asyncio.Task[None]] = None

        # Optional DLQ — set via set_dlq()
        self._dlq: Optional[Any] = None
        # Optional hooks — set via set_hooks()
        self._hooks: Optional[Any] = None

    def set_dlq(self, dlq: Any) -> None:
        """Attach a DeadLetterQueue for failed event retry."""
        self._dlq = dlq

    def set_hooks(self, hooks: Any) -> None:
        """Attach a HookRegistry for pre/post event hooks."""
        self._hooks = hooks

    def subscribe(
        self,
        event_type: Type[Event],
        handler: EventHandler,
    ) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(
            "Handler subscribed",
            event_type=event_type.__name__,
            handler=handler.__qualname__,
        )

    def subscribe_all(self, handler: EventHandler) -> None:
        """Register a handler that receives all events."""
        self._global_handlers.append(handler)

    async def publish(self, event: Event) -> None:
        """Publish an event to be processed by matching handlers."""
        logger.info(
            "Event published",
            event_type=event.event_type,
            event_id=event.id,
            source=event.source,
        )
        await self._queue.put(event)

    async def start(self) -> None:
        """Start processing events from the queue."""
        if self._running:
            return
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("Event bus started")

    async def stop(self) -> None:
        """Stop processing events and drain the queue."""
        if not self._running:
            return
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("Event bus stopped")

    async def _process_events(self) -> None:
        """Main event processing loop."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            await self._dispatch(event)

    async def _dispatch(self, event: Event) -> None:
        """Dispatch event to all matching handlers concurrently."""
        # Fire pre-dispatch hooks
        if self._hooks:
            try:
                from .hooks import HookTiming

                await self._hooks.fire(
                    event.event_type, HookTiming.PRE, {"event": event}
                )
            except Exception:
                logger.debug("Pre-dispatch hook error", event_type=event.event_type)

        handlers: List[EventHandler] = []

        # Collect type-specific handlers (including parent classes)
        for event_type, type_handlers in self._handlers.items():
            if isinstance(event, event_type):
                handlers.extend(type_handlers)

        # Add global handlers
        handlers.extend(self._global_handlers)

        if not handlers:
            logger.debug("No handlers for event", event_type=event.event_type)
            return

        # Run all handlers concurrently
        results = await asyncio.gather(
            *(self._safe_call(handler, event) for handler in handlers),
            return_exceptions=True,
        )

        has_failures = False
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                has_failures = True
                logger.error(
                    "Event handler failed",
                    event_type=event.event_type,
                    event_id=event.id,
                    handler=handlers[i].__qualname__,
                    error=str(result),
                )

        # Add failed events to DLQ for retry
        if has_failures and self._dlq:
            self._dlq.add(event, error="Handler failure during dispatch")

        # Fire post-dispatch hooks
        if self._hooks:
            try:
                from .hooks import HookTiming

                await self._hooks.fire(
                    event.event_type,
                    HookTiming.POST,
                    {"event": event, "had_failures": has_failures},
                )
            except Exception:
                logger.debug("Post-dispatch hook error", event_type=event.event_type)

    async def _safe_call(self, handler: EventHandler, event: Event) -> None:
        """Call handler with error isolation."""
        try:
            await handler(event)
        except Exception:
            logger.exception(
                "Unhandled error in event handler",
                handler=handler.__qualname__,
                event_type=event.event_type,
            )
            raise
