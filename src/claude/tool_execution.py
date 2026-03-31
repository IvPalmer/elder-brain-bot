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
