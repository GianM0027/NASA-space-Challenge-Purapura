<!-- ABOUTME: Append-only log of every team decision; newer rows supersede older ones (MISSION.md section 4) -->
<!-- ABOUTME: Everyone may append rows at the end; nobody edits or deletes existing rows -->

# Decisions

Rules: append at the end, next free number, never edit existing rows. To reverse a decision,
add a row "Supersedes D<n> (<short reminder>)". Changes to `MISSION.md` rules need a row approved
by Gian **and** Michael.

| # | Date | Decision | Choice | Why | By |
|---|------|----------|--------|-----|----|
| D1 | 2026-11-14 | Coverage | Whole Moon, not only the south pole | Same computation everywhere (ephemerides plus horizon mask); polar contrast with Apollo sites is a strong story | team |
| D2 | 2026-11-14 | Target users | Mission-planning experts first, interface still intuitive | Sharper value for Impact and Validity; no separate public mode | team |
| D3 | 2026-11-14 | Ephemerides | For arbitrary dates; Michael owns and picks the method (Horizons API or offline) | Horizons covers any date; cache keeps the demo offline-capable | team |
| D4 | 2026-11-14 | Terrain horizon | Computed by us from LOLA DEMs (no ready-made horizon masks exist for the whole Moon) | PGDA publishes only polar averages, not masks | team |
| D5 | 2026-11-14 | AI role | LLM translates requests into GUI parameters with short rationale, retrieves from a limited site catalog; a deterministic engine computes every number | Validity: no hallucinated lunar data; future RAG out of scope | team |
| D6 | 2026-11-14 | Trade-off method | AHP as in Governale et al. 2021 (pairwise weights, principal eigenvector, consistency ratio <= 10%, Triantaphyllou sensitivity) | Established method, code already available | team |
| D7 | 2026-11-14 | Demo priorities | (a) AI request to ranked sites, (b) live change of site/date, (c) AHP trade-off | Creativity first, then core challenge ask | team |
| D8 | 2026-11-14 | Sky-from-site panel | Optional plug-in module (P2), addable late without breaking anything | Nice visual, not on the critical path | team |
| D9 | 2026-11-14 | Stack | Backend Python 3.12 + FastAPI with uv; frontend React + Vite + TypeScript + OpenLayers | One language for science and AI; OpenLayers handles non-Earth and polar projections; TS catches API mismatches | Gian |
| D10 | 2026-11-14 | Basemap | NASA Moon Trek WMTS tiles | Space agency open data (Relevance), nothing to download | Gian |
| D11 | 2026-11-14 | Catalog storage | JSON file (`data/catalog/sites.json`), user sites in `data/user/sites.json` | No database needed for a demo | team |
| D12 | 2026-11-14 | AHP trade-off | Separate popup, independent of the AI; implementation chosen by its owner; owner open | Keeps the AI path simple | team |
| D13 | 2026-11-14 | Module owners | As in `MISSION.md` section 4: Gian (contracts, AI, mission analysis, API, frontend), Federico (terrain, evaluation), Michael (ephemeris, catalog, domain content) | One writer per folder avoids conflicts | team |
| D14 | 2026-11-14 | Mission analysis owner | Gian; its results are also presented by the AI | Tight coupling with the AI module | team |
| D15 | 2026-11-14 | Python environment | One `pyproject.toml`, one dependency group per module, Python pinned in `.python-version`, `uv.lock` committed | Each member installs only what they need, same versions for all | team |
| D16 | 2026-11-14 | Data in git | Light data committed; heavy data (DEMs) downloaded by scripts into git-ignored `data/raw/` | Repo stays small, setup reproducible | team |
| D17 | 2026-11-14 | Branches | One branch per person (`gian`, `federico`, `michael`), PRs to `main` merged by Gian or Federico | Simple and enough for 3 people | team |
| D18 | 2026-11-14 | LLM provider | Swappable component: Claude Code CLI headless (Pro plan) during development, Anthropic API available as fallback; model chosen by Gian | Pro plan limits are shared with coding sessions | Gian |
| D19 | 2026-11-14 | Pitch | Prepared together on the second day; not part of the first push | Focus on the product first | team |
| D20 | 2026-11-14 | Visibility definition | Body center above the interpolated horizon mask; run durations n x step; event = first sample in the new state | One definition for engine, AI and UI | Gian |
| D21 | 2026-11-14 | Module wiring | Each module exposes a factory (`build_catalog`, `build_ephemeris_provider`, `build_terrain_provider`, `build_evaluator(ephemeris, terrain)`, `build_mission_analyzer(evaluator)`) from its package `__init__`; the API picks it up automatically, placeholder otherwise; status at `GET /api/modules` (spec IF-5) | Every owner sees their module in the GUI from their own branch, no edits to Gian's files | Gian |
| D22 | 2026-11-14 | Main view | Supersedes the OpenLayers part of D9 (stack): a 3D Moon globe (three.js) textured with the NASA LRO WAC mosaic and lit by the real Sun direction at the selected date, with the Earth direction shown; no flat map like Moon Trek. A 2D polar inset is optional (P2) | Creativity and Presentation: the day/night terminator answers the challenge question visually; poles are undistorted | Gian |
| D23 | 2026-11-14 | Golden rule: announce cross-member impact | Whenever a change is added (feature, contract, convention, endpoint, dependency), the Claude that makes it tells its member, in the same report, whether another member must change something in their approach or outputs, naming the member and the change; "nobody needs to change anything" is stated explicitly too. The member forwards it | Three people work in parallel; a silent change costs hours | Gian (pending Michael's OK, as MISSION.md requires for team rules) |
| D24 | 2026-11-14 | Ephemeris method (resolves D3) | JPL Horizons API (`CENTER=coord@301`, geodetic site, `QUANTITIES=4`, airless apparent az/el, UTC) + disk cache (EPH-2); offline Skyfield/SPICE only as fallback if Horizons is unavailable | C2 check: works for any lunar site in the Moon ME frame (same as LOLA); 60 days at 10 min = 8,641 rows in about 3 s; hard cap 90,000 rows per request (split longer windows); no documented rate limit, so requests go one at a time; apparent vs geometric difference is well under 1 arcmin, negligible next to the 0.53 deg solar disk | Michael |
