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

One-time data download (LOLA elevation models, about 650 MB, into the git-ignored `data/raw/`).
Without it the app still runs, with placeholder terrain:

```bash
uv run python scripts/terrain_download_dem.py
```

Before a demo, warm the caches so no site selection waits (needs `uv sync --all-groups` first):
horizon masks of every catalog site, then Sun and Earth ephemerides for the demo window (needs
network; align the GUI start date to the warm-up start).

```bash
uv run python scripts/terrain_warm_cache.py
uv run python scripts/ephemeris_warm_cache.py --start 2026-12-01 --days 60
```

Backend, from the repo root:

```bash
uv sync --all-groups
uv run uvicorn lunarnav.api.main:app --reload --port 8000
```

Frontend, in a second terminal (run npm from inside `frontend/`: `npm --prefix` fails on Windows
with some npm versions):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 (the dev server proxies `/api` to the backend).

### AI provider

The AI box uses the server's LLM, chosen by `LUNARNAV_LLM_PROVIDER` (see `.env.example`): `cli`
(default: the Claude Code CLI with your logged-in plan), `api` (Anthropic API with the server's
`ANTHROPIC_API_KEY`) or `none`. Any visitor can also add their own Anthropic API key with the
**API key** button in the AI box: it stays in their browser and is sent only with AI requests,
which the server passes to Anthropic without storing it (decision D43). For a public deployment
use `LUNARNAV_LLM_PROVIDER=none`, so visitors never spend your plan; without a key the rest of the
app works and the AI texts fall back to deterministic sentences.

The API limits requests per client and minute (decision D44; `LUNARNAV_RATE_LIMITS` in
`.env.example`): generous for a person using the GUI, HTTP 429 with `Retry-After` beyond. Behind a
reverse proxy run uvicorn with `--proxy-headers` so each visitor is counted by their own address.

### Accounts and site proposals

Accounts are optional (decision D45). A visitor's first saved site starts a guest session: their
sites are private and last until the browser is closed. Creating an account keeps them; logging in
from another browser brings them along. Registered users can **propose** one of their sites for the
shared catalog; the usernames in `LUNARNAV_ADMIN_USERS` review proposals in the Account panel, and
approved sites appear in the catalog for everyone. Data lives in one SQLite file under
`LUNARNAV_STATE_DIR` (default `data/state/`, git-ignored); passwords are hashed with scrypt.

Admins also see **Site version** in the Account panel (decision D46): the live commit, the latest
`main` on GitHub with what changed, and an **Update the site** button. The app only drops a request
file in `LUNARNAV_CONTROL_DIR`; a service of the server's owner runs the deploy (tests, maintenance
page, rollback on failure) and writes `status.json` there, which the panel polls.
API docs: http://localhost:8000/docs. The header badges show which modules are live; a module
that is missing or fails falls back to a labelled placeholder (spec IF-5), and
http://localhost:8000/api/modules gives the reason.
