<!-- ABOUTME: Task file of Gian: contracts, AI, mission analysis, API and frontend; status, next, blockers -->
<!-- ABOUTME: Only Gian (and Gian's Claude) writes here; requirement IDs refer to docs/spec.md -->

# Gian: tasks

## Status
End to end on real catalog, ephemeris, terrain and evaluation: 3D globe, site panel with timeline,
and the AI box (UI-4): chat and ranking tabs over one bar of editable criteria, deterministic
ranking (AI-2), extraction and explanations through the Claude Code CLI (AI-1, AI-3, AI-4),
archetypes from Michael's file (AI-5, decision D33). Mission analysis is still a placeholder.

## Next (in priority order)
1. Look at the globe with the Browser pane visible: terminator, markers and click picking were
   checked through the DOM and network only, not by eye.
3. AI-1 acceptance: 5 scripted requests through the real CLI, recorded with their timings.
4. UI-3 (side-by-side comparison).
5. MA-1 (date-slip sweep), MA-2 (dispersion), MA-3 (summary), UI-5 (mission analysis view), AI-6 (AI presents it).
6. UI-6 (data attribution), then P2 items if time remains.

## Done
- User locations (Federico's request, decision D34): coordinates box (lat [-90, 90], east-positive
  lon [-180, 180), checked client-side) that analyzes a point like a globe click and is prefilled by
  a click; "Save as location" (id `user-<slug>`); "My locations" section with inline rename and
  delete with confirmation. API `DELETE`/`PATCH /api/sites/{id}` (404, 403, 422; 501 until the real
  catalog implements them), 7 API tests, 13 frontend tests. Checked in the browser on the real
  catalog (save, 409, 501 message) and on placeholders (rename, delete, 404 after an outside delete).
- Site panel holds the whole window (start date, duration, step), always visible; picking a ranked
  site sets it to the mission window, so panel and ranking show the same numbers (checked in the browser).
- UI-4, AI-1, AI-2, AI-3, AI-4, AI-5 (decision D33): `lunarnav.ai` (ranking with ROC weights, archetype
  loader, CLI client with no context, number check, chat assistant) and the AI box; 29 tests in
  `tests/ai/` (sabotage-checked), checked in the browser on real data (short crewed stay: 9 polar
  sites, none passes 156 h of continuous light, IM-2 closest). Measured once each: request 7.7 s,
  five explanations 12.7 s, cold-cache ranking of 36 sites 21 s.
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
- Michael (decision D34, user locations): `JsonSiteCatalog` gets the two new `SiteCatalog` methods,
  with the same atomic write path as `add_user_site`:
  - `remove_user_site(site_id) -> None` and `rename_user_site(site_id, name) -> Site` (name stripped,
    id unchanged);
  - raise the contract errors from `lunarnav.contracts`: `UnknownSiteError` for an unknown id,
    `ReadOnlySiteError` for a curated site (`origin != "user"`), `ValueError` for a blank name;
    `add_user_site` should raise `DuplicateSiteError` (a `ValueError`, so nothing else changes);
  - tests: remove, rename, curated site rejected, unknown id rejected, file round trip (a new
    catalog on the same file sees the change).
  Until then the app answers 501 to rename and delete on the real catalog. Also worth a look: two
  backends on the same `data/user/sites.json` overwrite each other's additions, because each keeps
  its own in-memory list and rewrites the whole file (seen with two dev servers running).
- Michael (AI-5, decision D33): add `priority` (ordered groups of criterion names, with a source in
  `sources["priority"]`) to each archetype; after this merges, move `max_continuous_dark_h` from
  `proposed_fields` to `requirements` (now a contract field). Details sent by message.
- Michael (EPH-3, demo speed): a cold ranking of 36 sites takes about 21 s, almost all of it
  Horizons. Warm the cache for the demo windows (start date x mission durations of the archetypes).
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
