"""Tests for contextvars-based agent isolation."""

import asyncio
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
            await asyncio.sleep(0.01)
            current = get_current_agent_context()
            results.append(current["user_id"])
        finally:
            agent_context.reset(token)

    await asyncio.gather(worker(1), worker(2), worker(3))
    assert sorted(results) == [1, 2, 3]
