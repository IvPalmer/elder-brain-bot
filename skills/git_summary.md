---
name: git_summary
description: Summarize recent git activity across all projects
trigger: /git
---

Summarize recent git activity across key projects:

For each directory, run `git log --oneline -5 --since="3 days ago"`:
- ~/Work/Dev/claude-assistant
- ~/Work/Dev/master-trader
- ~/Work/Dev/vault
- ~/Work/Dev/mcp-servers/ableton-mcp-ultimate

Format as a concise summary grouped by project, showing what changed and when.
Skip projects with no recent commits.
