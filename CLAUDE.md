<!-- ABOUTME: Instructions for every team member's Claude Code in this repo: ownership, workflow, safety rails -->
<!-- ABOUTME: Frozen after the bootstrap commit; the hackathon variant of the team's engineering rules -->

# CLAUDE.md: LunarNav (24-hour hackathon)

You are one of three Claude Code instances working **in parallel** on this repo, each paired with
one team member. Speed matters, but a broken `main` or a contract mismatch costs the team more
than any feature. These rules are lean on purpose.

## Precedence

For this repo, **this file and `MISSION.md` override** any personal or global instruction about
process: no plan files, no ADRs, no multi-agent review loops, no spec phases. Personal rules about
language, tone and safety still apply.

## Start of every session

1. Ask (or infer from `git config user.name`) **which team member you work with**: Gian, Federico or Michael.
2. Read `MISSION.md`, then the tail of `docs/decisions.md`, then `docs/tasks/<member>.md`,
   then the requirements of your member in `docs/spec.md`.
3. Make sure you are on the member's branch (`gian`, `federico`, `michael`) and merge `origin/main`.
4. Run the `hackathon-workflow` skill's session checklist.

## Hard rules (never break)

- **Write only in the paths your member owns** (`MISSION.md` section 4). Reading anything is fine.
  If the task needs a change elsewhere, stop and tell your member who owns it.
- **Never edit** `MISSION.md`, `CLAUDE.md`, `.claude/skills/**`, or existing rows of `docs/decisions.md`.
- **Never change a contract locally.** Contracts live in `src/lunarnav/contracts/` (owner: Gian).
  Consume and produce exactly those models. Need a change? Draft it for your member to send to Gian.
- **Never commit on `main`**, never force-push, never push without your member's OK.
- **Never commit** secrets, `.env`, API keys, or files under `data/raw/` and `data/cache/`.
- **Never skip git hooks** or weaken a check to get green; fix the cause.
- **No invented numbers** in science code: constants (Moon radius, solar disk size, frames) come
  from a cited source written next to them in a comment.
- Commits, code, comments and docs in **English**.

## How to work (lean loop)

1. **Clarify** the task in 1-3 questions only if it is ambiguous; otherwise state your approach in
   3-5 lines and start (the member can interrupt).
2. **Contract first**: write the function signature with the contract types before the body.
3. **Test what computes numbers**: one test with a known answer per formula or metric
   (e.g. Sun at known elevation, a flat terrain gives a zero horizon). UI and glue code: smoke tests only.
4. **Run the checks** (`pre-pr-check` skill) before every commit.
5. **Commit small**, conventional format; update `docs/tasks/<member>.md` (done / next / blockers).
6. **Report** to your member in 2-4 lines: what works, how it was verified, what is next.

Stuck after 2 attempts on the same bug? Stop, explain the cause you suspect and the evidence,
and propose a different approach instead of pushing harder.

## Skills in this repo (`.claude/skills/`)

| Skill | When |
|-------|------|
| `hackathon-workflow` | start of session, branches, commits, PRs, requesting a contract change |
| `hackathon-python` | writing or changing any Python in `src/`, `tests/`, `scripts/` |
| `pre-pr-check` | before every commit and before opening a PR |

## Domain conventions (summary; the contracts are authoritative)

- Angles in **degrees**, distances in **meters**, times **UTC** (ISO 8601, timezone-aware).
- Selenographic coordinates: planetocentric latitude, **east-positive longitude in [-180, 180)**,
  Moon Mean Earth / polar axis frame, reference sphere radius 1737.4 km.
- Azimuth measured **from local north, clockwise** (east = 90°); elevation above the local
  horizontal plane of the reference sphere; terrain horizon elevation uses the same convention.
