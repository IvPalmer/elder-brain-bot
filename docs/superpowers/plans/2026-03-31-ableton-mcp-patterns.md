# Ableton MCP Ultimate: Claude Code Patterns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt 2 patterns from Claude Code — buildTool factory and deferred tool loading — to reduce boilerplate and save tokens (352 tools sending full schemas every turn is extremely expensive).

**Architecture:** The buildTool factory standardizes tool definitions with defaults. Deferred tool loading implements a ToolSearch-like system where only requested tool schemas are sent to the model, dramatically reducing token usage.

**Tech Stack:** Python 3.10+, FastMCP, Poetry

**Note:** This plan requires reading the actual ableton-mcp-ultimate codebase for exact tool definition patterns. A dedicated session should `cd /Users/palmer/Work/Dev/ableton-mcp-ultimate` and read the server file + 3-4 tool definitions before starting implementation.

---

### Task 1: buildTool Factory

**Concept:** Create a `build_tool()` function that provides safe defaults for all 352 tools, eliminating repetitive boilerplate.

**Approach:**
1. Read 5+ existing tool definitions to identify common patterns
2. Extract shared defaults (error handling, parameter validation, logging)
3. Create `build_tool()` factory that fills in defaults
4. Migrate 5 tools as proof of concept
5. Migrate remaining tools in batches

- [ ] **Step 1: Audit current tool patterns**

Read the server file and identify the tool registration pattern. Document:
- How tools are currently defined (decorator? function? class?)
- What parameters they share
- What error handling is duplicated

- [ ] **Step 2: Design build_tool interface**

Based on audit, create `src/tools/factory.py` with a `build_tool()` function that provides defaults for:
- Error handling (catch AbletonLive exceptions, return structured errors)
- Parameter validation
- Logging (structlog with tool name, inputs, duration)
- Response formatting

- [ ] **Step 3: Write tests for factory**

Test that build_tool produces a callable with correct defaults, error handling, and logging.

- [ ] **Step 4: Migrate 5 representative tools**

Pick tools from different categories (track, clip, transport, device, browser) and migrate them.

- [ ] **Step 5: Verify migrated tools work identically**

Run the tool test suite and verify no behavioral changes.

- [ ] **Step 6: Commit proof of concept**

- [ ] **Step 7: Batch-migrate remaining tools**

Migrate in groups of ~50, testing after each batch.

---

### Task 2: Deferred Tool Loading (ToolSearch)

**Concept:** Instead of sending all 352 tool schemas to Claude every turn (~70K+ tokens), send a `tool_search` meta-tool that lets Claude request specific tools by keyword.

**Approach:**

This is a significant architectural change to how the MCP server presents tools. Two possible implementations:

**Option A: MCP-level deferred loading**
- Register only ~20 "core" tools + a `search_tools` tool in MCP
- `search_tools` returns matching tool schemas from an index
- Claude calls `search_tools("drum")` → gets drum-related tool schemas
- Subsequent calls use the loaded tools

**Option B: Claude Code's ToolSearch pattern**
- All tools registered but with `defer_loading: true` metadata
- Claude Code's ToolSearch mechanism handles the deferred loading
- Requires Claude Code to support this for MCP tools (it does — see `alwaysLoad` and `shouldDefer` in Tool.ts)

- [ ] **Step 1: Audit token usage**

Measure current token usage per turn with all 352 tools loaded vs. a subset.

- [ ] **Step 2: Create tool search index**

Build a keyword→tool mapping:
```python
# src/tools/search_index.py
TOOL_INDEX = {
    "track": ["create_midi_track", "create_audio_track", "delete_track", ...],
    "clip": ["create_clip", "fire_clip", "stop_clip", ...],
    "drum": ["generate_drum_pattern", "get_drum_rack_pads", ...],
    "mix": ["set_track_volume", "set_track_pan", "set_eq_band", ...],
    ...
}
```

- [ ] **Step 3: Implement search_tools MCP tool**

```python
@mcp.tool()
async def search_tools(query: str) -> str:
    """Search for available Ableton tools by keyword.

    Returns matching tool names and descriptions.
    Use this to find the right tool before calling it.
    """
    matches = search_index.search(query)
    return format_tool_list(matches)
```

- [ ] **Step 4: Configure core vs. deferred tools**

Mark ~20 essential tools as "always loaded" (transport, basic track ops) and the rest as deferred.

- [ ] **Step 5: Test with Claude Code**

Verify that Claude can discover and use deferred tools via search.

- [ ] **Step 6: Measure token savings**

Compare before/after token usage per turn.

- [ ] **Step 7: Commit**
