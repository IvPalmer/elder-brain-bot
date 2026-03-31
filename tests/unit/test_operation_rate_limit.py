"""Tests for operation-level rate limiting."""

import pytest
from src.security.rate_limiter import OperationRateLimiter


@pytest.fixture
def limiter():
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
    allowed, _ = await limiter.check(user_id=2, operation="file_write")
    assert allowed is True
