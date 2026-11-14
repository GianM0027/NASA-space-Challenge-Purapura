<!-- ABOUTME: Task file of Federico: terrain (horizon masks, slopes) and evaluation (metrics) -->
<!-- ABOUTME: Only Federico (and Federico's Claude) writes here; requirement IDs refer to docs/spec.md -->

# Federico: tasks

## Status
Not started.

## Next (in priority order)
1. Setup: `git checkout -b federico`, `uv sync --group terrain --group evaluation --group dev`, `uv run pytest` green.
2. C1 (DEM feasibility): choose the LOLA DEM(s) for the whole Moon and the poles; measure time and memory for one
   horizon mask; record the choice in `docs/decisions.md`.
3. TER-3 (DEM download script) `scripts/terrain_download_dem.py`.
4. TER-1 (horizon mask, curvature included) with known-answer tests.
5. EVA-1 (visibility and metrics from series plus mask) against `data/examples/ephemeris_series.json` and
   `horizon_mask.json`; tests on synthetic series (definitions in spec section 3 and D20, visibility definition).
6. TER-2 (slope statistics over a disk) and EVA-2 (terrain over the operations area).
7. TER-5 (horizon mask cache), EVA-3 (speed target), TER-4 (high-resolution polar DEMs).

Tips: the `Evaluator` receives an `EphemerisProvider` and a `TerrainProvider` in its constructor;
for tests write small fakes of both that return the example payloads.

## Done

## Blockers

## Requests
