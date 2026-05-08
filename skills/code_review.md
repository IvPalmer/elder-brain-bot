---
name: code_review
description: Review recent git changes in the current project
trigger: /review
---

Review the most recent git changes in this project:

1. Run `git diff HEAD~1` to see the latest commit's changes
2. Run `git log --oneline -5` for recent commit context
3. Analyze the changes for:
   - Potential bugs or logic errors
   - Security concerns (hardcoded secrets, injection risks)
   - Code style issues
   - Missing error handling
4. Provide a concise review with specific line references
