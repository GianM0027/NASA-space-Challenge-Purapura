<!-- ABOUTME: Entry point of the LunarNav repo: what it is, where the rules are, how to set up and run -->
<!-- ABOUTME: Owner: Gian; run instructions grow as the API and frontend land -->

# LunarNav (team Purapura, NASA Space Apps 2026)

Lunar landing site navigator for the challenge
[Lunar Landing Site Navigator](https://www.spaceappschallenge.org/2026/challenges/lunar-landing-site-navigator/?tab=details):
Sun and Earth visibility against the real terrain horizon, power and direct-to-Earth
communication windows, AI-assisted site search and mission robustness analysis, anywhere on the Moon.

## Read first

1. [`MISSION.md`](MISSION.md): goal, roles, who writes which file, git flow (frozen)
2. [`docs/decisions.md`](docs/decisions.md): decisions log (append-only)
3. [`docs/spec.md`](docs/spec.md): requirements, priorities, owners, API
4. [`docs/tasks/`](docs/tasks/): what each of us is doing
5. [`CLAUDE.md`](CLAUDE.md) and [`.claude/skills/`](.claude/skills/): rules for our Claude Code sessions

## Setup

Requirements: [uv](https://docs.astral.sh/uv/) (Python is installed by uv from `.python-version`),
Git, and Node.js LTS for the frontend.

```bash
git clone https://github.com/GianM0027/NASA-space-Challenge-Purapura.git
cd NASA-space-Challenge-Purapura
git checkout -b <your-name>                  # gian | federico | michael
uv sync --group <your-module> --group dev    # e.g. --group terrain --group evaluation
uv run pytest                                # must be green
```

## Checks (before every commit)

```bash
uv run ruff format . && uv run ruff check . && uv run pytest
```

## Run

Two terminals, from the repo root:

```bash
uv sync --all-groups
uv run uvicorn lunarnav.api.main:app --reload --port 8000
```

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

Open http://localhost:5173 (the dev server proxies `/api` to the backend).
API docs: http://localhost:8000/docs. Until the engine modules are merged, the API serves the
synthetic payloads in `data/examples/` (spec IF-2).
