<!-- ABOUTME: Task file of Federico: terrain (horizon masks, slopes) and evaluation (metrics) -->
<!-- ABOUTME: Only Federico (and Federico's Claude) writes here; requirement IDs refer to docs/spec.md -->

# Federico: tasks

## Status
Terrain and evaluation live with the D29 fields; TER-5 and EVA-3 done. Next: TER-4 (20 m near-site DEM).

## Next (in priority order)
1. TER-4 (finer polar DEMs,
   multi-resolution rays: fine near the site, coarse far away).

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

## Blockers

## Requests
- Michael + Gian (observer height above ground, domain + contract): `LolaTerrainProvider` now takes
  `observer_height_above_ground_m` (default 0 m = on the surface) and rejects absolute heights below the DEM.
  Sensitivity, 30 d from 2026-11-14, light % at 0/1/2/5/10 m: Malapert 47/50/53/60/69, IM-2 51/52/52/53/53,
  Mons Mouton plateau 40/40/41/41/42, Nobile rim 1 unchanged. Michael: pick a sourced default (solar panel
  height); Gian: decide whether it becomes a per-request field (e.g. in `OperationsArea`).
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
