---
name: git_summary
description: Summarize recent git activity across all projects
trigger: /git
---

Summarize recent git activity across key projects:

For each directory, run `git log --oneline -5 --since="3 days ago"`:
- ~/Dev/finance/trading/master-trader
- ~/Dev/finance/financial-control/vault
- ~/Dev/music/production/ableton-mcp

Format as a concise summary grouped by project, showing what changed and when.
Skip projects with no recent commits.
