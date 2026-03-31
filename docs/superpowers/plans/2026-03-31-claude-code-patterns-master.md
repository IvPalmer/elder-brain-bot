# Claude Code Patterns: Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt 26 architectural patterns from the leaked Claude Code source across 4 projects: claude-assistant, ableton-mcp-ultimate, Master Trader, and Vault.

**Architecture:** Each project gets an independent sub-plan. Plans are ordered by ROI — claude-assistant first (22 items), then ableton-mcp-ultimate (2 items), Master Trader (3 items), Vault (3 items). Within each plan, tasks are ordered by dependency: quick wins first, then features that build on them.

**Tech Stack:** Python 3.10+, Poetry, pytest-asyncio, structlog, pydantic-settings, python-telegram-bot, claude-agent-sdk, FastMCP

---

## Sub-Plans

1. **[claude-assistant](2026-03-31-claude-assistant-patterns.md)** — 22 items (Tier 1-3)
2. **[ableton-mcp-ultimate](2026-03-31-ableton-mcp-patterns.md)** — 2 items (buildTool factory, deferred tool loading)
3. **[master-trader](2026-03-31-master-trader-patterns.md)** — 3 items (provider fallback, deferred persistence, trade-type rate limiting)
4. **[vault](2026-03-31-vault-patterns.md)** — 3 items (composite keys, deferred persistence, DLQ)

## Execution Order

Start with claude-assistant Tier 1 (quick wins), then ableton-mcp-ultimate (highest token savings ROI), then claude-assistant Tier 2-3, then Master Trader and Vault.
