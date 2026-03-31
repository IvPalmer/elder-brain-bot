# Vault: Claude Code Patterns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt 3 patterns — composite key ownership, deferred persistence, and dead-letter queue — to improve multi-tenant security and data reliability.

**Architecture:** These patterns apply to the Vault financial dashboard (Django REST backend + React frontend). Each is independent.

**Tech Stack:** Python 3.10+, Django REST Framework, React, SQLite

**Note:** This plan requires reading `/Users/palmer/Work/Dev/Vault` for exact model structure, auth patterns, and sync mechanisms before implementation.

---

### Task 1: Composite Key Ownership Verification

**Concept:** All queries must filter by `(workspace_id, user_id, resource_id)` to prevent cross-tenant data access.

- [ ] **Step 1: Audit current queryset filtering**

Find all Django views/viewsets and check which ones filter by user_id.

- [ ] **Step 2: Create ownership mixin**

```python
class OwnershipFilterMixin:
    """Filter querysets by authenticated user ownership."""

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(user=self.request.user)
```

- [ ] **Step 3: Apply mixin to all viewsets**

- [ ] **Step 4: Write tests for cross-tenant isolation**

Verify that User A cannot access User B's data.

- [ ] **Step 5: Commit**

---

### Task 2: Deferred Persistence

**Concept:** Wait for external service confirmation before persisting financial records.

- [ ] **Step 1: Identify external data flows**

Find where data from external APIs (bank feeds, import files) is persisted.

- [ ] **Step 2: Implement two-phase write**

Stage records as "pending" → confirm → promote to "confirmed".

- [ ] **Step 3: Add cleanup for stale pending records**

- [ ] **Step 4: Commit**

---

### Task 3: Dead-Letter Queue for Failed Syncs

**Concept:** When data sync fails, queue for retry instead of silently dropping.

- [ ] **Step 1: Audit current sync failure handling**

- [ ] **Step 2: Create SyncFailure model**

```python
class SyncFailure(models.Model):
    source = models.CharField(max_length=100)
    payload = models.JSONField()
    error = models.TextField()
    attempt_count = models.IntegerField(default=1)
    next_retry = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
```

- [ ] **Step 3: Implement retry management command**

`python manage.py retry_failed_syncs` — processes retryable failures with exponential backoff.

- [ ] **Step 4: Add admin dashboard for failed syncs**

- [ ] **Step 5: Commit**
