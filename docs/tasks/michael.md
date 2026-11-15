<!-- ABOUTME: Task file of Michael: ephemerides, site catalog, domain knowledge for the AI -->
<!-- ABOUTME: Only Michael (and Michael's Claude) writes here; requirement IDs refer to docs/spec.md -->

# Michael: tasks

## Status
EPH-1, EPH-2, CAT-1, CAT-2 done (`build_ephemeris_provider`, `build_catalog` exported, IF-5).
CAT-3, EPH-3 and AI-5 content done. Next: support Gian on AI-5 parsing. Optional: landing times of
recent missions, Haworth/de Gerlache points on the rim.

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
- EPH-3: `scripts/ephemeris_warm_cache.py` (all sites at 10 min, globe origin at 1 min, default
  60 days from today; `--start`, `--days`, `--step`, `--sites`). The cache keeps parsed files in
  memory so repeated globe lookups do not re-read the large 1-minute file.
  Before the demo: `uv run python scripts/ephemeris_warm_cache.py --start <demo date> --days 60`.

- Globe checked by eye (Gian's Next item 1), all OK: Apollo 11 at 1969-07-20 20:17 UTC just inside
  the lit side near the terminator; today's phase matches; Earth direction at the near-side center;
  south pole lit at grazing angle, lit side rotating with the date; Chang'e 4/6 with no Earth;
  markers in place; click picking gives sensible coordinates.

- D34 user sites: `JsonSiteCatalog.remove_user_site` and `rename_user_site` (name stripped, id
  unchanged), contract errors (`UnknownSiteError`, `ReadOnlySiteError`, `DuplicateSiteError`).
  Several processes on one `data/user/sites.json` no longer overwrite each other: every change takes
  a lock file, re-reads the file, writes atomically; reads reload when the file changed. Checked
  end to end through the API: add 200, rename 200, delete curated 403, delete 204, delete again 404.

- AI-7 regions: `docs/domain/regions.md` (south pole <= -84 deg Artemis; north pole >= 80 deg LOLA
  polar study; equatorial and Apollo zone, NASA 1967; near/far side, LRO frame), JSON between
  REGIONS_JSON markers, acceptance case tested on the catalog. Note: IM-1 (-80.1) and the
  approximate point of Peak near Cabeus B (-82.3) fall outside the south-pole band.
- MA-1/2/3 (D37): `RobustnessAnalyzer` + `build_mission_analyzer(evaluator)`; shifts default
  +1/+3/+7/+14 d; dispersion on 2 rings x 4 points of the operations disk, each sample evaluated as a
  landing point (landing-disk slope); summary quotes only report numbers. Known-answer tests with a
  fake evaluator; live API: Apollo 11, 14 days, 1 km disk, 6.1 s, badge "real".

## Blockers

## Requests
- To Gian (D23 impact): AI-7 table ready in `docs/domain/regions.md` (regex in the file; far side
  wraps: `lon_min_deg > lon_max_deg`). MA-1/2/3 ready: `build_mission_analyzer` is exported, the API
  wires it; `RobustnessReport` needed no new field. For UI-5: offsets of each dispersion sample are
  in `offset_m`, ring radii are R/2 and R with R = landing precision + operating range.
- To Gian (user-site description, D23 impact): "Save as location" asks for a description, the
  catalog stores it, but the GUI never shows it and nothing can edit it. Proposal:
  - port: `SiteCatalog.update_user_site(site_id, *, name: str | None = None, description: str | None
    = None) -> Site` (None keeps a field, "" clears the description, blank name rejected, same
    errors as rename); `rename_user_site` can stay as a shortcut. Already implemented and tested in
    `JsonSiteCatalog` (`tests/catalog/test_catalog.py`), so the real catalog is ready;
  - API: `PATCH /api/sites/{id}` accepting `{"name"?, "description"?}`;
  - GUI: show the description in the site panel and in "My locations", with an edit action.
- To Gian (Claude CLI on Windows): `find_claude_executable` returns the extensionless npm shim
  `%APPDATA%\npm\claude` (Python 3.12 `shutil.which` matches the bare name first), which
  `subprocess` cannot run; on Windows prefer `claude.cmd` / `claude.exe`. Workaround here:
  `LUNARNAV_CLAUDE_BIN` set to `claude.cmd`. Also nothing loads `.env`: the variables must be in the
  backend's environment (or add `uvicorn --env-file .env`, which needs python-dotenv).
- To Gian (D23 impact): D34 done in `JsonSiteCatalog`, so rename and delete on the real catalog no
  longer answer 501; the two-backends overwrite is fixed too. Nothing to change on your side.
- To Gian, AI-5 priority (D23 impact): no archetype has a `priority` list (Michael's decision): for
  the crewed stay NASA lists light, Earth >= 25 % and landing slope all as mandatory without ranking
  them; the other archetypes set one weighted criterion or none. Equal weights, explained in
  `mission_archetypes.md`; the tests you asked for are in place and will check any future list.
- To Gian, D32 follow-up: `traverse_slope_limit_deg` and the observer height are now in
  `requirements.area` (`traverse_slope_limit_deg`, `observer_height_above_ground_m`) since D32 put
  them in `OperationsArea`; the top-level `observer_height_m` key is gone. `max_continuous_dark_h`
  stays in `proposed_fields` until your contract PR lands; then I move it to `requirements`.
- To Gian, AI-1: `docs/domain/example_requests.md` has 8 scripted requests with expected
  requirements (fields + values, no invented constraints) for your AI tests.
- To Gian: your Next item 1 (look at the globe by eye) is done, see Done above.
- To Federico: `docs/decisions.md` has two D30 rows (mine: observer height; yours: near-site DEM,
  which your task file calls D31). Please add a row renaming yours, since existing rows are not edited.
- Resolved by Gian (merged 496a26b): EPH-1 wording, API tests off real modules, whole-minute step in
  the contract (D25), `sky_state` truncates to the whole minute.
- Contracts review decided by Michael (D27): `Site.region_radius_m` and `Site.feature` dropped.
- To Gian (D23 impact): add `VisibilityMetrics.sun_and_earth_visible_fraction: float` in [0, 1],
  fraction of samples with Sun and Earth both visible (same "visible" definition as D20); if wanted,
  `MissionRequirements.min_sun_and_earth_visible_fraction` so the AI can constrain it (AI-5).
- To Federico (D23 impact): once the field exists, compute it in the evaluator
  (mean of `sun_visible AND earth_visible`).
- To Federico, answer on observer height and catalog points (D23 impact):
  1. Height above ground: default 2 m (D30, Gläser et al. 2014 use 2 m and 10 m as rover/lander
     solar panel heights). Per archetype: rover 2 m, small CLPS lander 2 m, crewed lander 10 m;
     the values will also go in `docs/domain/mission_archetypes.md` (AI-5).
  2. `artemis-haworth` and `artemis-de-gerlache-rim-2`: kept, flagged NOT REPRESENTATIVE (crater
     floor, not rim) in the description. Moving them onto the rim needs coordinates from the NASA
     region maps; possible later.
- To Gian, AI-5 (D23 impact): `docs/domain/mission_archetypes.md` is ready. Parse the JSON block
  with the regex written in the file (tested in `tests/domain/test_mission_archetypes.py`).
  `requirements` validates as `MissionRequirements` (without `window`: use `mission_duration_h`).
  Two contract fields requested, values already in `proposed_fields`:
  - `MissionRequirements.max_continuous_dark_h: float | None` (>= 0): longest tolerable continuous
    darkness, hours (rover battery 50 h, outpost energy storage 192 h). Needs
    `VisibilityMetrics.longest_dark_h`, which already exists.
  - Slopes (Michael's decision): `max_slope_deg` should apply to the **landing-precision disk**
    only (Artemis: < 10 deg over 100 m), not to the whole operations area: a site next to a steep
    wall the crew never crosses must not be rejected. For the operations area, add an informational
    "reachable share": fraction of the operations disk reachable from the landing point through
    cells below `traverse_slope_limit_deg` (EVA 20 deg, VIPER 15 deg) with a path length within
    `operating_range_m`; shown to the user, no minimum (no source gives one). Contract wording is
    yours.
- To Federico (D23 impact), once Gian updates the contract: (1) max slope over the
  landing-precision disk; (2) reachable share: cells with slope below the limit are traversable;
  minimum path distance from the landing point through traversable cells (Dijkstra, e.g.
  `skimage.graph.MCP_Geometric`); count cells within `operating_range_m`. A wall splitting the disk
  cuts off the far side; a detour longer than the range also excludes it. Landing dispersion is
  covered by Gian's mission analysis (MA-2), so start from the nominal point. At 20 m pixels the
  rover case (20 km) is about 2000 x 2000 cells: worth timing.
- To Gian (D23 impact): (a) whether observer height becomes a request field is your call (D30
  gives the default and per-archetype values). (b) Ephemeris stays on per-site Horizons queries
  (Michael's choice: fewer own formulas). A new date costs about 2-4 s per site; the warm-up makes
  any window inside the warmed period instant if its start is on the 10-minute grid, so please
  round window starts to 10 minutes in the UI (the globe already rounds to the minute).
