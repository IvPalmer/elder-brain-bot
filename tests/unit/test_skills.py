"""Tests for markdown skill templates."""

import pytest
from pathlib import Path
from src.bot.features.skills import SkillLoader, Skill


@pytest.fixture
def skills_dir(tmp_path):
    (tmp_path / "daily_report.md").write_text(
        "---\n"
        "name: daily_report\n"
        "description: Generate a daily health report\n"
        "trigger: /daily_report\n"
        "---\n\n"
        "Analyze the current state of the project and generate a daily report.\n"
        "Include: test status, recent commits, open issues.\n"
    )
    (tmp_path / "trade_analysis.md").write_text(
        "---\n"
        "name: trade_analysis\n"
        "description: Analyze recent trading performance\n"
        "trigger: /trade_analysis\n"
        "---\n\n"
        "Review the last 24h of trading activity.\n"
        "Report: P&L, win rate, notable trades.\n"
    )
    return tmp_path


def test_load_skills(skills_dir):
    loader = SkillLoader(skills_dir)
    skills = loader.load_all()
    assert len(skills) == 2
    names = {s.name for s in skills}
    assert "daily_report" in names
    assert "trade_analysis" in names


def test_get_skill_by_name(skills_dir):
    loader = SkillLoader(skills_dir)
    loader.load_all()
    skill = loader.get("daily_report")
    assert skill is not None
    assert "daily" in skill.description.lower()


def test_skill_to_prompt(skills_dir):
    loader = SkillLoader(skills_dir)
    loader.load_all()
    skill = loader.get("daily_report")
    prompt = skill.to_prompt()
    assert "Analyze" in prompt
    assert "test status" in prompt


def test_missing_skill(skills_dir):
    loader = SkillLoader(skills_dir)
    loader.load_all()
    assert loader.get("nonexistent") is None
