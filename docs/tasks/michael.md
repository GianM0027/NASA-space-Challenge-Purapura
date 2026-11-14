<!-- ABOUTME: Task file of Michael: ephemerides, site catalog, domain knowledge for the AI -->
<!-- ABOUTME: Only Michael (and Michael's Claude) writes here; requirement IDs refer to docs/spec.md -->

# Michael: tasks

## Status
EPH-1, EPH-2, CAT-1, CAT-2 done (`build_ephemeris_provider`, `build_catalog` exported, IF-5).
Next: AI-5, CAT-3 (Apollo and recent landing times), EPH-3.

## Next (in priority order)
1. Setup: `git checkout -b michael`, `uv sync --group ephemeris --group catalog --group dev`, `uv run pytest` green.
2. Check the Space Apps submission requirements (format, deadline, AI-use disclosure) and tell the team.
3. C2 (Horizons query check): a JPL Horizons query for a topocentric lunar site returns Sun and Earth azimuth and
   elevation; note request limits; decide Horizons vs offline kernels (D3, ephemerides); record in `docs/decisions.md`.
4. EPH-1 (Sun and Earth provider) with a recorded-response test, EPH-2 (disk cache).
5. CAT-1 (catalog file, at least 20 sourced sites) and CAT-2 (catalog class). Suggested coverage: Apollo 11, 12, 14, 15, 16, 17;
   Luna 9, 16, 17, 20, 21, 24; Surveyor 1, 3, 5, 6, 7; Chang'e 3, 4, 5, 6; Chandrayaan-3; SLIM;
   CLPS landings (IM-1, Blue Ghost M1, IM-2); NASA's current Artemis III candidate regions.
   Coordinates only from a citable source, written in `sources`.
6. AI-5 (mission archetypes): domain content for the AI: mission archetypes and **sourced** typical values
   (illumination, continuous light, Earth visibility, slope, landing precision, rover range).
   Write it in `docs/domain/mission_archetypes.md` (Michael owns `docs/domain/`); agree the
   layout with Gian so the AI module can parse it.
7. CAT-3 (site descriptions), EPH-3 (cache warm-up script).

## Done
- Setup: branch `michael`, `uv sync`, 15 tests green.
- Submission rules: team already aware (skipped).
- C2 (Horizons query check): works for topocentric lunar sites; limits and decision in D24.
  Recorded responses for the EPH-1 test in `tests/ephemeris/fixtures/` (Apollo 11, Sun and Earth, 2026-12-01 00:00-01:00 UTC, 10 min).
- EPH-1: `HorizonsEphemerisProvider`, any window length (split at 80,000 rows), 1-sample windows work.
  Tolerance vs Horizons: exact to the printed 1e-6 deg (values passed through; live check in the slow test).
- EPH-2: disk cache `data/cache/ephemeris/`, also serves sub-windows and coarser steps on the same grid.
- CAT-1: `data/catalog/sites.json`, 27 landed sites (Apollo 6, Luna 7, Surveyor 5, Chang'e 4,
  Chandrayaan-3, SLIM, CLPS 3), coordinates from LROC/NSSDCA/NASA/JAXA, cited per site; heights left
  null (taken from the DEM). Landing times only where a source gives UT (Luna, Surveyor, Chang'e 5, Chandrayaan-3).
- CAT-2: `JsonSiteCatalog`, user sites in `data/user/sites.json`; tests for list, get, add, duplicates, round trip.

- Artemis candidate regions: the 9 regions of NASA's 2024-10-28 list added as `candidate` sites
  (36 sites in total). NASA publishes no region centers, so each uses the IAU gazetteer center of
  the named feature, flagged APPROXIMATE in the description (Michael's decision). Named "first Artemis
  crewed landing", not "Artemis III", because the landing mission may change.

## Blockers

## Requests
- To Gian, tests (D23 impact): with the real `build_catalog` present, `test_add_user_site` writes the
  real `data/user/sites.json`, so it fails with 409 on every second run. Suggested fix: the API test
  client should use a fake catalog or a `JsonSiteCatalog(user_path=tmp_path / ...)`.
- To Gian (spec owner), EPH-1: replace "spans up to about 60 days" with "any window (landing date plus
  mission duration); the provider splits long windows into several Horizons requests (90,000-row cap)".
  60 days at 10 min stays only as the acceptance test case. Reason: the window comes from the user, it
  should not be capped by the spec; 1 year at 10 min is about 52,600 rows per body, still cheap.
- To Gian, tests (D23 impact): with the real `build_ephemeris_provider` present, 3 API tests fail
  (`test_placeholder_earth_is_at_zenith_at_the_sub_earth_point`, `test_placeholder_earth_is_hidden_on_the_far_side`,
  `test_real_evaluator_receives_ephemeris_and_terrain`): they assume the placeholder ephemeris, and the
  test client now calls live Horizons and writes `data/cache/`. Suggested fix: in those tests force the
  example provider (e.g. `_fake_module(monkeypatch, "lunarnav.ephemeris")` or patch `find_factory`).
- To Gian, globe (D23 impact): a new date costs 2 Horizons requests (about 2-4 s) the first time; the
  cache hits only the same instant on the same grid. If `sky_state` rounds `time_utc` to the whole
  minute, an EPH-3 warm-up at lat 0, lon 0 with a 1-minute step makes every date change instant.
- To Gian and Federico (D23 impact): `step_minutes` must be a whole number of minutes (Horizons
  limit); a fractional step raises `ValueError`.
- To Gian, contracts review (optional fields, catalog side):
  - `Site.region_radius_m: float | None`: Artemis III candidates are regions (about 15 km), not points.
  - `Site.feature: str | None`: named feature (e.g. "Mare Tranquillitatis", "Shackleton rim") for UI and AI retrieval.
  - `VisibilityMetrics.sun_and_earth_visible_fraction`: time with power and direct-to-Earth link
    together, a common archetype constraint (AI-5).
