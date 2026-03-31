"""Context compaction to manage conversation length and token costs.

Inspired by Claude Code's compact/ service which auto-compacts
conversations when approaching context limits.
"""

from dataclasses import dataclass
from typing import List

import structlog

logger = structlog.get_logger()


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    role: str  # "user", "assistant", "system"
    content: str


class CompactionService:
    """Compacts old conversation turns into summaries.

    When conversation exceeds max_turns_before_compact, older turns
    are summarized into a single system message, keeping
    recent_turns_to_keep turns verbatim.
    """

    def __init__(
        self,
        max_turns_before_compact: int = 20,
        recent_turns_to_keep: int = 6,
        max_summary_chars: int = 2000,
    ) -> None:
        self.max_turns_before_compact = max_turns_before_compact
        self.recent_turns_to_keep = recent_turns_to_keep
        self.max_summary_chars = max_summary_chars

    def maybe_compact(
        self, turns: List[ConversationTurn]
    ) -> List[ConversationTurn]:
        """Compact conversation if it exceeds the threshold."""
        if len(turns) <= self.max_turns_before_compact:
            return turns

        split_point = len(turns) - self.recent_turns_to_keep
        old_turns = turns[:split_point]
        recent_turns = turns[split_point:]

        summary = self._summarize_turns(old_turns)
        summary_turn = ConversationTurn(
            role="system",
            content=summary,
        )

        logger.info(
            "Conversation compacted",
            old_turns=len(old_turns),
            kept_turns=len(recent_turns),
            summary_chars=len(summary),
        )

        return [summary_turn] + recent_turns

    def _summarize_turns(self, turns: List[ConversationTurn]) -> str:
        """Create an extractive summary of conversation turns."""
        key_points: List[str] = []

        for turn in turns:
            content = turn.content.strip()
            if not content:
                continue

            first_line = content.split("\n")[0][:200]

            if turn.role == "user":
                key_points.append(f"User asked: {first_line}")
            elif turn.role == "assistant":
                if len(content) > 50:
                    key_points.append(f"Assistant: {first_line}")

        summary = "Conversation summary (older messages compacted):\n"
        summary += "\n".join(f"- {p}" for p in key_points)

        if len(summary) > self.max_summary_chars:
            summary = summary[: self.max_summary_chars] + "\n... (truncated)"

        return summary
