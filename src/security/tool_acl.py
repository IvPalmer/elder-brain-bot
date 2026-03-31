"""Per-tool access control lists.

Inspired by Claude Code's per-tool permission model where each tool
has checkPermissions() and tools can be denied before the model sees them.

This module provides user-level ACLs for Claude tools, allowing different
users to have different tool access levels.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import structlog

logger = structlog.get_logger()


@dataclass
class ToolACL:
    """Access control for a specific tool."""

    tool_name: str
    allowed_users: Optional[Set[int]] = None  # None = all users
    denied_users: Set[int] = field(default_factory=set)
    max_uses_per_session: Optional[int] = None
    requires_confirmation: bool = False


class ToolACLManager:
    """Manages per-tool per-user access control.

    Rules are evaluated in order:
    1. If tool has denied_users and user is in it → deny
    2. If tool has allowed_users and user is NOT in it → deny
    3. If tool has max_uses_per_session and count exceeded → deny
    4. Otherwise → allow
    """

    def __init__(self) -> None:
        self._acls: Dict[str, ToolACL] = {}
        self._session_counts: Dict[str, Dict[str, int]] = {}  # session_id → {tool: count}

    def add_rule(self, acl: ToolACL) -> None:
        """Add or update a tool ACL rule."""
        self._acls[acl.tool_name] = acl

    def check(
        self,
        tool_name: str,
        user_id: int,
        session_id: Optional[str] = None,
    ) -> tuple[bool, str]:
        """Check if a user can use a tool.

        Returns (allowed, reason) tuple.
        """
        acl = self._acls.get(tool_name)
        if not acl:
            return True, "ok"

        # Check denied users
        if user_id in acl.denied_users:
            return False, f"User {user_id} is denied access to {tool_name}"

        # Check allowed users
        if acl.allowed_users is not None and user_id not in acl.allowed_users:
            return False, f"User {user_id} is not in allowed list for {tool_name}"

        # Check session usage count
        if acl.max_uses_per_session is not None and session_id:
            count = self._get_count(session_id, tool_name)
            if count >= acl.max_uses_per_session:
                return False, (
                    f"Session limit reached for {tool_name}: "
                    f"{count}/{acl.max_uses_per_session}"
                )

        return True, "ok"

    def record_use(self, session_id: str, tool_name: str) -> None:
        """Record a tool use for session-based limiting."""
        if session_id not in self._session_counts:
            self._session_counts[session_id] = {}
        counts = self._session_counts[session_id]
        counts[tool_name] = counts.get(tool_name, 0) + 1

    def _get_count(self, session_id: str, tool_name: str) -> int:
        return self._session_counts.get(session_id, {}).get(tool_name, 0)

    def filter_tools_for_user(
        self, tools: List[str], user_id: int
    ) -> List[str]:
        """Filter a tool list to only those the user can access."""
        return [t for t in tools if self.check(t, user_id)[0]]

    def cleanup_session(self, session_id: str) -> None:
        """Clean up session counts when session ends."""
        self._session_counts.pop(session_id, None)
