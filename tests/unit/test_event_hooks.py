"""Tests for event hooks system."""

import asyncio
import pytest
from src.events.hooks import HookRegistry, HookTiming


@pytest.mark.asyncio
async def test_register_and_fire_pre_hook():
    registry = HookRegistry()
    called = []

    async def on_tool(event_name, data):
        called.append((event_name, data))

    registry.register("tool_execute", HookTiming.PRE, on_tool)
    await registry.fire("tool_execute", HookTiming.PRE, {"tool": "Read"})
    assert len(called) == 1
    assert called[0][1]["tool"] == "Read"


@pytest.mark.asyncio
async def test_post_hook_receives_result():
    registry = HookRegistry()
    results = []

    async def on_result(event_name, data):
        results.append(data.get("result"))

    registry.register("tool_execute", HookTiming.POST, on_result)
    await registry.fire("tool_execute", HookTiming.POST, {"result": "success"})
    assert results == ["success"]


@pytest.mark.asyncio
async def test_hook_error_does_not_propagate():
    registry = HookRegistry()

    async def bad_hook(event_name, data):
        raise RuntimeError("hook failed")

    registry.register("test", HookTiming.PRE, bad_hook)
    await registry.fire("test", HookTiming.PRE, {})  # Should not raise
