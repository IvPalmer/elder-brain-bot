"""Event handlers that bridge the event bus to Claude and Telegram.

AgentHandler: translates events into ClaudeIntegration.run_command() calls.
NotificationHandler: subscribes to AgentResponseEvent and delivers to Telegram.
FreqtradeHandler: formats Freqtrade trade notifications for Telegram delivery.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from ..claude.facade import ClaudeIntegration
from .bus import Event, EventBus
from .types import AgentResponseEvent, ScheduledEvent, WebhookEvent

logger = structlog.get_logger()


class AgentHandler:
    """Translates incoming events into Claude agent executions.

    Webhook and scheduled events are converted into prompts and sent
    to ClaudeIntegration.run_command(). The response is published
    back as an AgentResponseEvent for delivery.
    """

    def __init__(
        self,
        event_bus: EventBus,
        claude_integration: ClaudeIntegration,
        default_working_directory: Path,
        default_user_id: int = 0,
    ) -> None:
        self.event_bus = event_bus
        self.claude = claude_integration
        self.default_working_directory = default_working_directory
        self.default_user_id = default_user_id

    def register(self) -> None:
        """Subscribe to events that need agent processing."""
        self.event_bus.subscribe(WebhookEvent, self.handle_webhook)
        self.event_bus.subscribe(ScheduledEvent, self.handle_scheduled)

    async def handle_webhook(self, event: Event) -> None:
        """Process a webhook event through Claude."""
        if not isinstance(event, WebhookEvent):
            return

        # Skip Freqtrade events — handled by FreqtradeHandler directly
        if event.provider == "freqtrade":
            return

        logger.info(
            "Processing webhook event through agent",
            provider=event.provider,
            event_type=event.event_type_name,
            delivery_id=event.delivery_id,
        )

        prompt = self._build_webhook_prompt(event)

        try:
            response = await self.claude.run_command(
                prompt=prompt,
                working_directory=self.default_working_directory,
                user_id=self.default_user_id,
            )

            if response.content:
                # We don't know which chat to send to from a webhook alone.
                # The notification service needs configured target chats.
                # Publish with chat_id=0 — the NotificationService
                # will broadcast to configured notification_chat_ids.
                await self.event_bus.publish(
                    AgentResponseEvent(
                        chat_id=0,
                        text=response.content,
                        originating_event_id=event.id,
                    )
                )
        except Exception:
            logger.exception(
                "Agent execution failed for webhook event",
                provider=event.provider,
                event_id=event.id,
            )

    async def handle_scheduled(self, event: Event) -> None:
        """Process a scheduled event through Claude."""
        if not isinstance(event, ScheduledEvent):
            return

        logger.info(
            "Processing scheduled event through agent",
            job_id=event.job_id,
            job_name=event.job_name,
        )

        prompt = event.prompt
        if event.skill_name:
            prompt = (
                f"/{event.skill_name}\n\n{prompt}" if prompt else f"/{event.skill_name}"
            )

        working_dir = event.working_directory or self.default_working_directory

        try:
            response = await self.claude.run_command(
                prompt=prompt,
                working_directory=working_dir,
                user_id=self.default_user_id,
            )

            if response.content:
                for chat_id in event.target_chat_ids:
                    await self.event_bus.publish(
                        AgentResponseEvent(
                            chat_id=chat_id,
                            text=response.content,
                            originating_event_id=event.id,
                        )
                    )

                # Also broadcast to default chats if no targets specified
                if not event.target_chat_ids:
                    await self.event_bus.publish(
                        AgentResponseEvent(
                            chat_id=0,
                            text=response.content,
                            originating_event_id=event.id,
                        )
                    )
        except Exception:
            logger.exception(
                "Agent execution failed for scheduled event",
                job_id=event.job_id,
                event_id=event.id,
            )

    def _build_webhook_prompt(self, event: WebhookEvent) -> str:
        """Build a Claude prompt from a webhook event."""
        payload_summary = self._summarize_payload(event.payload)

        return (
            f"A {event.provider} webhook event occurred.\n"
            f"Event type: {event.event_type_name}\n"
            f"Payload summary:\n{payload_summary}\n\n"
            f"Analyze this event and provide a concise summary. "
            f"Highlight anything that needs my attention."
        )

    def _summarize_payload(self, payload: Dict[str, Any], max_depth: int = 2) -> str:
        """Create a readable summary of a webhook payload."""
        lines: List[str] = []
        self._flatten_dict(payload, lines, max_depth=max_depth)
        # Cap at 2000 chars to keep prompt reasonable
        summary = "\n".join(lines)
        if len(summary) > 2000:
            summary = summary[:2000] + "\n... (truncated)"
        return summary

    def _flatten_dict(
        self,
        data: Any,
        lines: list,
        prefix: str = "",
        depth: int = 0,
        max_depth: int = 2,
    ) -> None:
        """Flatten a nested dict into key: value lines."""
        if depth >= max_depth:
            lines.append(f"{prefix}: ...")
            return

        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, (dict, list)):
                    self._flatten_dict(value, lines, full_key, depth + 1, max_depth)
                else:
                    val_str = str(value)
                    if len(val_str) > 200:
                        val_str = val_str[:200] + "..."
                    lines.append(f"{full_key}: {val_str}")
        elif isinstance(data, list):
            lines.append(f"{prefix}: [{len(data)} items]")
            for i, item in enumerate(data[:3]):  # Show first 3 items
                self._flatten_dict(item, lines, f"{prefix}[{i}]", depth + 1, max_depth)
        else:
            lines.append(f"{prefix}: {data}")


class FreqtradeHandler:
    """Formats Freqtrade trade webhook notifications for Telegram delivery.

    Intercepts WebhookEvents from the 'freqtrade' provider and publishes
    formatted AgentResponseEvents directly — no Claude processing needed.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus

    def register(self) -> None:
        """Subscribe to webhook events."""
        self.event_bus.subscribe(WebhookEvent, self.handle_freqtrade)

    async def handle_freqtrade(self, event: Event) -> None:
        """Format and publish a Freqtrade webhook event."""
        if not isinstance(event, WebhookEvent):
            return
        if event.provider != "freqtrade":
            return

        payload = event.payload
        msg_type = payload.get("type", event.event_type_name)

        logger.info(
            "Freqtrade webhook received",
            msg_type=msg_type,
            delivery_id=event.delivery_id,
        )

        text = self._format_message(msg_type, payload)
        if not text:
            logger.warning("Unknown Freqtrade message type", msg_type=msg_type)
            return

        await self.event_bus.publish(
            AgentResponseEvent(
                chat_id=0,  # broadcast to default notification chats
                text=text,
                parse_mode="HTML",
                originating_event_id=event.id,
            )
        )

    # ------------------------------------------------------------------
    # Formatters
    # ------------------------------------------------------------------

    # Only send closed trade results and status messages — suppress entry notifications to reduce noise
    IMPORTANT_TYPES = {"exit_fill", "exit", "status"}

    def _format_message(self, msg_type: str, p: Dict[str, Any]) -> Optional[str]:
        """Route to the appropriate formatter. Returns None for noisy events."""
        if msg_type not in self.IMPORTANT_TYPES:
            logger.debug("Skipping non-important Freqtrade event", msg_type=msg_type)
            return None

        if msg_type == "status":
            return p.get("status", "")
        if msg_type == "entry_fill":
            return self._format_entry_fill(p)
        if msg_type in ("exit_fill", "exit"):
            return self._format_exit_fill(p)
        return None

    def _format_entry_fill(self, p: Dict[str, Any]) -> str:
        pair = p.get("pair", "?")
        stake = p.get("stake_amount", "?")
        rate = p.get("open_rate", p.get("limit", "?"))
        currency = p.get("stake_currency", "USDT")
        direction = p.get("direction", "Long")

        return (
            f"\U0001f7e2 <b>{pair}</b> \u2014 {direction}\n"
            f"\u2514 {self._fmt_num(stake)} {currency} @ {self._fmt_num(rate)}"
        )

    def _format_exit_fill(self, p: Dict[str, Any]) -> str:
        pair = p.get("pair", "?")
        profit_pct = self._to_float(p.get("profit_ratio", 0))
        profit_amount = self._to_float(p.get("profit_amount"))
        currency = p.get("stake_currency", "USDT")
        exit_reason = p.get("exit_reason", p.get("sell_reason", "?"))
        duration = p.get("duration", "?")
        open_rate = p.get("open_rate", "?")
        close_rate = p.get("close_rate", p.get("limit", "?"))

        pct_display = f"{profit_pct * 100:+.2f}%" if profit_pct is not None else "?"
        is_win = profit_pct is not None and profit_pct >= 0
        emoji = "\u2705" if is_win else "\u274c"

        lines = [
            f"{emoji} <b>{pair}</b> \u2014 <b>{pct_display}</b>",
            f"\u2514 {self._fmt_num(open_rate)} \u2192 {self._fmt_num(close_rate)}",
        ]
        if profit_amount is not None:
            lines.append(f"\u2514 P/L: <b>{profit_amount:+.2f} {currency}</b>")
        lines.append(f"\u2514 {exit_reason} \u2022 {self._fmt_duration(duration)}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        """Safely convert to float, returning None on failure."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _fmt_num(value: Any) -> str:
        """Format a number nicely, or return as-is if not numeric."""
        try:
            f = float(value)
            return f"{f:.8f}".rstrip("0").rstrip(".")
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def _fmt_duration(value: Any) -> str:
        """Format duration (minutes or string) into a readable form."""
        if isinstance(value, (int, float)):
            mins = int(value)
            if mins >= 60:
                hours = mins // 60
                remaining = mins % 60
                return f"{hours}h {remaining}m"
            return f"{mins}m"
        return str(value)
