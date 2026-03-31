"""Structured error classification for Claude operations.

Inspired by Claude Code's error categorization which distinguishes
MCP errors, timeouts, permission denials, and validation failures.
"""

from enum import Enum

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
