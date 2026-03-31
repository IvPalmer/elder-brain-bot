"""Markdown-based skill templates for configurable automation.

Inspired by Claude Code's skills/ system which defines specialized
workflows as markdown files with frontmatter.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import structlog

logger = structlog.get_logger()

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


@dataclass
class Skill:
    """A skill template loaded from a markdown file."""

    name: str
    description: str
    trigger: str
    content: str
    file_path: Path

    def to_prompt(self) -> str:
        """Convert skill content to a Claude prompt."""
        return self.content.strip()


class SkillLoader:
    """Loads skill templates from a directory of markdown files."""

    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = skills_dir
        self._skills: Dict[str, Skill] = {}

    def load_all(self) -> List[Skill]:
        """Load all skill files from the directory."""
        self._skills.clear()

        if not self.skills_dir.exists():
            logger.warning("Skills directory not found", path=str(self.skills_dir))
            return []

        for path in sorted(self.skills_dir.glob("*.md")):
            skill = self._parse_file(path)
            if skill:
                self._skills[skill.name] = skill

        logger.info("Skills loaded", count=len(self._skills))
        return list(self._skills.values())

    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(name)

    def _parse_file(self, path: Path) -> Optional[Skill]:
        """Parse a skill markdown file."""
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

            return Skill(
                name=meta.get("name", path.stem),
                description=meta.get("description", ""),
                trigger=meta.get("trigger", f"/{path.stem}"),
                content=content,
                file_path=path,
            )
        except Exception:
            logger.exception("Failed to parse skill file", path=str(path))
            return None
