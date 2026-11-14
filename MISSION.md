<!-- ABOUTME: Frozen mission statement of team Purapura: goal, roles, who writes which file, git flow, change procedure -->
<!-- ABOUTME: Written once in the bootstrap commit and never edited again; changes go through docs/decisions.md -->

# MISSION: LunarNav (team Purapura, NASA Space Apps 2026)

> **This file is frozen.** Nobody edits it after the bootstrap commit, humans and Claude alike.
> If a rule here proves wrong, record a superseding decision in `docs/decisions.md`
> approved by Gian **and** Michael; the newest decision wins over this file.

## 1. Goal

Challenge: [Lunar Landing Site Navigator](https://www.spaceappschallenge.org/2026/challenges/lunar-landing-site-navigator/?tab=details).
We have **24 hours** to ship a **working local web app** for **mission-planning experts**
(still intuitive) that evaluates **landing site + date** combinations **anywhere on the Moon**:

- Sun and Earth position relative to the **real terrain horizon** (ephemerides + LOLA horizon masks)
- power metrics (illumination fraction, solar elevation, longest light/dark periods, time to sunset)
- direct-to-Earth communication metrics (Earth visibility, time to Earthset)
- an **AI assistant** that turns a natural-language mission request into the app's parameters
  and ranks sites from our catalog; **the AI never invents numbers**, every number comes from the engine
- **mission analysis**: how robust a choice is to launch-date slips and landing dispersion
- side-by-side comparison of sites

We play to win. Judging criteria: Impact, Creativity, Validity, Relevance (use of space agency
open data), Presentation. Every feature should serve at least one of them.

## 2. Team and roles

| Person | Role | Owns |
|--------|------|------|
| **Gian** | Technical lead (code orchestration), AI | contracts, AI, mission analysis, API, frontend, `docs/spec.md` |
| **Federico** | Technical co-lead, computation engine | terrain (horizon masks, slopes), evaluation (metrics) |
| **Michael** | Project lead (high level), aerospace domain | ephemerides, site catalog, domain knowledge for the AI |

Gian or Federico merge into `main`. Michael has the last word on domain correctness
(what a metric means, what a mission needs); Gian on technical structure.

## 3. Sources of truth (read in this order)

1. `MISSION.md` (this file): rules of the game
2. `docs/decisions.md`: every decision taken, append-only; newer rows supersede older ones
3. `docs/spec.md`: requirements with priority (P0/P1/P2) and owner
4. `src/lunarnav/contracts/`: the data models and interfaces between modules (code is the contract)
5. `docs/tasks/<name>.md`: what each person is doing now

## 4. Who writes what

**Rule zero: you write only where the table says you may.** Need a change elsewhere?
Ask the owner (message, or a line in your own task file under `## Requests`).

| Path | Writer(s) | Notes |
|------|-----------|-------|
| `MISSION.md`, `CLAUDE.md`, `.claude/skills/**` | nobody | frozen after bootstrap |
| `docs/decisions.md` | everyone | **append-only**: add rows at the end, never edit or delete rows |
| `docs/spec.md` | Gian | others propose changes via `## Requests` in their task file |
| `docs/tasks/gian.md` | Gian | |
| `docs/tasks/federico.md` | Federico | |
| `docs/tasks/michael.md` | Michael | |
| `src/lunarnav/contracts/**`, `data/examples/**` | Gian | interface changes: see section 6 |
| `src/lunarnav/ephemeris/**` | Michael | |
| `src/lunarnav/catalog/**`, `data/catalog/**` | Michael | `data/user/` is written by the app at runtime, not by hand |
| `docs/domain/**` | Michael | domain knowledge for the AI (mission archetypes, sourced values); read by `ai/` |
| `src/lunarnav/terrain/**`, `src/lunarnav/evaluation/**` | Federico | |
| `src/lunarnav/mission_analysis/**` | Gian | |
| `src/lunarnav/ai/**` | Gian | domain content (mission archetypes, sourced values) supplied by Michael |
| `src/lunarnav/api/**`, `frontend/**` | Gian | the API is the composition root: it wires the modules together |
| `src/lunarnav/tradeoff/**` | unassigned | claimed by a row in `docs/decisions.md` |
| `tests/<module>/**` | owner of `<module>` | `tests/test_contracts.py`: Gian |
| `scripts/<module>_*.py` | owner of `<module>` | e.g. `scripts/terrain_download_dem.py` |
| `pyproject.toml` | everyone, **only your own dependency group** | shared sections (`[project]`, tools): Gian |
| `uv.lock` | regenerated, never hand-edited | on conflict: take either side, then run `uv lock` |
| `README.md`, `.gitignore`, `.python-version`, `.env.example` | Gian | |

## 5. Git flow

- One long-lived branch per person: `gian`, `federico`, `michael`. Never commit on `main`.
- Start of every session: `git fetch origin && git merge origin/main` into your branch.
- Small commits, conventional format, **English only**: `feat(terrain): add horizon mask from DEM`.
- When a piece works: run the checks (section 7), push your branch, open a PR to `main`.
  Gian or Federico review and merge. Merge `main` back into your branch right after.
- Never force-push to `main`, never rewrite someone else's branch.
- Never commit secrets (`.env`, API keys) or heavy data (`data/raw/`, `data/cache/`).

## 6. Changing an interface (contracts)

Contracts let three people (and three Claudes) work in parallel without waiting for each other.

1. Code against the contracts as they are. Missing a field? Do **not** add it in your module.
2. Ask Gian, stating the field, its type, its unit and why.
3. Gian changes `src/lunarnav/contracts/`, updates `data/examples/`, adds a row to `docs/decisions.md`,
   merges to `main` and tells everyone to merge `main`.
4. Additive changes (new optional field) are cheap. Renames and removals need everyone's OK.

Until a real module exists, consumers use the example payloads in `data/examples/`
(valid, contract-checked sample outputs) so nobody blocks on anybody.

## 7. Definition of done for any PR

- `uv run ruff format --check . && uv run ruff check . && uv run pytest` is green
- the change stays inside the files you own (section 4)
- new logic that computes numbers (geometry, metrics, ranking) has at least one test with a known answer
- contracts respected: your outputs validate against the Pydantic models
- `docs/tasks/<you>.md` updated (done, next, blockers)

## 8. Data

- Light data (catalog JSON, small examples, small precomputed tables) is committed under `data/`.
- Heavy data (DEMs, rasters) is **never** committed: each owner writes a download script in
  `scripts/` that fills `data/raw/`; caches go to `data/cache/`. Both are git-ignored.
- Every dataset used is cited (name, provider, URL) in `docs/spec.md` (Data sources) and in the app.

## 9. Environment

- One Python version for everyone, pinned in `.python-version`; `uv` only (no pip, conda, poetry).
- One `pyproject.toml` with one **dependency group per module**: install only what you need,
  e.g. `uv sync --group terrain --group dev`. Gian runs `uv sync --all-groups` for integration.
- Code, comments, commits and docs in **English**. Chat with your Claude in any language.
