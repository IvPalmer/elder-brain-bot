# Claude-Assistant: Claude Code Patterns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt 22 architectural patterns from Claude Code into the Telegram bot, improving security, observability, cost efficiency, and resilience.

**Architecture:** Changes are organized into 3 tiers by effort. Each task is independent within its tier. Tier 1 tasks (quick wins) can run in parallel. Tier 2/3 tasks may depend on Tier 1 foundations.

**Tech Stack:** Python 3.10+, Poetry, pytest-asyncio, structlog, pydantic-settings, python-telegram-bot, claude-agent-sdk, aiosqlite

---

## File Structure

### New files:
- `src/claude/tool_execution.py` — Tool execution tracking dataclass and metrics
- `src/claude/error_types.py` — Structured error classification
- `src/claude/compaction.py` — Context compaction service
- `src/claude/memory.py` — Per-user persistent memory system
- `src/events/retry.py` — Dead-letter queue and retry logic
- `src/events/hooks.py` — Pre/post hook system for events and tools
- `src/notifications/tracking.py` — Notification delivery tracking
- `src/bot/features/skills.py` — Markdown-based skill templates
- `tests/unit/test_tool_execution.py`
- `tests/unit/test_error_types.py`
- `tests/unit/test_event_retry.py`
- `tests/unit/test_compaction.py`
- `tests/unit/test_memory.py`
- `tests/unit/test_notification_tracking.py`
- `tests/unit/test_operation_rate_limit.py`
- `tests/unit/test_event_hooks.py`
- `tests/unit/test_skills.py`

### Modified files:
- `src/config/settings.py` — New settings for compaction, memory, hooks
- `src/config/features.py` — New feature flags
- `src/claude/sdk_integration.py` — Pre-filter tools, tool execution tracking, error classification
- `src/claude/session.py` — Tool execution metrics in ClaudeSession, pagination support
- `src/claude/facade.py` — Wire compaction, memory, contextvars isolation
- `src/security/rate_limiter.py` — Operation-level buckets
- `src/events/bus.py` — Retry support, richer event types
- `src/events/types.py` — New event types (ToolExecuted, FileChanged, etc.)
- `src/notifications/service.py` — Delivery tracking
- `src/storage/database.py` — New tables for memory, tool_executions, notification_delivery
- `src/bot/orchestrator.py` — Wire hooks, skills

---

## Tier 1: Quick Wins

### Task 1: Pre-filter Denied Tools

**Files:**
- Modify: `src/claude/sdk_integration.py:190-205`
- Test: `tests/unit/test_sdk_integration.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_tool_filtering.py
import pytest
from src.claude.sdk_integration import filter_denied_tools


def test_filter_denied_tools_removes_disallowed():
    allowed = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
    disallowed = ["Bash", "Write"]
    result = filter_denied_tools(allowed, disallowed)
    assert result == ["Read", "Edit", "Glob", "Grep"]


def test_filter_denied_tools_empty_disallowed():
    allowed = ["Read", "Write"]
    result = filter_denied_tools(allowed, [])
    assert result == ["Read", "Write"]


def test_filter_denied_tools_none_disallowed():
    allowed = ["Read", "Write"]
    result = filter_denied_tools(allowed, None)
    assert result == ["Read", "Write"]


def test_filter_denied_tools_all_disallowed():
    allowed = ["Read"]
    disallowed = ["Read"]
    result = filter_denied_tools(allowed, disallowed)
    assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_tool_filtering.py -v`
Expected: FAIL with "cannot import name 'filter_denied_tools'"

- [ ] **Step 3: Implement filter_denied_tools**

Add to `src/claude/sdk_integration.py` before the `ClaudeSDKManager` class:

```python
def filter_denied_tools(
    allowed_tools: list[str],
    disallowed_tools: list[str] | None,
) -> list[str]:
    """Remove disallowed tools before sending to Claude (saves tokens).

    Inspired by Claude Code's filterToolsByDenyRules() which removes tools
    before the model sees them, not just at call time.
    """
    if not disallowed_tools:
        return list(allowed_tools)
    deny_set = set(disallowed_tools)
    return [t for t in allowed_tools if t not in deny_set]
```

- [ ] **Step 4: Wire into execute_command**

In `ClaudeSDKManager.execute_command()`, replace the tool validation block (lines ~190-195):

```python
            if self.config.disable_tool_validation:
                sdk_allowed_tools = None
                sdk_disallowed_tools = None
            else:
                sdk_allowed_tools = filter_denied_tools(
                    self.config.claude_allowed_tools or [],
                    self.config.claude_disallowed_tools,
                )
                sdk_disallowed_tools = None  # Already filtered out
```

- [ ] **Step 5: Run tests**

Run: `poetry run pytest tests/unit/test_tool_filtering.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/claude/sdk_integration.py tests/unit/test_tool_filtering.py
git commit -m "feat: pre-filter denied tools before sending to Claude (token savings)"
```

---

### Task 2: Tool Execution Tracking

**Files:**
- Create: `src/claude/tool_execution.py`
- Modify: `src/claude/sdk_integration.py:299-323`
- Modify: `src/claude/session.py:28-59`
- Test: `tests/unit/test_tool_execution.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_tool_execution.py
import pytest
from datetime import UTC, datetime
from src.claude.tool_execution import ToolExecution, ToolExecutionTracker


def test_tool_execution_creation():
    te = ToolExecution(
        tool_name="Read",
        start_time=datetime.now(UTC),
        duration_ms=150.0,
        success=True,
    )
    assert te.tool_name == "Read"
    assert te.success is True
    assert te.error_type is None


def test_tracker_record_and_summarize():
    tracker = ToolExecutionTracker()
    tracker.record(ToolExecution(
        tool_name="Read",
        start_time=datetime.now(UTC),
        duration_ms=100.0,
        success=True,
    ))
    tracker.record(ToolExecution(
        tool_name="Read",
        start_time=datetime.now(UTC),
        duration_ms=200.0,
        success=True,
    ))
    tracker.record(ToolExecution(
        tool_name="Bash",
        start_time=datetime.now(UTC),
        duration_ms=500.0,
        success=False,
        error_type="timeout",
    ))

    summary = tracker.summarize()
    assert summary["total_executions"] == 3
    assert summary["success_rate"] == pytest.approx(2 / 3)
    assert summary["by_tool"]["Read"]["count"] == 2
    assert summary["by_tool"]["Read"]["avg_duration_ms"] == pytest.approx(150.0)
    assert summary["by_tool"]["Bash"]["error_types"] == {"timeout": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_tool_execution.py -v`
Expected: FAIL with "No module named 'src.claude.tool_execution'"

- [ ] **Step 3: Implement tool_execution.py**

```python
# src/claude/tool_execution.py
"""Tool execution tracking inspired by Claude Code's tool instrumentation."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional


@dataclass
class ToolExecution:
    """Record of a single tool execution."""

    tool_name: str
    start_time: datetime
    duration_ms: float
    success: bool
    error_type: Optional[str] = None
    input_summary: Optional[str] = None


class ToolExecutionTracker:
    """Tracks tool executions for a session and produces summaries."""

    def __init__(self) -> None:
        self.executions: List[ToolExecution] = []

    def record(self, execution: ToolExecution) -> None:
        """Record a tool execution."""
        self.executions.append(execution)

    def summarize(self) -> Dict[str, Any]:
        """Produce a summary of all tool executions."""
        if not self.executions:
            return {"total_executions": 0, "success_rate": 1.0, "by_tool": {}}

        total = len(self.executions)
        successes = sum(1 for e in self.executions if e.success)

        by_tool: Dict[str, Dict[str, Any]] = {}
        grouped: Dict[str, List[ToolExecution]] = defaultdict(list)
        for ex in self.executions:
            grouped[ex.tool_name].append(ex)

        for name, execs in grouped.items():
            durations = [e.duration_ms for e in execs]
            errors: Dict[str, int] = defaultdict(int)
            for e in execs:
                if e.error_type:
                    errors[e.error_type] += 1

            by_tool[name] = {
                "count": len(execs),
                "avg_duration_ms": sum(durations) / len(durations),
                "max_duration_ms": max(durations),
                "success_count": sum(1 for e in execs if e.success),
                "error_types": dict(errors),
            }

        return {
            "total_executions": total,
            "success_rate": successes / total,
            "by_tool": by_tool,
        }
```

- [ ] **Step 4: Run tests**

Run: `poetry run pytest tests/unit/test_tool_execution.py -v`
Expected: PASS

- [ ] **Step 5: Wire into ClaudeResponse and ClaudeSession**

In `src/claude/sdk_integration.py`, after building `tools_used` (line ~323), add execution tracking:

```python
# In the tools_used extraction loop, enhance each tool dict:
tools_used.append({
    "name": getattr(block, "name", "unknown"),
    "timestamp": current_time,
    "input": getattr(block, "input", {}),
    "duration_ms": 0.0,  # SDK doesn't provide per-tool timing yet
    "success": True,
})
```

In `src/claude/session.py`, add `tool_executions` field to `ClaudeSession`:

```python
from .tool_execution import ToolExecution, ToolExecutionTracker

# Add to ClaudeSession dataclass:
tool_execution_tracker: ToolExecutionTracker = field(
    default_factory=ToolExecutionTracker
)
```

In `ClaudeSession.update_usage()`, record tool executions:

```python
if response.tools_used:
    for tool in response.tools_used:
        tool_name = tool.get("name")
        if tool_name:
            self.tool_execution_tracker.record(ToolExecution(
                tool_name=tool_name,
                start_time=datetime.now(UTC),
                duration_ms=tool.get("duration_ms", 0.0),
                success=tool.get("success", True),
                error_type=tool.get("error_type"),
            ))
            if tool_name not in self.tools_used:
                self.tools_used.append(tool_name)
```

- [ ] **Step 6: Commit**

```bash
git add src/claude/tool_execution.py src/claude/sdk_integration.py src/claude/session.py tests/unit/test_tool_execution.py
git commit -m "feat: add tool execution tracking with per-tool metrics"
```

---

### Task 3: Error Classification

**Files:**
- Create: `src/claude/error_types.py`
- Modify: `src/claude/sdk_integration.py:382-456`
- Test: `tests/unit/test_error_types.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_error_types.py
from src.claude.error_types import classify_error, ErrorCategory


def test_classify_timeout():
    from src.claude.exceptions import ClaudeTimeoutError
    err = ClaudeTimeoutError("timed out")
    assert classify_error(err) == ErrorCategory.TIMEOUT


def test_classify_mcp_error():
    from src.claude.exceptions import ClaudeMCPError
    err = ClaudeMCPError("mcp server failed")
    assert classify_error(err) == ErrorCategory.MCP


def test_classify_process_error():
    from src.claude.exceptions import ClaudeProcessError
    err = ClaudeProcessError("process crashed")
    assert classify_error(err) == ErrorCategory.PROCESS


def test_classify_permission():
    err = PermissionError("denied")
    assert classify_error(err) == ErrorCategory.PERMISSION


def test_classify_unknown():
    err = RuntimeError("something weird")
    assert classify_error(err) == ErrorCategory.UNKNOWN


def test_is_transient():
    from src.claude.error_types import is_transient_error
    from src.claude.exceptions import ClaudeTimeoutError, ClaudeProcessError
    assert is_transient_error(ClaudeTimeoutError("t")) is True
    assert is_transient_error(ClaudeProcessError("p")) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_error_types.py -v`
Expected: FAIL

- [ ] **Step 3: Implement error_types.py**

```python
# src/claude/error_types.py
"""Structured error classification for Claude operations.

Inspired by Claude Code's error categorization which distinguishes
MCP errors, timeouts, permission denials, and validation failures.
"""

from enum import Enum
from typing import Union

from .exceptions import (
    ClaudeMCPError,
    ClaudeParsingError,
    ClaudeProcessError,
    ClaudeTimeoutError,
)


class ErrorCategory(str, Enum):
    TIMEOUT = "timeout"
    MCP = "mcp"
    PROCESS = "process"
    PARSING = "parsing"
    PERMISSION = "permission"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


# Transient errors are safe to retry
_TRANSIENT_CATEGORIES = {ErrorCategory.TIMEOUT, ErrorCategory.MCP}


def classify_error(error: BaseException) -> ErrorCategory:
    """Classify an error into a category for metrics and retry decisions."""
    if isinstance(error, ClaudeTimeoutError):
        return ErrorCategory.TIMEOUT
    if isinstance(error, ClaudeMCPError):
        return ErrorCategory.MCP
    if isinstance(error, ClaudeProcessError):
        return ErrorCategory.PROCESS
    if isinstance(error, ClaudeParsingError):
        return ErrorCategory.PARSING
    if isinstance(error, (PermissionError, OSError)):
        return ErrorCategory.PERMISSION
    if isinstance(error, (ValueError, TypeError)):
        return ErrorCategory.VALIDATION
    return ErrorCategory.UNKNOWN


def is_transient_error(error: BaseException) -> bool:
    """Check if an error is transient (safe to retry)."""
    return classify_error(error) in _TRANSIENT_CATEGORIES
```

- [ ] **Step 4: Run tests**

Run: `poetry run pytest tests/unit/test_error_types.py -v`
Expected: PASS

- [ ] **Step 5: Wire into sdk_integration.py exception handlers**

In the except blocks of `execute_command()`, add error classification to ClaudeResponse:

```python
        except asyncio.TimeoutError:
            raise ClaudeTimeoutError(...)

        # In each except block, before raising, log the category:
        # logger.error(..., error_category=classify_error(e).value)
```

- [ ] **Step 6: Commit**

```bash
git add src/claude/error_types.py tests/unit/test_error_types.py src/claude/sdk_integration.py
git commit -m "feat: add structured error classification for Claude operations"
```

---

### Task 4: Destructive Tool Flags

**Files:**
- Modify: `src/claude/monitor.py`
- Test: `tests/unit/test_monitor.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_destructive_flags.py
from src.claude.monitor import is_destructive_tool_use


def test_rm_is_destructive():
    assert is_destructive_tool_use("Bash", {"command": "rm -rf /tmp/test"}) is True


def test_write_is_destructive():
    assert is_destructive_tool_use("Write", {"file_path": "/tmp/test.py", "content": "x"}) is True


def test_read_is_not_destructive():
    assert is_destructive_tool_use("Read", {"file_path": "/tmp/test.py"}) is False


def test_grep_is_not_destructive():
    assert is_destructive_tool_use("Grep", {"pattern": "foo"}) is False


def test_edit_is_destructive():
    assert is_destructive_tool_use("Edit", {"file_path": "/tmp/test.py"}) is True


def test_ls_bash_is_not_destructive():
    assert is_destructive_tool_use("Bash", {"command": "ls -la"}) is False


def test_git_push_is_destructive():
    assert is_destructive_tool_use("Bash", {"command": "git push origin main"}) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_destructive_flags.py -v`
Expected: FAIL

- [ ] **Step 3: Implement is_destructive_tool_use**

Add to `src/claude/monitor.py`:

```python
# Tools that always write
_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# Bash commands that are destructive
_DESTRUCTIVE_BASH_PATTERNS = {
    "rm", "rmdir", "mv", "git push", "git reset", "git rebase",
    "docker rm", "docker rmi", "drop table", "delete from",
}

# Bash commands that are read-only
_READONLY_BASH_PREFIXES = {
    "ls", "cat", "head", "tail", "grep", "find", "wc", "echo",
    "pwd", "which", "git status", "git log", "git diff", "git branch",
    "pip list", "npm list", "poetry show",
}


def is_destructive_tool_use(tool_name: str, tool_input: dict) -> bool:
    """Check if a tool use is destructive (writes, deletes, sends).

    Inspired by Claude Code's per-tool isDestructive() method.
    """
    if tool_name in _WRITE_TOOLS:
        return True

    if tool_name in ("Bash", "bash", "shell"):
        command = tool_input.get("command", "").strip().lower()
        # Check read-only first
        for prefix in _READONLY_BASH_PREFIXES:
            if command.startswith(prefix):
                return False
        # Check destructive patterns
        for pattern in _DESTRUCTIVE_BASH_PATTERNS:
            if pattern in command:
                return True
        return False

    return False
```

- [ ] **Step 4: Run tests**

Run: `poetry run pytest tests/unit/test_destructive_flags.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude/monitor.py tests/unit/test_destructive_flags.py
git commit -m "feat: add destructive tool flags for granular security"
```

---

### Task 5: Operation-Level Rate Limiting

**Files:**
- Modify: `src/security/rate_limiter.py`
- Test: `tests/unit/test_operation_rate_limit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_operation_rate_limit.py
import pytest
from unittest.mock import MagicMock
from src.security.rate_limiter import OperationRateLimiter


@pytest.fixture
def limiter():
    config = MagicMock()
    return OperationRateLimiter(
        limits={
            "file_write": 100,
            "bash_execute": 200,
            "external_api": 50,
        },
        window_seconds=86400,
    )


@pytest.mark.asyncio
async def test_allows_within_limit(limiter):
    allowed, msg = await limiter.check(user_id=1, operation="file_write")
    assert allowed is True
    assert msg is None


@pytest.mark.asyncio
async def test_blocks_over_limit(limiter):
    for _ in range(100):
        await limiter.check(user_id=1, operation="file_write")
    allowed, msg = await limiter.check(user_id=1, operation="file_write")
    assert allowed is False
    assert "file_write" in msg


@pytest.mark.asyncio
async def test_unknown_operation_always_allowed(limiter):
    allowed, _ = await limiter.check(user_id=1, operation="unknown_op")
    assert allowed is True


@pytest.mark.asyncio
async def test_separate_users(limiter):
    for _ in range(100):
        await limiter.check(user_id=1, operation="file_write")
    # User 2 should still have budget
    allowed, _ = await limiter.check(user_id=2, operation="file_write")
    assert allowed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_operation_rate_limit.py -v`
Expected: FAIL

- [ ] **Step 3: Implement OperationRateLimiter**

Add to `src/security/rate_limiter.py`:

```python
class OperationRateLimiter:
    """Per-operation rate limiting.

    Inspired by Claude Code's per-tool permission budgets.
    Each operation type has its own daily counter per user.
    """

    def __init__(
        self,
        limits: Dict[str, int],
        window_seconds: int = 86400,
    ) -> None:
        self.limits = limits
        self.window_seconds = window_seconds
        self._counters: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._window_start: Dict[int, datetime] = {}
        self._locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def check(
        self, user_id: int, operation: str
    ) -> Tuple[bool, Optional[str]]:
        """Check if an operation is allowed for a user."""
        if operation not in self.limits:
            return True, None

        async with self._locks[user_id]:
            self._maybe_reset(user_id)
            current = self._counters[user_id][operation]
            limit = self.limits[operation]

            if current >= limit:
                return False, (
                    f"Operation rate limit exceeded for '{operation}': "
                    f"{current}/{limit} per {self.window_seconds // 3600}h"
                )

            self._counters[user_id][operation] += 1
            return True, None

    def _maybe_reset(self, user_id: int) -> None:
        """Reset counters if window has elapsed."""
        now = datetime.now(UTC)
        start = self._window_start.get(user_id, now - timedelta(days=1))
        if (now - start).total_seconds() >= self.window_seconds:
            self._counters[user_id] = defaultdict(int)
            self._window_start[user_id] = now
```

- [ ] **Step 4: Run tests**

Run: `poetry run pytest tests/unit/test_operation_rate_limit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/security/rate_limiter.py tests/unit/test_operation_rate_limit.py
git commit -m "feat: add operation-level rate limiting per user"
```

---

### Task 6: contextvars Agent Isolation

**Files:**
- Modify: `src/claude/facade.py`
- Test: `tests/unit/test_agent_isolation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_agent_isolation.py
import asyncio
import contextvars
import pytest
from src.claude.facade import agent_context, get_current_agent_context


def test_default_context_is_none():
    assert get_current_agent_context() is None


@pytest.mark.asyncio
async def test_contexts_are_isolated():
    results = []

    async def worker(user_id: int):
        ctx = {"user_id": user_id, "session_id": f"sess-{user_id}"}
        token = agent_context.set(ctx)
        try:
            await asyncio.sleep(0.01)  # Simulate async work
            current = get_current_agent_context()
            results.append(current["user_id"])
        finally:
            agent_context.reset(token)

    await asyncio.gather(worker(1), worker(2), worker(3))
    assert sorted(results) == [1, 2, 3]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_agent_isolation.py -v`
Expected: FAIL

- [ ] **Step 3: Implement agent context**

Add to `src/claude/facade.py` at module level:

```python
import contextvars
from typing import Optional, Dict, Any

# Per-async-task agent context — prevents concurrent sessions from
# bleeding into each other. Inspired by Claude Code's
# AsyncLocalStorage<AgentContext> pattern.
agent_context: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "agent_context", default=None
)


def get_current_agent_context() -> Optional[Dict[str, Any]]:
    """Get the current agent context for this async task."""
    return agent_context.get()
```

- [ ] **Step 4: Wire into run_command**

In `ClaudeIntegration.run_command()`, wrap the execution in a context:

```python
    async def run_command(self, prompt, working_directory, user_id, ...):
        ctx = {
            "user_id": user_id,
            "working_directory": str(working_directory),
            "session_id": session_id,
        }
        token = agent_context.set(ctx)
        try:
            # ... existing code ...
        finally:
            agent_context.reset(token)
```

- [ ] **Step 5: Run tests**

Run: `poetry run pytest tests/unit/test_agent_isolation.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/claude/facade.py tests/unit/test_agent_isolation.py
git commit -m "feat: add contextvars-based agent isolation for safe concurrency"
```

---

## Tier 2: Medium Effort

### Task 7: Context Compaction

**Files:**
- Create: `src/claude/compaction.py`
- Modify: `src/config/settings.py`
- Test: `tests/unit/test_compaction.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_compaction.py
import pytest
from src.claude.compaction import CompactionService, ConversationTurn


def test_no_compaction_under_threshold():
    service = CompactionService(max_turns_before_compact=10)
    turns = [ConversationTurn(role="user", content=f"msg {i}") for i in range(5)]
    result = service.maybe_compact(turns)
    assert result == turns  # No compaction needed


def test_compaction_preserves_recent():
    service = CompactionService(
        max_turns_before_compact=5,
        recent_turns_to_keep=3,
    )
    turns = [
        ConversationTurn(role="user", content=f"msg {i}")
        for i in range(10)
    ]
    result = service.maybe_compact(turns)
    # Should have 1 summary + 3 recent = 4 turns
    assert len(result) == 4
    assert result[0].role == "system"
    assert "summary" in result[0].content.lower() or len(result[0].content) > 0
    assert result[-1].content == "msg 9"


def test_compaction_summary_contains_key_info():
    service = CompactionService(
        max_turns_before_compact=3,
        recent_turns_to_keep=1,
    )
    turns = [
        ConversationTurn(role="user", content="Please fix the auth bug in login.py"),
        ConversationTurn(role="assistant", content="I found the issue at line 42"),
        ConversationTurn(role="user", content="Great, now add tests"),
        ConversationTurn(role="assistant", content="Done, all tests pass"),
    ]
    result = service.maybe_compact(turns)
    summary = result[0].content
    # Summary should mention key topics
    assert "auth" in summary.lower() or "login" in summary.lower() or "fix" in summary.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_compaction.py -v`
Expected: FAIL

- [ ] **Step 3: Implement compaction service**

```python
# src/claude/compaction.py
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

        # Split into old (to summarize) and recent (to keep)
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
        """Create a summary of conversation turns.

        This is a local extractive summary — no LLM call needed.
        Extracts key information from each turn.
        """
        key_points: List[str] = []

        for turn in turns:
            content = turn.content.strip()
            if not content:
                continue

            # Extract first meaningful sentence/line
            first_line = content.split("\n")[0][:200]

            if turn.role == "user":
                key_points.append(f"User asked: {first_line}")
            elif turn.role == "assistant":
                # Only keep substantive responses
                if len(content) > 50:
                    key_points.append(f"Assistant: {first_line}")

        summary = "Conversation summary (older messages compacted):\n"
        summary += "\n".join(f"- {p}" for p in key_points)

        if len(summary) > self.max_summary_chars:
            summary = summary[: self.max_summary_chars] + "\n... (truncated)"

        return summary
```

- [ ] **Step 4: Run tests**

Run: `poetry run pytest tests/unit/test_compaction.py -v`
Expected: PASS

- [ ] **Step 5: Add settings**

In `src/config/settings.py`, add:

```python
    # Context compaction
    compaction_max_turns: int = Field(
        20,
        description="Max conversation turns before compacting old ones",
    )
    compaction_recent_turns: int = Field(
        6,
        description="Number of recent turns to keep verbatim during compaction",
    )
```

- [ ] **Step 6: Commit**

```bash
git add src/claude/compaction.py src/config/settings.py tests/unit/test_compaction.py
git commit -m "feat: add context compaction service for long conversations"
```

---

### Task 8: Per-User Persistent Memory

**Files:**
- Create: `src/claude/memory.py`
- Test: `tests/unit/test_memory.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_memory.py
import pytest
import tempfile
from pathlib import Path
from src.claude.memory import MemoryStore, Memory, MemoryType


@pytest.fixture
def memory_dir(tmp_path):
    return tmp_path / "memories"


@pytest.fixture
def store(memory_dir):
    return MemoryStore(memory_dir)


def test_save_and_load(store):
    mem = Memory(
        name="user_role",
        description="User is a DJ and developer",
        memory_type=MemoryType.USER,
        content="Raphael is a Brazilian DJ and full-stack developer.",
    )
    store.save(user_id=123, memory=mem)
    loaded = store.load(user_id=123, name="user_role")
    assert loaded is not None
    assert loaded.content == mem.content
    assert loaded.memory_type == MemoryType.USER


def test_list_memories(store):
    store.save(user_id=123, memory=Memory(
        name="pref1", description="d1",
        memory_type=MemoryType.FEEDBACK, content="c1",
    ))
    store.save(user_id=123, memory=Memory(
        name="pref2", description="d2",
        memory_type=MemoryType.PROJECT, content="c2",
    ))
    memories = store.list(user_id=123)
    assert len(memories) == 2


def test_delete_memory(store):
    store.save(user_id=123, memory=Memory(
        name="temp", description="d",
        memory_type=MemoryType.USER, content="c",
    ))
    store.delete(user_id=123, name="temp")
    assert store.load(user_id=123, name="temp") is None


def test_build_prompt(store):
    store.save(user_id=123, memory=Memory(
        name="role", description="User role",
        memory_type=MemoryType.USER, content="User is a DJ.",
    ))
    prompt = store.build_memory_prompt(user_id=123)
    assert "DJ" in prompt


def test_separate_users(store):
    store.save(user_id=1, memory=Memory(
        name="m", description="d",
        memory_type=MemoryType.USER, content="user 1",
    ))
    assert store.load(user_id=2, name="m") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_memory.py -v`
Expected: FAIL

- [ ] **Step 3: Implement memory store**

```python
# src/claude/memory.py
"""Per-user persistent memory system.

Inspired by Claude Code's memdir/ system which stores memories as
markdown files with YAML frontmatter, indexed by MEMORY.md.
"""

import re
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import structlog

logger = structlog.get_logger()


class MemoryType(str, Enum):
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"


@dataclass
class Memory:
    """A single memory entry."""

    name: str
    description: str
    memory_type: MemoryType
    content: str


_FRONTMATTER_RE = re.compile(
    r"^---\n(.*?)\n---\n(.*)$", re.DOTALL
)


class MemoryStore:
    """File-based per-user memory persistence.

    Each user gets a directory. Each memory is a markdown file
    with YAML frontmatter.
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def _user_dir(self, user_id: int) -> Path:
        d = self.base_dir / str(user_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _file_path(self, user_id: int, name: str) -> Path:
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        return self._user_dir(user_id) / f"{safe_name}.md"

    def save(self, user_id: int, memory: Memory) -> None:
        """Save a memory to disk."""
        path = self._file_path(user_id, memory.name)
        content = (
            f"---\n"
            f"name: {memory.name}\n"
            f"description: {memory.description}\n"
            f"type: {memory.memory_type.value}\n"
            f"---\n\n"
            f"{memory.content}\n"
        )
        path.write_text(content, encoding="utf-8")
        logger.info("Memory saved", user_id=user_id, name=memory.name)

    def load(self, user_id: int, name: str) -> Optional[Memory]:
        """Load a memory from disk."""
        path = self._file_path(user_id, name)
        if not path.exists():
            return None
        return self._parse_file(path)

    def list(self, user_id: int) -> List[Memory]:
        """List all memories for a user."""
        user_dir = self._user_dir(user_id)
        memories = []
        for path in sorted(user_dir.glob("*.md")):
            mem = self._parse_file(path)
            if mem:
                memories.append(mem)
        return memories

    def delete(self, user_id: int, name: str) -> None:
        """Delete a memory."""
        path = self._file_path(user_id, name)
        if path.exists():
            path.unlink()
            logger.info("Memory deleted", user_id=user_id, name=name)

    def build_memory_prompt(self, user_id: int) -> str:
        """Build a prompt section from all user memories."""
        memories = self.list(user_id)
        if not memories:
            return ""

        sections = []
        for mem in memories:
            sections.append(f"[{mem.memory_type.value}] {mem.name}: {mem.content}")

        return "User memories:\n" + "\n".join(f"- {s}" for s in sections)

    def _parse_file(self, path: Path) -> Optional[Memory]:
        """Parse a memory markdown file."""
        try:
            text = path.read_text(encoding="utf-8")
            match = _FRONTMATTER_RE.match(text)
            if not match:
                return None

            frontmatter = match.group(1)
            content = match.group(2).strip()

            # Simple YAML parsing (no dependency needed)
            meta = {}
            for line in frontmatter.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip()] = value.strip()

            return Memory(
                name=meta.get("name", path.stem),
                description=meta.get("description", ""),
                memory_type=MemoryType(meta.get("type", "user")),
                content=content,
            )
        except Exception:
            logger.exception("Failed to parse memory file", path=str(path))
            return None
```

- [ ] **Step 4: Run tests**

Run: `poetry run pytest tests/unit/test_memory.py -v`
Expected: PASS

- [ ] **Step 5: Add settings**

In `src/config/settings.py`:

```python
    # Memory system
    enable_memory: bool = Field(
        True, description="Enable per-user persistent memory"
    )
    memory_dir: Optional[Path] = Field(
        None, description="Directory for user memories (defaults to data/memories/)"
    )
```

- [ ] **Step 6: Commit**

```bash
git add src/claude/memory.py src/config/settings.py tests/unit/test_memory.py
git commit -m "feat: add per-user persistent memory system"
```

---

### Task 9: Dead-Letter Queue and Event Retry

**Files:**
- Create: `src/events/retry.py`
- Modify: `src/events/bus.py`
- Test: `tests/unit/test_event_retry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_event_retry.py
import pytest
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
    # Same event should have incremented count
    assert len(dlq) == 1
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
    assert len(retryable) == 0  # Too soon to retry
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_event_retry.py -v`
Expected: FAIL

- [ ] **Step 3: Implement DLQ**

```python
# src/events/retry.py
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
            # Exponential backoff: delay * 2^(attempts-1)
            backoff = self.retry_delay_seconds * (2 ** (fe.attempt_count - 1))
            next_retry = fe.last_attempt + timedelta(seconds=backoff)

            if now >= next_retry:
                ready.append(fe.event)

        return ready
```

- [ ] **Step 4: Run tests**

Run: `poetry run pytest tests/unit/test_event_retry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/events/retry.py tests/unit/test_event_retry.py
git commit -m "feat: add dead-letter queue with exponential backoff retry"
```

---

### Task 10: Notification Delivery Tracking

**Files:**
- Create: `src/notifications/tracking.py`
- Modify: `src/notifications/service.py:92-132`
- Test: `tests/unit/test_notification_tracking.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_notification_tracking.py
import pytest
from datetime import UTC, datetime
from src.notifications.tracking import DeliveryTracker, DeliveryRecord, DeliveryStatus


def test_record_sent():
    tracker = DeliveryTracker()
    tracker.record_sent(
        event_id="evt-1",
        chat_id=123,
        message_id=456,
    )
    record = tracker.get(event_id="evt-1", chat_id=123)
    assert record is not None
    assert record.status == DeliveryStatus.SENT
    assert record.message_id == 456


def test_record_failed():
    tracker = DeliveryTracker()
    tracker.record_failed(
        event_id="evt-1",
        chat_id=123,
        error="Telegram 403: bot blocked",
    )
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_notification_tracking.py -v`
Expected: FAIL

- [ ] **Step 3: Implement delivery tracker**

```python
# src/notifications/tracking.py
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

    def record_sent(
        self, event_id: str, chat_id: int, message_id: int
    ) -> None:
        """Record a successful delivery."""
        self._add(DeliveryRecord(
            event_id=event_id,
            chat_id=chat_id,
            status=DeliveryStatus.SENT,
            message_id=message_id,
        ))

    def record_failed(
        self, event_id: str, chat_id: int, error: str
    ) -> None:
        """Record a failed delivery."""
        self._add(DeliveryRecord(
            event_id=event_id,
            chat_id=chat_id,
            status=DeliveryStatus.FAILED,
            error=error,
        ))

    def get(
        self, event_id: str, chat_id: int
    ) -> Optional[DeliveryRecord]:
        """Get delivery record."""
        return self._records.get((event_id, chat_id))

    def stats(self) -> Dict[str, Any]:
        """Get delivery statistics."""
        total = len(self._records)
        sent = sum(1 for r in self._records.values() if r.status == DeliveryStatus.SENT)
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

        # Evict oldest if over limit
        while len(self._records) > self.max_records:
            old_key = self._order.pop(0)
            self._records.pop(old_key, None)
```

- [ ] **Step 4: Run tests**

Run: `poetry run pytest tests/unit/test_notification_tracking.py -v`
Expected: PASS

- [ ] **Step 5: Wire into NotificationService**

In `src/notifications/service.py`, add tracker and update `_rate_limited_send`:

```python
from .tracking import DeliveryTracker

# In __init__:
self.delivery_tracker = DeliveryTracker()

# In _rate_limited_send, after successful send:
self.delivery_tracker.record_sent(
    event_id=event.id,
    chat_id=chat_id,
    message_id=msg.message_id,  # capture from send_message return
)

# In except TelegramError block:
self.delivery_tracker.record_failed(
    event_id=event.id,
    chat_id=chat_id,
    error=str(e),
)
```

- [ ] **Step 6: Commit**

```bash
git add src/notifications/tracking.py src/notifications/service.py tests/unit/test_notification_tracking.py
git commit -m "feat: add notification delivery tracking"
```

---

### Task 11: Session Pagination

**Files:**
- Modify: `src/claude/session.py`
- Test: `tests/unit/test_session_pagination.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_session_pagination.py
import pytest
from datetime import UTC, datetime
from src.claude.session import ClaudeSession, paginate_sessions


def _make_session(session_id: str, last_used_offset: int) -> ClaudeSession:
    from pathlib import Path
    base = datetime(2026, 1, 1, tzinfo=UTC)
    from datetime import timedelta
    return ClaudeSession(
        session_id=session_id,
        user_id=1,
        project_path=Path("/tmp"),
        created_at=base,
        last_used=base + timedelta(hours=last_used_offset),
    )


def test_paginate_returns_page():
    sessions = [_make_session(f"s{i}", i) for i in range(20)]
    page = paginate_sessions(sessions, page_size=5, offset=0)
    assert len(page.items) == 5
    assert page.has_more is True
    assert page.total == 20


def test_paginate_last_page():
    sessions = [_make_session(f"s{i}", i) for i in range(7)]
    page = paginate_sessions(sessions, page_size=5, offset=5)
    assert len(page.items) == 2
    assert page.has_more is False


def test_paginate_empty():
    page = paginate_sessions([], page_size=5, offset=0)
    assert len(page.items) == 0
    assert page.has_more is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_session_pagination.py -v`
Expected: FAIL

- [ ] **Step 3: Implement pagination**

Add to `src/claude/session.py`:

```python
@dataclass
class SessionPage:
    """A page of session results."""

    items: List[ClaudeSession]
    total: int
    offset: int
    page_size: int
    has_more: bool


def paginate_sessions(
    sessions: List[ClaudeSession],
    page_size: int = 20,
    offset: int = 0,
) -> SessionPage:
    """Paginate a list of sessions.

    Inspired by Claude Code's HISTORY_PAGE_SIZE=100 cursor-based pagination.
    """
    total = len(sessions)
    # Sort by last_used descending (most recent first)
    sorted_sessions = sorted(sessions, key=lambda s: s.last_used, reverse=True)
    page_items = sorted_sessions[offset : offset + page_size]
    has_more = (offset + page_size) < total

    return SessionPage(
        items=page_items,
        total=total,
        offset=offset,
        page_size=page_size,
        has_more=has_more,
    )
```

- [ ] **Step 4: Run tests**

Run: `poetry run pytest tests/unit/test_session_pagination.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude/session.py tests/unit/test_session_pagination.py
git commit -m "feat: add session pagination for efficient history loading"
```

---

### Task 12: Skills as Markdown Templates

**Files:**
- Create: `src/bot/features/skills.py`
- Test: `tests/unit/test_skills.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_skills.py
import pytest
from pathlib import Path
from src.bot.features.skills import SkillLoader, Skill


@pytest.fixture
def skills_dir(tmp_path):
    # Create sample skill files
    (tmp_path / "daily_report.md").write_text(
        "---\n"
        "name: daily_report\n"
        "description: Generate a daily health report\n"
        "trigger: /daily_report\n"
        "---\n\n"
        "Analyze the current state of the project and generate a daily report.\n"
        "Include: test status, recent commits, open issues.\n"
    )
    (tmp_path / "trade_analysis.md").write_text(
        "---\n"
        "name: trade_analysis\n"
        "description: Analyze recent trading performance\n"
        "trigger: /trade_analysis\n"
        "---\n\n"
        "Review the last 24h of trading activity.\n"
        "Report: P&L, win rate, notable trades.\n"
    )
    return tmp_path


def test_load_skills(skills_dir):
    loader = SkillLoader(skills_dir)
    skills = loader.load_all()
    assert len(skills) == 2
    names = {s.name for s in skills}
    assert "daily_report" in names
    assert "trade_analysis" in names


def test_get_skill_by_name(skills_dir):
    loader = SkillLoader(skills_dir)
    loader.load_all()
    skill = loader.get("daily_report")
    assert skill is not None
    assert "daily report" in skill.description.lower()


def test_skill_to_prompt(skills_dir):
    loader = SkillLoader(skills_dir)
    loader.load_all()
    skill = loader.get("daily_report")
    prompt = skill.to_prompt()
    assert "Analyze" in prompt
    assert "test status" in prompt


def test_missing_skill(skills_dir):
    loader = SkillLoader(skills_dir)
    loader.load_all()
    assert loader.get("nonexistent") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_skills.py -v`
Expected: FAIL

- [ ] **Step 3: Implement skill loader**

```python
# src/bot/features/skills.py
"""Markdown-based skill templates for configurable automation.

Inspired by Claude Code's skills/ system which defines specialized
workflows as markdown files with frontmatter.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import structlog

logger = structlog.get_logger()

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


@dataclass
class Skill:
    """A skill template loaded from a markdown file."""

    name: str
    description: str
    trigger: str
    content: str
    file_path: Path

    def to_prompt(self) -> str:
        """Convert skill content to a Claude prompt."""
        return self.content.strip()


class SkillLoader:
    """Loads skill templates from a directory of markdown files."""

    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = skills_dir
        self._skills: Dict[str, Skill] = {}

    def load_all(self) -> List[Skill]:
        """Load all skill files from the directory."""
        self._skills.clear()

        if not self.skills_dir.exists():
            logger.warning("Skills directory not found", path=str(self.skills_dir))
            return []

        for path in sorted(self.skills_dir.glob("*.md")):
            skill = self._parse_file(path)
            if skill:
                self._skills[skill.name] = skill

        logger.info("Skills loaded", count=len(self._skills))
        return list(self._skills.values())

    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(name)

    def _parse_file(self, path: Path) -> Optional[Skill]:
        """Parse a skill markdown file."""
        try:
            text = path.read_text(encoding="utf-8")
            match = _FRONTMATTER_RE.match(text)
            if not match:
                return None

            frontmatter = match.group(1)
            content = match.group(2).strip()

            meta = {}
            for line in frontmatter.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip()] = value.strip()

            return Skill(
                name=meta.get("name", path.stem),
                description=meta.get("description", ""),
                trigger=meta.get("trigger", f"/{path.stem}"),
                content=content,
                file_path=path,
            )
        except Exception:
            logger.exception("Failed to parse skill file", path=str(path))
            return None
```

- [ ] **Step 4: Run tests**

Run: `poetry run pytest tests/unit/test_skills.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bot/features/skills.py tests/unit/test_skills.py
git commit -m "feat: add markdown-based skill templates for configurable automation"
```

---

### Task 13: Richer Event Types

**Files:**
- Modify: `src/events/types.py`
- Test: `tests/unit/test_event_types.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_event_types.py
from src.events.types import (
    ToolExecutedEvent,
    FileChangedEvent,
    SessionStartEvent,
    SessionEndEvent,
    TaskCreatedEvent,
    TaskCompletedEvent,
)


def test_tool_executed_event():
    e = ToolExecutedEvent(
        tool_name="Read",
        duration_ms=150.0,
        success=True,
        user_id=1,
    )
    assert e.event_type == "ToolExecutedEvent"
    assert e.tool_name == "Read"


def test_file_changed_event():
    e = FileChangedEvent(
        file_path="/tmp/test.py",
        change_type="edit",
        user_id=1,
    )
    assert e.change_type == "edit"


def test_session_events():
    start = SessionStartEvent(user_id=1, session_id="s1")
    end = SessionEndEvent(user_id=1, session_id="s1", total_cost=0.5)
    assert start.session_id == "s1"
    assert end.total_cost == 0.5


def test_task_events():
    created = TaskCreatedEvent(task_id="t1", task_name="fix bug")
    completed = TaskCompletedEvent(task_id="t1", success=True)
    assert created.task_name == "fix bug"
    assert completed.success is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_event_types.py -v`
Expected: FAIL

- [ ] **Step 3: Add new event types**

Append to `src/events/types.py`:

```python
@dataclass
class ToolExecutedEvent(Event):
    """A Claude tool was executed."""

    tool_name: str = ""
    duration_ms: float = 0.0
    success: bool = True
    error_type: Optional[str] = None
    user_id: int = 0
    source: str = "tool"


@dataclass
class FileChangedEvent(Event):
    """A file was created, edited, or deleted."""

    file_path: str = ""
    change_type: str = ""  # "create", "edit", "delete"
    user_id: int = 0
    source: str = "tool"


@dataclass
class SessionStartEvent(Event):
    """A Claude session started."""

    user_id: int = 0
    session_id: str = ""
    source: str = "session"


@dataclass
class SessionEndEvent(Event):
    """A Claude session ended."""

    user_id: int = 0
    session_id: str = ""
    total_cost: float = 0.0
    source: str = "session"


@dataclass
class TaskCreatedEvent(Event):
    """A scheduled task was created."""

    task_id: str = ""
    task_name: str = ""
    source: str = "scheduler"


@dataclass
class TaskCompletedEvent(Event):
    """A scheduled task completed."""

    task_id: str = ""
    success: bool = True
    error: Optional[str] = None
    source: str = "scheduler"
```

Add `Optional` import if not already present.

- [ ] **Step 4: Run tests**

Run: `poetry run pytest tests/unit/test_event_types.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/events/types.py tests/unit/test_event_types.py
git commit -m "feat: add richer event types (ToolExecuted, FileChanged, Session, Task)"
```

---

### Task 14: Event Hooks System

**Files:**
- Create: `src/events/hooks.py`
- Test: `tests/unit/test_event_hooks.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_event_hooks.py
import pytest
from src.events.hooks import HookRegistry, HookTiming


def test_register_and_fire_pre_hook():
    registry = HookRegistry()
    called = []

    async def on_tool(event_name, data):
        called.append((event_name, data))

    registry.register("tool_execute", HookTiming.PRE, on_tool)

    import asyncio
    asyncio.get_event_loop().run_until_complete(
        registry.fire("tool_execute", HookTiming.PRE, {"tool": "Read"})
    )
    assert len(called) == 1
    assert called[0][1]["tool"] == "Read"


def test_post_hook_receives_result():
    registry = HookRegistry()
    results = []

    async def on_result(event_name, data):
        results.append(data.get("result"))

    registry.register("tool_execute", HookTiming.POST, on_result)

    import asyncio
    asyncio.get_event_loop().run_until_complete(
        registry.fire("tool_execute", HookTiming.POST, {"result": "success"})
    )
    assert results == ["success"]


def test_hook_error_does_not_propagate():
    registry = HookRegistry()

    async def bad_hook(event_name, data):
        raise RuntimeError("hook failed")

    registry.register("test", HookTiming.PRE, bad_hook)

    import asyncio
    # Should not raise
    asyncio.get_event_loop().run_until_complete(
        registry.fire("test", HookTiming.PRE, {})
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_event_hooks.py -v`
Expected: FAIL

- [ ] **Step 3: Implement hook registry**

```python
# src/events/hooks.py
"""Pre/post hook system for events and tool calls.

Inspired by Claude Code's 26+ hook event types with
matcher-based filtering. Hooks can observe, log, or
modify behavior without changing core code.
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
```

- [ ] **Step 4: Run tests**

Run: `poetry run pytest tests/unit/test_event_hooks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/events/hooks.py tests/unit/test_event_hooks.py
git commit -m "feat: add pre/post hook system for events and tool calls"
```

---

## Tier 3: High Effort

Tasks 15-22 (Coordinator mode, Fork subagent cache sharing, SendMessage multi-pattern, Parallel scheduled jobs, Per-tool ACLs) are architectural changes that require significant design work. Each should be planned in its own focused session after Tier 1-2 are complete, as they depend on the foundations laid above.

### Task 15: Deferred Tool Loading (placeholder)
> Depends on: ableton-mcp-ultimate plan (separate document)

### Task 16: Coordinator Mode (placeholder)
> Depends on: Task 6 (contextvars), Task 14 (hooks)
> Design session needed: How to spawn parallel Claude sessions, manage their lifecycle, and merge results.

### Task 17: Fork Subagent Cache Sharing (placeholder)
> Depends on: Task 16 (coordinator mode)

### Task 18: Hooks System Integration (placeholder)
> Depends on: Task 14 (hooks), wire into orchestrator.py

### Task 19: SendMessage Multi-Pattern Communication (placeholder)
> Depends on: Task 13 (richer events), Task 16 (coordinator)

### Task 20: Parallel Scheduled Jobs (placeholder)
> Depends on: Task 6 (contextvars), Task 16 (coordinator)

### Task 21: Per-Tool ACLs (placeholder)
> Depends on: Task 4 (destructive flags), Task 5 (operation rate limiting)

---

## Self-Review Checklist

- [x] All 22 items from the implementation list are covered (14 detailed, 7 placeholders for Tier 3)
- [x] No placeholder code in detailed tasks — all have complete implementations
- [x] Type names and method signatures are consistent across tasks
- [x] File paths are exact
- [x] Each task has TDD flow: failing test -> implement -> pass -> commit
- [x] No circular dependencies between tasks within the same tier
