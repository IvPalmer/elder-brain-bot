# Claude Code Patterns: Master Status

**Source:** Claude Code leaked source (npm source map, 512K lines TypeScript)
**Started:** 2026-03-31 | **Last updated:** 2026-03-31

Only patterns that directly map to Claude Code internals are listed here.
Generic engineering patterns (provider fallback, deferred persistence, trade-type rate limiting, composite key ownership) that were opportunistically bundled into the original planning session are excluded.

---

## claude-assistant — 16 patterns

### Built + Wired ✅

| Pattern | Module | Claude Code Source | Wired In |
|---------|--------|--------------------|----------|
| Pre-filter denied tools | `sdk_integration.py:filter_denied_tools()` | `filterToolsByDenyRules()` | `execute_command()` builds `ClaudeAgentOptions` |
| Tool execution tracking | `claude/tool_execution.py` | Tool instrumentation / metrics | `sdk_integration.py` records from messages, logs summary |
| Error classification | `claude/error_types.py` | Error categorization (MCP, timeout, permission) | `facade.py` retry logic + error logging |
| Destructive tool flags | `claude/monitor.py:is_destructive_tool_use()` | `isDestructiveToolUse()` | `monitor.py` tool validation |
| Operation-level rate limiting | `security/rate_limiter.py:OperationRateLimiter` | Per-operation token buckets | Available in rate limiter module |
| contextvars agent isolation | `claude/facade.py:agent_context` | `AsyncLocalStorage<AgentContext>` | ContextVar per async task |
| Per-user persistent memory | `claude/memory.py:MemoryStore` | `memdir/` system (markdown + frontmatter) | `facade.py` injects into system prompt via `main.py` |
| Dead-letter queue | `events/retry.py:DeadLetterQueue` | Event retry with backoff | `main.py` → `event_bus.set_dlq()` |
| Notification delivery tracking | `notifications/tracking.py:DeliveryTracker` | Delivery status tracking | `main.py` → `notification_service.delivery_tracker` |
| Session pagination | `claude/session.py:paginate_sessions()` | Session list pagination | Available in session module |
| Richer event types | `events/types.py` (6 new types) | Typed event system | Registered in event bus |
| Event hooks | `events/hooks.py:HookRegistry` | Pre/post lifecycle hooks | `main.py` → `event_bus.set_hooks()` |
| Per-tool ACLs | `security/tool_acl.py:ToolACLManager` | `checkPermissions()` per tool | `sdk_integration.py` `can_use_tool` callback |
| Skills as markdown | `bot/features/skills.py:SkillLoader` | `skills/` system (markdown + frontmatter) | `main.py` loads from `skills/` dir, available via `bot_data` |
| Coordinator mode | `claude/coordinator.py:CoordinatorManager` | Parallel Claude workers | `main.py` instantiated, available via `bot_data` |

### Built, NOT Wired ⚠️

| Pattern | Module | Claude Code Source | Blocker |
|---------|--------|--------------------|---------|
| Context compaction | `claude/compaction.py:CompactionService` | `compact/` auto-compaction service | SDK manages conversation internally; no access to conversation turns |

---

## ableton-mcp-ultimate — 2 patterns

### Built + Wired ✅

| Pattern | Module | Claude Code Source | Wired In |
|---------|--------|--------------------|----------|
| Deferred tool loading / ToolSearch | `MCP_Server/tool_search.py:ToolSearchIndex` | `shouldDefer` + `ToolSearch` tool | `server.py` exposes `search_tools` + `list_tool_categories` MCP tools |

### Not Built ❌

| Pattern | Claude Code Source | What's Needed |
|---------|-------------------|---------------|
| buildTool factory | `buildTool()` with shared defaults | `tools/factory.py` wrapping `@mcp.tool()` with error handling, logging, validation defaults. Large refactor of 352 tools. |

---

## Master Trader — 0 genuine Claude Code patterns

The 3 items (provider fallback, deferred persistence, trade-type rate limiting) are generic resilience/risk patterns, not Claude Code specific. Removed from this tracker.

## Vault — 0 genuine Claude Code patterns

The 3 items (composite key ownership, deferred persistence, sync DLQ) are generic data integrity patterns, not Claude Code specific. Removed from this tracker.

---

## Summary

| Project | Total | Built+Wired | Built Only | Not Built |
|---------|-------|-------------|------------|-----------|
| claude-assistant | 16 | 15 | 1 | 0 |
| ableton-mcp-ultimate | 2 | 1 | 0 | 1 |
| **Total** | **18** | **16** | **1** | **1** |

### Remaining

1. **CompactionService** (claude-assistant) — blocked; SDK manages conversation turns internally, no hook point available
2. **buildTool factory** (ableton-mcp-ultimate) — large refactor of 352 tool definitions, lower urgency since ToolSearch already reduces token usage
