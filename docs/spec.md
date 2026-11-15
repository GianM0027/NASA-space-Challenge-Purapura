<!-- ABOUTME: LunarNav specification: functional and interface requirements with priority, owner, acceptance -->
<!-- ABOUTME: Owner: Gian; others propose changes under "Requests" in their task file (MISSION.md section 4) -->

# LunarNav: Specification

## 1. Overview

LunarNav is a local web app for **mission-planning experts** that answers, for any point on the
Moon and any date: *is there enough sunlight for power, and can we talk directly to Earth?*

- It computes Sun and Earth positions (ephemerides) and checks them against the **real terrain
  horizon** derived from LOLA topography, then summarizes power and communication metrics.
- An **AI assistant** translates a natural-language mission request ("a polar ISRU rover that can
  recharge at least 70% of the time") into the app's parameters, each with a one-line rationale,
  and ranks sites from a curated catalog. **The AI never produces numbers about the Moon**: those
  come only from the deterministic engine, so every figure on screen is traceable to data.
- **Mission analysis** shows how robust a choice is when the launch slips (days, weeks) and when
  the lander misses the nominal point (landing precision plus operating range).

Demo priority (decision D7, demo order): (a) AI request to ranked sites, (b) change site or date and see
the conditions update live, (c) AHP trade-off popup.

Priority levels: **P0** = the demo fails without it; **P1** = strong for judging, build after P0;
**P2** = bonus, only if time remains. Plug-in modules (P2) must not break anything when absent.

## 2. Architecture

```
frontend (React + Vite + TypeScript + three.js)            owner: Gian
   |  REST/JSON (section 5)
api (FastAPI, composition root)                             owner: Gian
   |-- ai ----------------> catalog, evaluation             owner: Gian
   |-- mission_analysis --> evaluation                      owner: Michael (D37)
   |-- evaluation --------> ephemeris, terrain              owner: Federico
   |-- terrain (LOLA DEM)                                   owner: Federico
   |-- ephemeris (JPL Horizons or offline kernels)          owner: Michael
   |-- catalog (data/catalog/sites.json + data/user/)       owner: Michael
   '-- tradeoff --------> evaluation (AHP weights)          owner: Federico (D37)
```

Modules exchange only the types in `src/lunarnav/contracts/` (models and Protocols). The API
module builds the concrete classes and injects dependencies; no module instantiates another
module's classes by itself.

## 3. Conventions (binding)

| Quantity | Convention |
|----------|-----------|
| Angles | degrees |
| Distances, heights | meters; heights above the 1737.4 km reference sphere |
| Durations | hours |
| Times | timezone-aware UTC, ISO 8601 in JSON |
| Sampling step | whole minutes, >= 1 (`TimeWindow.step_minutes` is an integer; JPL Horizons takes no fractions) |
| Coordinates | planetocentric latitude [-90, 90]; east-positive longitude [-180, 180); Moon Mean Earth / polar axis frame |
| Azimuth | from local north, clockwise, [0, 360) |
| Elevation | above the local horizontal plane; ephemeris values are geometric (no terrain) |
| Visible | body **center** above the horizon mask interpolated at its azimuth |
| Durations of runs | n consecutive samples in one state last n x step |
| Truncated run | a longest run is truncated when at least one run of that length starts at the first sample or ends at the last one: its value is a lower bound (common at the poles) |
| Joint visibility | a sample counts for `sun_and_earth_visible_fraction` when Sun and Earth are both visible (power and direct-to-Earth link together) |
| Horizon per sample | `sun_horizon_elevation_deg` / `earth_horizon_elevation_deg` hold the mask interpolated (linearly, wrapping at 360 deg) at the body azimuth: the exact threshold used for `*_visible` |
| Event time | time of the first sample in the new state after the window start |

## 4. Functional requirements

Format: **ID** (priority, owner): requirement. *Acceptance*: how we know it works.

### 4.1 Catalog (CAT)

- **CAT-1** (P0, Michael): `data/catalog/sites.json` holds at least 20 historical, current and planned
  landing sites across the whole Moon (Apollo, Luna, Surveyor, Chang'e, Chandrayaan, SLIM, CLPS,
  Artemis candidate regions), each with coordinates and at least one source.
  *Acceptance*: the file validates as `list[Site]`; every non-user site has a source.
- **CAT-2** (P0, Michael): a `SiteCatalog` implementation that loads curated sites and user sites
  (`data/user/sites.json`, created at runtime) and adds new user sites.
  *Acceptance*: tests for list, get, add, duplicate id rejected, user file round trip.
- **CAT-3** (P1, Michael): each site has a one-to-two sentence description usable by the AI retrieval
  (what the mission did or aims to do, terrain notes).

### 4.2 Ephemerides (EPH)

- **EPH-1** (P0, Michael): an `EphemerisProvider` returning topocentric Sun and Earth azimuth and
  geometric elevation for any lunar point and any `TimeWindow`: any length (landing date plus
  mission duration; long windows are split into several requests), step in whole minutes.
  Acceptance case for speed: 60 days at a 10 minute step.
  *Acceptance*: for one site and time, values agree with JPL Horizons within a tolerance Michael
  states and justifies; a test with a recorded Horizons response.
- **EPH-2** (P0, Michael): results are cached on disk (`data/cache/ephemeris/`) so the demo works
  offline for the catalog sites over the demo window once warmed up.
  *Acceptance*: second call for the same inputs does no network request.
- **EPH-3** (P1, Michael): a warm-up script `scripts/ephemeris_warm_cache.py` that fills the cache for
  all catalog sites over a configurable window.

### 4.3 Terrain (TER)

- **TER-1** (P0, Federico): a `TerrainProvider.horizon_mask` computing the terrain horizon elevation for
  at least 360 azimuths (1 degree step) from a LOLA DEM, for any point on the Moon, including the
  curvature of the lunar sphere.
  *Acceptance*: known-answer tests (flat sphere gives the curvature-only horizon; a synthetic ridge
  of known height and distance gives the expected elevation angle).
- **TER-2** (P0, Federico): `TerrainProvider.terrain_stats` with center elevation, mean and maximum slope
  over a disk of given radius.
  *Acceptance*: test on a synthetic inclined plane of known slope.
- **TER-3** (P0, Federico): `scripts/terrain_download_dem.py` downloads the chosen DEM(s) into
  `data/raw/` and documents product, resolution and URL.
- **TER-4** (P1, Federico): higher-resolution polar DEMs used automatically at high latitudes,
  where terrain shadows dominate.
- **TER-5** (P1, Federico): horizon masks cached per site in `data/cache/terrain/`.

### 4.4 Evaluation (EVA)

- **EVA-1** (P0, Federico): an `Evaluator` that combines `EphemerisSeries` and `HorizonMask` into
  per-sample visibility of Sun and Earth and `VisibilityMetrics`, following section 3.
  *Acceptance*: known-answer tests on synthetic series (fractions, longest runs, truncation, event times);
  the reference definitions and tests are `lunarnav.api.placeholder_metrics` (decision D29, new contract fields).
- **EVA-2** (P0, Federico): `Evaluation.terrain` computed over the disk of radius
  `landing_precision_m + operating_range_m`.
- **EVA-3** (P1, Federico): one site over one lunar day (about 30 days at a 1 hour step) evaluates in
  under 2 seconds with warm caches (target, to be measured).

### 4.5 Mission analysis (MA)

- **MA-1** (P1, Michael, D37): date-slip sweep: evaluate the window shifted by a list of offsets (default
  +1, +3, +7, +14 days) and report the change of every metric.
- **MA-2** (P1, Michael, D37): dispersion: evaluate sample points inside the operations-area disk and report
  worst case and spread.
- **MA-3** (P1, Michael, D37): `RobustnessReport.summary` in plain language; the AI can present it.

### 4.6 AI assistant (AI)

- **AI-1** (P0, Gian): natural-language request to `MissionRequirements` (validated JSON), each set
  field with a one-line rationale in `rationale`.
  *Acceptance*: 5 scripted requests produce valid requirements; invalid LLM output is retried or
  reported, never passed on unvalidated.
- **AI-2** (P0, Gian): deterministic ranking of catalog sites against the requirements using
  evaluation metrics (simple retrieval: filter plus score), returned as `SiteRanking`.
  *Acceptance*: tests with fixed metrics give the expected order.
- **AI-3** (P0, Gian): the LLM never outputs lunar numbers of its own; explanations cite only values
  from `SiteRanking`/`RobustnessReport`.
- **AI-4** (P0, Gian): the LLM provider is a swappable component (`LlmClient`), selected by
  `LUNARNAV_LLM_PROVIDER`: `cli` (default, implemented) runs the Claude Code CLI headless with
  every context source off (empty folder, no settings, skills, MCP or tools), so the model sees
  only the task prompt; `api` (Anthropic API) is the planned alternative if CLI latency is too
  high for the demo.
- **AI-5** (P1, Gian with content by Michael): mission archetypes (e.g. robotic ISRU, short human
  stay, long-duration outpost, communication relay) as domain knowledge with **sourced** typical
  values, used to suggest requirements.
- **AI-6** (P1, Gian): the AI presents mission-analysis results on request.
- **AI-7** (P0, Gian with content by Michael): a region named in words ("near the south pole",
  "equatorial", "far side") sets the matching search scope (latitude and longitude bounds).
  The bounds come from a table in `docs/domain/` (Michael), each with a cited source; the LLM only
  picks the region name, code applies the bounds.
  *Acceptance*: "two-week robotic lander near the south pole" ranks only sites inside the
  south-polar bounds.

### 4.7 User interface (UI)

- **UI-1** (P0, Gian): 3D Moon globe (decision D22, main view) textured with the NASA LRO WAC mosaic
  from Moon Trek, lit by the Sun direction at the selected date (day/night terminator), with the
  Earth direction shown; catalog markers; click on the surface to pick custom coordinates; quick
  views of the near side and both poles.
- **UI-2** (P0, Gian): site panel: date/time and window picker, metrics, Sun and Earth elevation
  timeline against the horizon, time to next sunset and Earthset prominently shown.
- **UI-3** (P0, Federico, D37): side-by-side comparison of 2 to 4 site-date scenarios, picked
  from the catalog, "My locations" or the AI ranking without re-entering them one at a time; it
  opens the trade-off of section 4.8.
- **UI-4** (P0, Gian): AI box: request text, extracted parameters as editable fields with rationale,
  ranked site list; editing a parameter re-runs the deterministic ranking without the LLM.
- **UI-5** (P1, Gian): mission analysis view (date-slip chart, dispersion summary).
- **UI-6** (P1, Gian): data sources and attribution panel (section 7).
- **UI-7** (P2, unassigned): "sky from the site" panel: horizon profile with Sun and Earth tracks over
  the window (plug-in; data already in `Evaluation.horizon` and the series).
- **UI-8**: merged into UI-3 and section 4.8 (decision D37).
- **UI-10** (P2, unassigned): 2D high-resolution polar inset next to the globe.
- **UI-9** (P2, unassigned): PGDA polar layers (average illumination, Earth visibility, permanent shadow).
- **UI-11** (P1, Gian): time wheel: a small scrollable timeline on the globe that moves the
  displayed instant forward or back step by step, with a play mode that advances it
  automatically; globe lighting and the site panel follow. Requests are throttled so scrolling
  never queues more than one `GET /api/sky` at a time.
- **UI-12** (P1, Gian): final visual pass over the whole app: remove redundant elements,
  consistent layout and typography, readable at a projector resolution.

### 4.8 Trade-off (TO)

Method: AHP as in Governale et al. 2021 (decision D6, trade-off method). Owner: Federico (D37);
the AI comment is Gian's.

- **TO-1** (P1, Federico): every significant quantitative parameter of a compared scenario is an
  independent figure of merit (FoM) with a direction (higher or lower is better) and a unit:
  at least illumination fraction, longest continuous light, longest continuous dark, Earth
  visibility fraction, longest Earth outage, landing slope maximum and reachable fraction when
  the area has an operating range. Values come from `Evaluation` only.
- **TO-2** (P1, Federico): FoM weights have defaults the user can change. Defaults come from an
  AHP pairwise comparison (weights by the row geometric mean, consistency ratio <= 10 % from
  lambda max of A.w; decision D39) whose judgments are taken from Governale et al. 2021 where
  their criteria match ours, and are equal otherwise (none match: all defaults are 1); every
  default judgment cites its source. The user edits weights directly or through the
  pairwise comparisons; weights are normalized to sum to 1.
- **TO-3** (P1, Federico): the user can add a FoM of their own: name, unit, direction, weight,
  and a value for every compared scenario; it enters the trade-off like the computed ones and
  is marked as user-supplied everywhere it appears.
- **TO-4** (P1, Federico): the trade-off score of each scenario is computed by a stated method
  (normalization across the compared scenarios plus weighted sum, with its source in the code),
  shown in the comparison view, and exported to a file (Excel or PDF, chosen by the owner) with
  scenarios, FoM values and units, weights, normalized values, total scores, ranking, data
  sources, and the AI comment.
- **TO-5** (P1, Gian): a short AI comment on the trade-off result, citing only numbers present
  in the trade-off table (number check as in AI-3, deterministic sentence as fallback).
- **TO-6** (P2, Federico): sensitivity of the ranking to the weights (Triantaphyllou, as in D6).
  *Acceptance (TO-1 to TO-4)*: a known-answer test with 3 scenarios and fixed weights gives the
  expected scores and order; an exported file reopens with the same numbers.

## 5. Interface requirements

- **IF-1**: all inter-module data uses the Pydantic models in `lunarnav.contracts`; modules
  implement the Protocols in `lunarnav.contracts.ports`.
- **IF-2**: until a module exists, consumers develop against `data/examples/*.json`, regenerated by
  `scripts/contracts_make_examples.py` after any contract change.
- **IF-3**: contract changes follow `MISSION.md` section 6 and get a row in `docs/decisions.md`.
- **IF-5**: automatic wiring. Each module exposes a factory from its package `__init__`; the API
  uses it when present and a labelled placeholder otherwise, so an owner sees their module in the
  GUI from their own branch without editing `lunarnav.api`. A factory receives its upstream
  dependencies as arguments. `GET /api/modules` reports each service as `real`, `example` or
  `error: <reason>` (a factory that raises falls back to the placeholder).

| Module | Factory | Returns |
|--------|---------|---------|
| `catalog` | `build_catalog()` | `SiteCatalog` |
| `ephemeris` | `build_ephemeris_provider()` | `EphemerisProvider` |
| `terrain` | `build_terrain_provider()` | `TerrainProvider` |
| `evaluation` | `build_evaluator(ephemeris, terrain)` | `Evaluator` |
| `mission_analysis` | `build_mission_analyzer(evaluator)` | `MissionAnalyzer` |
| `ai` | `build_ranker(catalog, evaluator)` | `Ranker` |
| `ai` | `build_assistant(ranker, catalog)` | `Assistant` |

  Placeholders: a toy ephemeris (far Sun and Earth, no libration, no tilt, arbitrary phase) and a
  flat horizon. They only draw plausible curves; never validate against them.
- **IF-4**: REST API (owner Gian), JSON bodies are the contract models serialized by Pydantic:

| Method and path | Request body | Response |
|-----------------|--------------|----------|
| `GET /api/health` | none | `{"status": "ok"}` |
| `GET /api/modules` | none | `{"<service>": "real" or "example" or "error: ..."}` |
| `GET /api/sky?time_utc=<ISO 8601>` | none | `SkyState` (subsolar and sub-Earth points, derived from `EphemerisProvider`) |
| `GET /api/sites` | none | `list[Site]` |
| `POST /api/sites` | `Site` (origin `user`) | `Site` |
| `PATCH /api/sites/{id}` | `{"name"?: str, "description"?: str}` (at least one; `""` clears the description) | `Site` (user sites only: 403 if curated, 404 if unknown) |
| `DELETE /api/sites/{id}` | none | 204 (user sites only: 403 if curated, 404 if unknown) |
| `POST /api/evaluate` | `{"site_id": str or null, "location": GeoPoint or null, "window": TimeWindow, "area": OperationsArea}` (one of site_id/location) | `Evaluation` |
| `POST /api/compare` | `{"scenarios": [evaluate request, ...]}` (2 to 4) | `list[Evaluation]` |
| `POST /api/rank` | `MissionRequirements` | `SiteRanking` |
| `POST /api/ai/ask` | `AiRequest` (message, history, current requirements, locked fields, GUI window) | `AiAnswer` (ranking null when the AI asks back) |
| `POST /api/ai/explain` | `{"ranking": SiteRanking, "language_hint": str}` | `SiteRanking` with a checked one-sentence `rationale` per site |
| `POST /api/mission-analysis` | evaluate request plus `"shifts_days": list[float]` | `RobustnessReport` |
| `POST /api/tradeoff` | `{"scenarios": [evaluate request] (2 to 4), "settings": TradeoffSettings}` | `TradeoffResult` |
| `POST /api/tradeoff/export` | same as `/api/tradeoff` | `.xlsx` workbook (501 until the trade-off module exists) |

  Errors: HTTP 422 for invalid input (Pydantic detail, or a `ValueError` raised by a module),
  404 for unknown site id, 502 when a module fails for any other reason (Horizons, LLM, data
  files), with `detail` the UI can show. `GET /api/sky` truncates the instant to the whole minute.

## 6. Non-functional requirements

- **NF-1**: runs locally on Windows, macOS and Linux with `uv` and Node.js LTS; one command each to
  start backend and frontend, documented in `README.md`.
- **NF-2**: after data download and cache warm-up, the demo works without network except the LLM call.
- **NF-3**: Python version pinned in `.python-version`; dependencies locked in `uv.lock`.
- **NF-4**: no secrets in git; LLM configuration in `.env` (template `.env.example`).
- **NF-5**: every number shown is reproducible from the engine and its data sources.

## 7. Data sources (cite in the app)

| Data | Provider | Use | Owner |
|------|----------|-----|-------|
| JPL Horizons API, https://ssd-api.jpl.nasa.gov/doc/horizons.html | NASA JPL | Sun and Earth topocentric directions | Michael |
| LOLA gridded DEMs LDEM_64 (global, 64 px/deg, about 474 m), LDEM_80S_80M (south pole to 80 S, 80 m) and LDEM_85S_20M (south pole to 85 S, 20 m, decision D31), data set LRO-L-LOLA-4-GDR-V1.0, https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/ | NASA LRO LOLA / PDS Geosciences Node | horizon masks, slopes | Federico |
| Lunar Polar Illumination, https://pgda.gsfc.nasa.gov/products/69 (Mazarico et al. 2011, Icarus 211) | NASA GSFC PGDA | optional polar layers, sanity check | Federico |
| LRO WAC global mosaic via Moon Trek WMTS, https://trek.nasa.gov/moon/ | NASA JPL / LROC (ASU) | globe texture | Gian |
| Landing site coordinates | per-site sources in `sites.json` | catalog | Michael |

## 8. Early feasibility checks (first hours)

Each owner runs these before building on them and records the result in their task file and,
if it changes a plan, in `docs/decisions.md`.

- **C1** (Federico, DEM feasibility): which LOLA DEM(s) to use; time and memory to compute one horizon mask.
- **C2** (Michael, Horizons query): a Horizons query for a topocentric site on the Moon returns Sun and Earth
  azimuth/elevation; request limits; offline alternative if Horizons is too slow.
- **C3** (Gian, LLM JSON): the LLM via Claude Code CLI headless returns schema-valid `MissionRequirements` JSON.
- **C4** (Gian, map tiles): Moon Trek tiles load in the browser as the globe texture (done: CORS open, levels 0 to 8).

## 9. Out of scope

Public/educational mode, user accounts, deployment to a server, mobile app, atmospheric effects
(the Moon has none), relay satellites, thermal modelling, partial solar disk visibility (P2 at most).
