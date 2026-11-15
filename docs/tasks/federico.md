<!-- ABOUTME: Task file of Federico: terrain (horizon masks, slopes) and evaluation (metrics) -->
<!-- ABOUTME: Only Federico (and Federico's Claude) writes here; requirement IDs refer to docs/spec.md -->

# Federico: tasks

## Status
Trade-off complete: engine, export (autofit, no cut text), and the compare/ view (UI-3), redesigned as a guided
popup opened from a dock pill. Waiting on Gian to mount it in the App dock.

## Next (in priority order)
1. Once mounted by Gian: polish the comparison view from team feedback; TO-6 sensitivity view is already in the table.
2. PDF report: register Michael's `MissionAnalysis` and Gian's `AiRanking` in `COMPONENTS` of
   `report/ReportBuilder.tsx` once their files land; check a real print to PDF.

Tips: the `Evaluator` receives an `EphemerisProvider` and a `TerrainProvider` in its constructor;
for tests write small fakes of both that return the example payloads.

## Done
- Setup: branch `federico`, `uv sync --group terrain --group evaluation --group dev`, 15 tests green.
- C1 (DEM feasibility): LDEM_64 global + LDEM_80S_80M south polar, rays to 150 km; ~0.02 s / 13 MB
  and ~0.19 s / 76 MB per mask (`scripts/terrain_c1_benchmark.py`, decision D28). Polar stereographic
  signs verified against LDEM_64 and Shackleton crater (an east-west mirror bug was caught this way).
- TER-3: `scripts/terrain_download_dem.py` fetches the D28 DEMs from PDS into `data/raw/lola/` (~650 MB);
  skips complete files, size-checked `.part` downloads; verified byte-identical re-download of LDEM_80S_80M.
- TER-1: `LolaTerrainProvider.horizon_mask` (360 azimuths, rays to 150 km, curvature included); picks the
  south polar DEM when the whole ray disk fits, else LDEM_64; ~15 ms equator, ~160 ms pole. Known-answer
  tests (bare sphere, geometric dip, 3 km ridge) plus slow real-DEM checks; both catch injected bugs.
- TER-2: `terrain_stats` (center elevation, mean/max slope over a disk at the DEM pixel baseline);
  known-answer tests on inclined planes (global and polar grids, exact pole); real: mare ~1 deg mean,
  Shackleton walls up to ~37 deg. Factory `build_terrain_provider()` exported (IF-5): API shows terrain `real`.
- EVA-1 + EVA-2: `LunarEvaluator` (visibility strictly above the mask interpolated periodically at the body
  azimuth, runs n x step, first-sample events) and terrain over landing precision + operating range;
  `build_evaluator` exported. 10 known-answer tests; 30 days at 1 h on the polar DEM: ~0.17 s via the API.
- TER-5: horizon mask cache, in-memory LRU plus JSON files in `data/cache/terrain/` (key: DEM, position,
  observer height, ray length, algorithm version). 36 catalog sites: 2.8 s computed, 2 ms again, 0.6 s from disk.
- EVA-3: with a warm ephemeris cache one 30-day 1 h evaluation takes ~16 ms (equator) and ~160 ms (pole, all
  of it the horizon mask; ~1 ms once cached). Target < 2 s met; cold Horizons calls dominate otherwise.
- D29 fields in the evaluator: horizon at the Sun/Earth azimuth per sample (the exact visibility threshold),
  joint Sun+Earth fraction, Earth mean visible elevation, truncation flags of the four longest runs.
  Agreement test against `lunarnav.api.placeholder_metrics` on 200 random series; `/api/evaluate` back to 200.
- TER-4 (decision D31): LDEM_85S_20M added; rays read 20 m within 10 km and 80 m to 150 km; slopes on the
  finest DEM. 20 m vs 80 m: median 0.7 m, same orientation (slow test). Malapert 47.4% -> 35.5% light, other
  polar sites within 1 point. Known-answer tests: relief known only to the fine or only to the coarse DEM.
- 5 m DEM analysis (not adopted): LDEM_875S_5M (1.84 GB, to 87.5 S) would cover only de Gerlache rim 2 and
  Slater plain, already converged (horizon change 40 -> 20 m: 0.13 and 0.04 deg). Malapert, the only site still
  changing with resolution (light 47.4/39.9/35.5% at 80/40/20 m), lies outside it. Observer height and site
  coordinates matter more there.
- Observer height (D30, Michael): the app provider (`from_raw_dir`, used by the factory) places the observer
  2 m above the DEM surface (Glaser et al. 2014); the constructor keeps 0 m as the geometric reference for
  the known-answer tests. Malapert 35.5% -> 37.2% light, IM-2 50.3% -> 51.9%. Duplicate D30 resolved by D31.
- D32 (contract by Gian, Michael's slope decisions): `horizon_mask(location, area)` takes the observer height
  from the area (default 2 m); `terrain_stats(location, area)` fills landing-disk slopes (finest DEM, pixel
  baseline), full-disk slopes and `reachable_fraction` (Dijkstra on slope cells with `skimage.graph`, detour
  corrected for 8-direction grid bias, corner squeezes closed; grid capped at 400 cells of radius). Crew area
  (100 m / 2 km / 20 deg) ~20 ms; rover (20 km / 15 deg) <= 0.5 s, was 4-9 s uncapped. Examples, rover reach:
  Apollo 11 100%, Apollo 15 58% (Hadley), Malapert 7%, Nobile rim 1 76%. scikit-image added to the terrain group.
- Terrain warm-up: `scripts/terrain_warm_cache.py` precomputes the horizon masks of all catalog sites at the
  D30 heights (2 m and 10 m) into `data/cache/terrain/`; 72 masks in ~5 s cold, ~1.3 s when cached; failing
  sites are reported, the run continues. Before a demo: DEM download, then this script.
- D36: landing slopes on a 100 m baseline (least-squares plane over the cells within 50 m; 80 m and 474 m
  DEMs fall back to their pixel baseline, already >= 100 m); every maximum is the 99th percentile of its disk.
  Known answers: exact plane, periodic roughness reduced by exactly 10/34, isolated spike ignored. Crew area,
  landing P99: IM-2 4.1, Nobile rim 1 8.9, Malapert 11.2, Mons Mouton plateau 20.4 deg. The horizon cache is
  unchanged: it stores masks only, which D36 does not affect, so no cache version bump.
- Trade-off core (`src/lunarnav/tradeoff/`): 6 computed FoMs from `Evaluation` plus up to 3 user FoMs;
  single-level AHP with row geometric-mean weights and Saaty CR (team decision with the reference template);
  default judgments all 1 (Governale et al. 2021 trades off micro-launchers, no matching criterion);
  per-FoM normalization summing to 1 (complement for lower-is-better); D_k sensitivity on normalized values.
  22 known-answer tests incl. the spec acceptance case (3 scenarios, fixed weights).
- Trade-off wired (D39): `LunarTradeoff` + `build_tradeoff()`; `/api/tradeoff` and `/api/tradeoff/export`
  work. Live Excel export following the team's reference template (sheets 0-7: FoM, AHP with weight mode,
  Scoring with direction, Decision, Sensitivity, Recommendation incl. AI comment, Data & sources); no array
  formulas. Tests re-evaluate the workbook formulas (`formulas` package) and match the app's weights, CR,
  scores, ranks and D_k; editing an input (FoM off) recomputes like the app. `openpyxl`, `formulas` added
  to the tradeoff group. Sensitivity follows the contract: 1 / D_k with D_k in percent.
- UI-3 view `frontend/src/compare/CompareView.tsx`: 2-4 scenarios (site, name, start) with shared mission (duration,
  step, area, panel height); FoM toggles; up to 3 user FoMs; weights equal / pairwise AHP (Saaty select per pair) /
  direct; results: scores and ranking, side-by-side table (value and share, D_k), CR check, AI comment, method;
  Excel export download. Pure logic in `model.ts` (unit-tested), calls in `tradeoffApi.ts`. Checked in the browser
  through the dev-only page `/src/compare/preview.html` (same numbers as the API; AHP CR 5.4 % shown as consistent).
- Excel export layout: column widths and wrapped row heights fitted to the content, formula text estimated
  from FoM and scenario names; test checks no text is cut (fails when the autofit is disabled).
- UI-3 redesign: guided popup (1 scenarios with full-width site select, 2 mission settings collapsed with a
  summary, 3 criteria with one-line hints and custom criteria, 4 weights as equal / pairwise sliders with a
  Saaty readout / direct), results column with ranking bars and per-criterion table. Opened from a dock pill.
- Trade-off Reset button (Gian's request): back to the initial setup, clears the result.
- Report shapes (D42): `report/types.ts` (ReportInputs, ReportBuilderProps, SectionProps<T> and the data of
  each section, rendering rules) and `report/selection.ts` (availability, print order, numbering; 3 tests).
- ReportBuilder (UI-13): dock pill "Report", popup with title, section checkboxes (disabled with "run it first"
  or "coming soon") and a live A4 preview; "Download PDF" prints only a portal copy of the same document
  (`@page` A4, 15 mm). Sections: cover with contents, site evaluation (Sun/Earth visibility strip, metrics,
  terrain), trade-off (ranking + details per criterion), sources and methods. Smoke tests via server rendering.
  Dev page `/src/report/preview.html` (real evaluation + trade-off view). Checked in the browser: ticking
  Trade-off adds the section at once. Not yet checked: the real print dialog output.
- Trade-off fix: sites loaded after mounting (App loads them async) left the scenarios empty; opening the popup
  before a first run now fills them.

## Blockers

## Requests
- Gian (App.tsx, D37 hook outside compare/): mount the comparison view in the bottom-left `.dock`, next to
  `<AiAssistant />`: `<CompareView sites={sites} defaultWindow={panelWindow} initialSiteId={selectedSite?.id ?? null} />`.
  It is self-contained like the AI assistant: a "Trade-off" pill that opens a full-app popup (fixed, z-index 50,
  Esc or Minimize keeps the setup and result). Optional `onResult` prop hands every result to App (e.g. for a
  PDF report). Optionally move `runTradeoff` / `downloadTradeoff` from `compare/tradeoffApi.ts` into `api/client.ts`.
- Gian (D42): mount `<ReportBuilder sites window={panelWindow} evaluation={outcome?.evaluation ?? null}
  analyses ranking tradeoff />` in the dock; pass `onResult` to CompareView for `tradeoff`.
- Gian (README, demo checklist): after `scripts/terrain_download_dem.py`, run
  `uv run python scripts/terrain_warm_cache.py` (next to Michael's `scripts/ephemeris_warm_cache.py`).
- Gian (D32 follow-up, D23 impact): (1) merging this PR restores `main` (13 tests red and terrain out of
  contract since PR #12); (2) the site panel can show `terrain.landing_slope_max_deg` (vs
  `max_slope_deg`) and `terrain.reachable_fraction` as soon as the UI sends an `OperationsArea` with
  `operating_range_m` > 0 (today the default area has 0, so the share is None); e.g. archetype presets
  crew 100 m / 2 km / 20 deg, rover 100 m / 20 km / 15 deg; (3) `terrain.dem_source` now says when the full
  disk was sampled on wider cells (large ranges, `MAX_GRID_RADIUS_CELLS` = 400);.
- Gian + Michael (slope max, contract meaning): on the 20 m DEM `slope_max_deg` catches isolated spikes
  (Shackleton: max 64 deg on 0.02% of pixels, 99th percentile 39 deg, mean 26 deg on both DEMs). A ranking
  filter on max slope could reject a site for one bad pixel. Proposal: define the reported maximum as the
  99th percentile over the disk (robust maximum), or keep the true max and filter on the mean.
- Gian (spec section 7): add LDEM_85S_20M (20 m, south pole to 85 S) to the LOLA data source row (D31).
- Michael (catalog coordinates): `artemis-haworth` (-87.45, -5.17) and `artemis-de-gerlache-rim-2`
  (-88.48, -88.34) fall in low ground (-3313 m and -1223 m, terrain horizon >= 3.6 deg in every direction):
  0% light and 0% Earth over 30 days. The description says rim; the approximate point is not on it.
- Michael (catalog): leave `location.height_m` empty (None) so the observer stands on the LOLA surface. A height
  is read as meters above the 1737.4 km sphere; a value from another reference lifts or buries the observer
  (e.g. 1500 m given vs -720 m terrain -> 92% light instead of 10%); below the DEM it is now rejected.
- Gian (README): `npm --prefix frontend install` fails on Windows with npm 10.9.2 (ENOENT package.json);
  `cd frontend && npm install` works.
- Gian (README): add the setup step `uv run python scripts/terrain_download_dem.py` (~650 MB, once per machine).
- Gian (spec section 7): LOLA DEM row can name the products of D28: LDEM_64 and LDEM_80S_80M,
  LRO-L-LOLA-4-GDR-V1.0, https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/
