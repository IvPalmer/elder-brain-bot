"""Tests for per-user persistent memory."""

import pytest
from pathlib import Path
from src.claude.memory import MemoryStore, Memory, MemoryType


@pytest.fixture
def memory_dir(tmp_path):
    return tmp_path / "memories"


@pytest.fixture
def store(memory_dir):
    return MemoryStore(memory_dir)


def test_save_and_load(store):
    mem = Memory(
        name="user_role",
        description="User is a DJ and developer",
        memory_type=MemoryType.USER,
        content="Raphael is a Brazilian DJ and full-stack developer.",
    )
    store.save(user_id=123, memory=mem)
    loaded = store.load(user_id=123, name="user_role")
    assert loaded is not None
    assert loaded.content == mem.content
    assert loaded.memory_type == MemoryType.USER


def test_list_memories(store):
    store.save(user_id=123, memory=Memory(
        name="pref1", description="d1",
        memory_type=MemoryType.FEEDBACK, content="c1",
    ))
    store.save(user_id=123, memory=Memory(
        name="pref2", description="d2",
        memory_type=MemoryType.PROJECT, content="c2",
    ))
    memories = store.list(user_id=123)
    assert len(memories) == 2


def test_delete_memory(store):
    store.save(user_id=123, memory=Memory(
        name="temp", description="d",
        memory_type=MemoryType.USER, content="c",
    ))
    store.delete(user_id=123, name="temp")
    assert store.load(user_id=123, name="temp") is None


def test_build_prompt(store):
    store.save(user_id=123, memory=Memory(
        name="role", description="User role",
        memory_type=MemoryType.USER, content="User is a DJ.",
    ))
    prompt = store.build_memory_prompt(user_id=123)
    assert "DJ" in prompt


def test_separate_users(store):
    store.save(user_id=1, memory=Memory(
        name="m", description="d",
        memory_type=MemoryType.USER, content="user 1",
    ))
    assert store.load(user_id=2, name="m") is None
