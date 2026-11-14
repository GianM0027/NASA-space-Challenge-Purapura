<!-- ABOUTME: Task file of Gian: contracts, AI, mission analysis, API and frontend; status, next, blockers -->
<!-- ABOUTME: Only Gian (and Gian's Claude) writes here; requirement IDs refer to docs/spec.md -->

# Gian: tasks

## Status
The app is viewable end to end on placeholder data: 3D Moon globe (NASA LRO WAC texture, sunlight
from `/api/sky`, Earth direction, site markers, click to pick), date control, site list and site
panel with power, communication and terrain metrics. Real modules plug in by themselves through
their factories (IF-5, automatic wiring); badges in the header show which are live.

## Next (in priority order)
1. Look at the globe with the Browser pane visible: terminator, markers and click picking were
   checked through the DOM and network only, not by eye.
3. UI-4 (AI box) on example data, then C3 (LLM JSON check) and AI-1 (request to requirements), AI-2 (deterministic ranking).
4. UI-3 (side-by-side comparison).
5. MA-1 (date-slip sweep), MA-2 (dispersion), MA-3 (summary), UI-5 (mission analysis view), AI-6 (AI presents it).
6. UI-6 (data attribution), then P2 items if time remains.

## Done
- UI-2 (site panel): Sun and Earth elevation timeline against the per-sample horizon, joint visibility, truncated periods; checked on Apollo 11 and Malapert Massif with real catalog, ephemeris and terrain.
- UI-1 (3D globe, decision D22) with `GET /api/sky`; automatic module wiring (IF-5, decision D21); TypeScript types generated from the contracts with a staleness test.
- API skeleton (IF-4, REST API) on example services, 11 smoke tests; frontend scaffold with `/api` proxy, verified end to end in the browser.
- Node.js LTS installed on this PC.
- Minor: Starlette warns that `httpx` with its TestClient is deprecated in favour of `httpx2`; switch after verifying the `httpx2` package.

## Answers to requests from others
- Michael, EPH-1 wording: done in the spec (any window length, 60 days at 10 min only as the speed case).
- Michael, API tests against the real provider: done; API tests build placeholder-only services
  (`build_services(use_real=False)`), wiring tests start from "no factories".
- Michael, globe: `sky_state` truncates to the whole minute, so a 1 minute warm-up at lat 0, lon 0 (EPH-3) hits.
- Michael, whole-minute step: now in the contract (decision D25, sampling step).
- Michael, new fields (`Site.region_radius_m`, `Site.feature`, `VisibilityMetrics.sun_and_earth_visible_fraction`):
  pending the team's review of the parameters to show; not added yet.

- Federico, wiring test: already fixed on `main` (wiring tests start from "no factories"); merge `main`.
- Federico, README (npm on Windows, DEM download step) and spec section 7 (LOLA products): done.
- Federico, slope baseline in the panel: done ("regional slopes, N m baseline").
- Federico and Michael, new contract fields (per-sample horizon elevation at the body azimuth,
  `sun_and_earth_visible_fraction`, `earth_elevation_mean_visible_deg`, truncated-run flags):
  waiting for Gian's go-ahead.

- Federico, slope contract request (landing slope, traverse limit, reachable share, observer
  height): done on `gian` as decision D32; the breaking port change waits for Federico (Requests).

## Blockers

## Requests
- Federico (decision D32, slope contract; breaking port change, lands atomically): merge `origin/gian`
  into `federico`, then in the same PR:
  - `LolaTerrainProvider.horizon_mask(location, area)`: observer height from
    `area.observer_height_above_ground_m` (default 2 m, D30) instead of the constructor; the horizon
    cache key must include the height;
  - `LolaTerrainProvider.terrain_stats(location, area)`: fill `landing_radius_m`,
    `landing_slope_mean_deg`, `landing_slope_max_deg`, `traverse_slope_limit_deg`, `reachable_fraction`
    (None when `operating_range_m` is 0); `slope_max_deg` stays the true maximum over the full disk;
  - `LunarEvaluator`: pass `area` to both calls; update the fakes in `tests/evaluation/` and
    `tests/terrain/` (13 tests red on `gian` until then).
  The placeholder `ExampleTerrainProvider` and `ExampleEvaluator` already use the new signatures.
- Done in PR #8: Federico (decision D29, new contract fields; blocks the tests on `main`): `LunarEvaluator` must fill the
  fields now required by the contract, otherwise `Evaluation`/`VisibilityMetrics` fail validation (8 tests in
  `tests/evaluation/` red after merging `main`, and `/api/evaluate` answers 502 in the app):
  - `Evaluation.sun_horizon_elevation_deg`, `Evaluation.earth_horizon_elevation_deg`: the `horizon_at(...)`
    arrays already computed for `is_visible` (same values, so the UI timeline matches the engine);
  - `VisibilityMetrics.sun_and_earth_visible_fraction`, `earth_elevation_mean_visible_deg`,
    `longest_light_truncated`, `longest_dark_truncated`, `longest_earth_visible_truncated`,
    `longest_earth_hidden_truncated`.
  Definitions: spec section 3 (Truncated run, Joint visibility, Horizon per sample); reference implementation
  and known-answer tests: `src/lunarnav/api/placeholder_metrics.py`, `tests/api/test_placeholder_metrics.py`.
