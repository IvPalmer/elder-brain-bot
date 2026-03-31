"""Per-user persistent memory system.

Inspired by Claude Code's memdir/ system which stores memories as
markdown files with YAML frontmatter, indexed by MEMORY.md.
"""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

import structlog

logger = structlog.get_logger()


class MemoryType(str, Enum):
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"


@dataclass
class Memory:
    """A single memory entry."""

    name: str
    description: str
    memory_type: MemoryType
    content: str


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


class MemoryStore:
    """File-based per-user memory persistence."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def _user_dir(self, user_id: int) -> Path:
        d = self.base_dir / str(user_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _file_path(self, user_id: int, name: str) -> Path:
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        return self._user_dir(user_id) / f"{safe_name}.md"

    def save(self, user_id: int, memory: Memory) -> None:
        """Save a memory to disk."""
        path = self._file_path(user_id, memory.name)
        content = (
            f"---\n"
            f"name: {memory.name}\n"
            f"description: {memory.description}\n"
            f"type: {memory.memory_type.value}\n"
            f"---\n\n"
            f"{memory.content}\n"
        )
        path.write_text(content, encoding="utf-8")
        logger.info("Memory saved", user_id=user_id, name=memory.name)

    def load(self, user_id: int, name: str) -> Optional[Memory]:
        """Load a memory from disk."""
        path = self._file_path(user_id, name)
        if not path.exists():
            return None
        return self._parse_file(path)

    def list(self, user_id: int) -> List[Memory]:
        """List all memories for a user."""
        user_dir = self._user_dir(user_id)
        memories = []
        for path in sorted(user_dir.glob("*.md")):
            mem = self._parse_file(path)
            if mem:
                memories.append(mem)
        return memories

    def delete(self, user_id: int, name: str) -> None:
        """Delete a memory."""
        path = self._file_path(user_id, name)
        if path.exists():
            path.unlink()
            logger.info("Memory deleted", user_id=user_id, name=name)

    def build_memory_prompt(self, user_id: int) -> str:
        """Build a prompt section from all user memories."""
        memories = self.list(user_id)
        if not memories:
            return ""

        sections = []
        for mem in memories:
            sections.append(f"[{mem.memory_type.value}] {mem.name}: {mem.content}")

        return "User memories:\n" + "\n".join(f"- {s}" for s in sections)

    def _parse_file(self, path: Path) -> Optional[Memory]:
        """Parse a memory markdown file."""
        try:
            text = path.read_text(encoding="utf-8")
            match = _FRONTMATTER_RE.match(text)
            if not match:
                return None

            frontmatter = match.group(1)
            content = match.group(2).strip()

            meta = {}
            for line in frontmatter.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip()] = value.strip()

            return Memory(
                name=meta.get("name", path.stem),
                description=meta.get("description", ""),
                memory_type=MemoryType(meta.get("type", "user")),
                content=content,
            )
        except Exception:
            logger.exception("Failed to parse memory file", path=str(path))
            return None
