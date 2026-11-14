<!-- ABOUTME: Task file of Michael: ephemerides, site catalog, domain knowledge for the AI -->
<!-- ABOUTME: Only Michael (and Michael's Claude) writes here; requirement IDs refer to docs/spec.md -->

# Michael: tasks

## Status
EPH-1, EPH-2, CAT-1, CAT-2 done (`build_ephemeris_provider`, `build_catalog` exported, IF-5).
CAT-3 done (descriptions for all sites). Next: AI-5, EPH-3. Optional: landing times of recent missions.

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
- CAT-3: one-to-two sentence description on every site.
- Historical verification: Apollo landing times added to the catalog (Orloff, via ALSJ); test
  `tests/ephemeris/test_apollo_verification.py` compares Sun and Earth alt/az at the 6 Apollo landings
  with the ALSJ table: Sun within 0.02 deg; Earth elevation 0.05-0.22 deg lower, explained by
  topocentric parallax (the table uses the Moon-center direction). Good demo material.

## Blockers

## Requests
- Resolved by Gian (merged 496a26b): EPH-1 wording, API tests off real modules, whole-minute step in
  the contract (D25), `sky_state` truncates to the whole minute.
- Contracts review decided by Michael (D27): `Site.region_radius_m` and `Site.feature` dropped.
- To Gian (D23 impact): add `VisibilityMetrics.sun_and_earth_visible_fraction: float` in [0, 1],
  fraction of samples with Sun and Earth both visible (same "visible" definition as D20); if wanted,
  `MissionRequirements.min_sun_and_earth_visible_fraction` so the AI can constrain it (AI-5).
- To Federico (D23 impact): once the field exists, compute it in the evaluator
  (mean of `sun_visible AND earth_visible`).
