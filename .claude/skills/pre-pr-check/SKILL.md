---
name: pre-pr-check
description: "Fast self-review before every commit and PR in the LunarNav hackathon repo: run format, lint and tests, check ownership of touched files, contracts untouched, no secrets or heavy data, English only, task file updated. Use before committing, before opening a PR, and when reviewing a teammate's PR before merging into main."
---

<!-- ABOUTME: Pre-commit and pre-PR self-review checklist for the hackathon repo -->
<!-- ABOUTME: Lean replacement for the team's multi-agent code review and quality gates, runs in minutes -->

# Pre-PR Check

## 1. Automated checks (must be green)

```bash
uv run ruff format .                 # apply formatting
uv run ruff check . --fix            # then fix what remains by hand
uv run pytest                        # default suite (slow tests excluded)
```

Frontend changes (Gian only): `npm run build` and `npm run lint` inside `frontend/`.

## 2. Ownership and scope

```bash
git diff --name-only origin/main...HEAD
git diff --name-only --cached
```

- Every path belongs to the member (`MISSION.md` section 4). Anything else: unstage it and tell the member.
- `src/lunarnav/contracts/` and `data/examples/` untouched unless the member is Gian.
- No frozen file touched (`MISSION.md`, `CLAUDE.md`, `.claude/skills/`).
- `docs/decisions.md`: only new rows at the end.

## 3. Content checks

- [ ] No secrets: `git diff --cached | grep -iE "api[_-]?key|secret|token|sk-"` returns nothing real
- [ ] No heavy or generated data staged (`data/raw/`, `data/cache/`, files > 5 MB)
- [ ] English only in code, comments, docs and the commit message
- [ ] Numeric code has known-answer tests; constants have a source comment
- [ ] Public functions use contract models at their boundary and have docstrings with units
- [ ] No leftover debug prints, commented-out blocks or TODOs without a line in the task file

## 4. Severity (what blocks)

| Blocks the commit | Does not block (write it under `## Next` in the task file) |
|-------------------|-------------------------------------------------------------|
| failing tests or lint, broken import | style nits, missing docstring on a private helper |
| contract violated or changed locally | suboptimal but correct code |
| file outside ownership | missing slow test |
| secret or heavy data staged | |
| a number computed without any test | |

## 5. Reviewing a teammate's PR (Gian, Federico)

Run sections 1-3 on the PR branch (`git fetch origin && git checkout <branch>`), then check that
the PR description says how it was verified. Merge only when the blocking column is empty, then
tell the team to merge `main` into their branches.
