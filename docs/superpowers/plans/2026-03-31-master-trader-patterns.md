# Master Trader: Claude Code Patterns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt 3 patterns — provider fallback, deferred persistence, and per-trade-type rate limiting — to improve trading resilience and risk management.

**Architecture:** These patterns apply to the Freqtrade multi-bot trading system. Each is independent.

**Tech Stack:** Python 3.10+, Freqtrade, Docker, Prometheus

**Note:** This plan requires reading `/Users/palmer/Work/Dev/Master Trader` for exact strategy patterns, risk management code, and config structure before implementation.

---

### Task 1: Provider Fallback Pattern

**Concept:** When a primary data source or strategy fails, gracefully fall back to a secondary instead of failing the trade.

- [ ] **Step 1: Audit current error handling in strategies**

Read strategy files to identify where external dependencies (API calls, data feeds) can fail.

- [ ] **Step 2: Create fallback utility**

```python
# utils/fallback.py
async def execute_with_fallback(primary_fn, fallback_fn, context, logger):
    """Execute primary function, fall back to secondary on failure."""
    try:
        return await primary_fn(context)
    except (ConnectionError, TimeoutError) as e:
        logger.warning("Primary failed, using fallback", error=str(e))
        return await fallback_fn(context)
```

- [ ] **Step 3: Wire into strategy data fetching**

Apply fallback pattern to indicator calculations and signal generation.

- [ ] **Step 4: Test with simulated failures**

Mock primary failures and verify fallback is used.

- [ ] **Step 5: Commit**

---

### Task 2: Deferred Persistence

**Concept:** Wait for trade confirmation before persisting state, preventing inconsistent records.

- [ ] **Step 1: Audit current trade state persistence**

Find where trade state is written to disk/DB and whether it happens before or after exchange confirmation.

- [ ] **Step 2: Implement deferred write pattern**

Only persist trade records after exchange confirms the order, not when the signal is generated.

- [ ] **Step 3: Test with order rejection scenarios**

Verify that rejected orders don't leave stale records.

- [ ] **Step 4: Commit**

---

### Task 3: Per-Trade-Type Rate Limiting

**Concept:** Apply different rate limits to scalping vs. swing trades to manage risk exposure.

- [ ] **Step 1: Identify trade types in current strategies**

Map which strategies produce which trade types (scalp, swing, position).

- [ ] **Step 2: Implement trade-type rate limiter**

```python
TRADE_TYPE_LIMITS = {
    "scalp": {"max_per_hour": 20, "max_concurrent": 5},
    "swing": {"max_per_hour": 5, "max_concurrent": 10},
    "position": {"max_per_hour": 2, "max_concurrent": 3},
}
```

- [ ] **Step 3: Wire into strategy entry signals**

Check trade-type limits before allowing entry.

- [ ] **Step 4: Add Prometheus metrics for trade-type counts**

- [ ] **Step 5: Commit**
