<!-- ABOUTME: Task file of Federico: terrain (horizon masks, slopes) and evaluation (metrics) -->
<!-- ABOUTME: Only Federico (and Federico's Claude) writes here; requirement IDs refer to docs/spec.md -->

# Federico: tasks

## Status
Setup, C1 and TER-3 done; next TER-1 (horizon mask).

## Next (in priority order)
1. TER-1 (horizon mask, curvature included) with known-answer tests.
2. EVA-1 (visibility and metrics from series plus mask) against `data/examples/ephemeris_series.json` and
   `horizon_mask.json`; tests on synthetic series (definitions in spec section 3 and D20, visibility definition).
3. TER-2 (slope statistics over a disk) and EVA-2 (terrain over the operations area).
4. TER-5 (horizon mask cache), EVA-3 (speed target), TER-4 (high-resolution polar DEMs).

Tips: the `Evaluator` receives an `EphemerisProvider` and a `TerrainProvider` in its constructor;
for tests write small fakes of both that return the example payloads.

## Done
- Setup: branch `federico`, `uv sync --group terrain --group evaluation --group dev`, 15 tests green.
- C1 (DEM feasibility): LDEM_64 global + LDEM_80S_80M south polar, rays to 150 km; ~0.02 s / 13 MB
  and ~0.19 s / 76 MB per mask (`scripts/terrain_c1_benchmark.py`, decision D21). Polar stereographic
  signs verified against LDEM_64 and Shackleton crater (an east-west mirror bug was caught this way).
- TER-3: `scripts/terrain_download_dem.py` fetches the D21 DEMs from PDS into `data/raw/lola/` (~650 MB);
  skips complete files, size-checked `.part` downloads; verified byte-identical re-download of LDEM_80S_80M.

## Blockers

## Requests
- Gian (README): add the setup step `uv run python scripts/terrain_download_dem.py` (~650 MB, once per machine).
- Gian (spec section 7): LOLA DEM row can name the products of D21: LDEM_64 and LDEM_80S_80M,
  LRO-L-LOLA-4-GDR-V1.0, https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/
