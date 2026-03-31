"""Pre/post hook system for events and tool calls.

Inspired by Claude Code's 26+ hook event types with
matcher-based filtering.
"""

from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Tuple

import structlog

logger = structlog.get_logger()

HookCallback = Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]]


class HookTiming(str, Enum):
    PRE = "pre"
    POST = "post"


class HookRegistry:
    """Registry for pre/post hooks on named events."""

    def __init__(self) -> None:
        self._hooks: Dict[Tuple[str, HookTiming], List[HookCallback]] = {}

    def register(
        self,
        event_name: str,
        timing: HookTiming,
        callback: HookCallback,
    ) -> None:
        """Register a hook callback."""
        key = (event_name, timing)
        if key not in self._hooks:
            self._hooks[key] = []
        self._hooks[key].append(callback)
        logger.debug(
            "Hook registered",
            event_name=event_name,
            timing=timing.value,
        )

    async def fire(
        self,
        event_name: str,
        timing: HookTiming,
        data: Dict[str, Any],
    ) -> None:
        """Fire all hooks for an event+timing. Errors are logged, not raised."""
        key = (event_name, timing)
        hooks = self._hooks.get(key, [])

        for hook in hooks:
            try:
                await hook(event_name, data)
            except Exception:
                logger.exception(
                    "Hook failed",
                    event_name=event_name,
                    timing=timing.value,
                    hook=hook.__qualname__,
                )
