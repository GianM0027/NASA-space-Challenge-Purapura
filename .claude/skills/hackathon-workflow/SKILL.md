---
name: hackathon-workflow
description: "Team workflow for the LunarNav 24-hour hackathon: session start checklist, branch per person, conventional commits, PRs into main, task file updates, requesting a contract change from the contracts owner. Use at the start of every session, before committing or opening a PR, when the task needs a file the member does not own, or when a contract field is missing."
---

<!-- ABOUTME: Hackathon workflow skill: session checklist, git flow, task files, contract change requests -->
<!-- ABOUTME: Lean version of the team's source-control and plan-first rules, tuned for 24 hours and 3 parallel Claudes -->

# Hackathon Workflow

Ownership and rules live in `MISSION.md`; this skill is the how-to.

## Session start checklist

```bash
git status                                   # clean? if not, ask the member before touching anything
git branch --show-current                    # must be gian | federico | michael
git fetch origin && git merge origin/main    # pick up contracts and others' merged work
uv sync --group <module> --group dev         # only the groups the member's modules need
uv run pytest                                # baseline must be green before you change anything
```

If the baseline is red on `main` code you do not own: do not fix it; tell the member who owns it.

Then read `docs/tasks/<member>.md` and pick the highest-priority open item (P0 before P1 before P2).

## Doing a task

1. State the approach in 3-5 lines (files touched, contract types used, how you will verify).
2. Implement inside owned paths only; code against `src/lunarnav/contracts/`.
3. Until the upstream module exists, load sample inputs from `data/examples/*.json`
   through the contract models (e.g. `Evaluation.model_validate_json(...)`).
4. Verify (`pre-pr-check`), commit, update the task file.

## Commits

Format `<type>(<scope>): <subject>`, imperative, lowercase, no period, at most 72 characters, English.
Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `perf`. Scope = module name.

```bash
git add <specific files>      # never `git add -A` or `git add .`
git commit -m "feat(evaluation): compute longest continuous light period"
```

Never `--no-verify`. A hook fails: read the error, fix the cause, commit again.

## Pull requests

When a coherent piece works (not after every commit) and `pre-pr-check` is green, give the member
the commands; the member pushes:

```bash
git push -u origin <branch>
gh pr create --base main --head <branch> --title "<conventional title>" --body "<what, why, how verified>"
```

After the merge: `git fetch origin && git merge origin/main`.

Gian or Federico merge. Reviewer checks: files inside the author's ownership, checks green,
contracts unchanged (unless the PR is Gian's contract change).

## Task file (`docs/tasks/<member>.md`)

Only the member's own file. Keep these sections current, newest first, one line per item:

- `## Status`: one sentence on what works now
- `## Done`, `## Next`, `## Blockers`
- `## Requests`: what you need from another owner, prefixed with the owner's name

## Decisions (`docs/decisions.md`)

Append a row at the end for any choice another member must know (a library adopted, a unit,
a scope cut). Never edit existing rows; to reverse one, add a row that supersedes it.

## Requesting a contract change

Do not edit `src/lunarnav/contracts/`. Draft for the member to send to Gian:

```
Contract change request: <model>.<field>
Type and unit: float, degrees
Why: <which requirement needs it>
Additive (new optional field) or breaking (rename/remove/type change): additive
```

Meanwhile keep the extra value internal to your module; do not leak it through the API.

## Needing a file you do not own

Stop. Tell the member which owner to ask and what exact change is needed. Add it to `## Requests`.
