---
name: hackathon-python
description: "Python rules for the LunarNav hackathon repo: uv with one dependency group per module, src layout, Pydantic contracts at module boundaries, Protocol ports, Google docstrings, ruff, pytest with known-answer tests for numeric code, numpy vectorization, scientific constants with sources. Use when writing or changing any .py file, adding a dependency, or writing tests."
---

<!-- ABOUTME: Hackathon Python skill: uv dependency groups, contracts at boundaries, docstrings, known-answer tests -->
<!-- ABOUTME: Lean version of the team's python and verification rules: no mypy strict, no mutation testing, no TDD ceremony -->

# Hackathon Python

## Environment

- Python version: whatever `.python-version` says. Never write it anywhere else.
- `uv` only. Run everything through `uv run ...`.
- Add a dependency **only to your module's group**, then commit `pyproject.toml` and `uv.lock` together:

```bash
uv add --group terrain rasterio      # group names = module names, see pyproject.toml
uv sync --group terrain --group dev
```

- `uv.lock` merge conflict: keep either side, run `uv lock`, commit the regenerated file.
- Prefer libraries with prebuilt wheels on Windows, macOS and Linux (the team uses all three).

## Layout

```
src/lunarnav/<module>/      production code of one module (one owner)
tests/<module>/             its tests
scripts/<module>_*.py       one-off scripts (data download, precompute)
data/examples/              contract-valid sample payloads (owner: Gian)
```

Imports between modules go through contracts: a module imports `lunarnav.contracts` and,
only where the spec says so, another module's public function. Never import from `scripts/`.

## Contracts at the boundary

- Public functions of a module take and return the Pydantic models in `lunarnav.contracts`.
- Inside a module use whatever is fastest (numpy arrays, dataclasses); convert at the edge.
- Validate external data (files, HTTP responses, LLM output) with `Model.model_validate(...)`
  at the point it enters; let `ValidationError` surface with context, never swallow it.

## Code style

- Type hints on every signature. `X | None`, `list[float]`.
- **Google docstrings** on every public function and class: what it does, `Args` with **units and
  frames**, `Returns`, `Raises`. Private helpers: one line is enough.
- Line comments only for the non-obvious: a source for a constant, a frame convention, a shape.
- Constants with a source next to them:
  `MOON_RADIUS_M = 1_737_400.0  # IAU mean radius, also the LOLA/PGDA reference sphere`
- Vectorize with numpy over time steps and azimuths; no Python loops over thousands of elements.
- No bare `except:`. Errors carry context: `raise ValueError(f"latitude {lat} outside [-90, 90]")`.
- No print debugging left in commits; use `logging`.

## Tests (pytest)

What must be tested, with a **known answer** computed by hand or from a cited source:

- every geometric formula (frames, azimuth/elevation, distances on the sphere)
- every metric (illumination fraction, longest period, time to next event)
- ranking and filtering logic

Patterns:

```python
def test_flat_terrain_has_zero_horizon() -> None:
    mask = horizon_from_dem(flat_dem(), lat_deg=0.0, lon_deg=0.0)
    assert np.allclose(mask.horizon_elevation_deg, 0.0, atol=0.05)


def test_example_payload_matches_contract() -> None:
    Evaluation.model_validate_json(Path("data/examples/evaluation.json").read_text())
```

- A new test must fail before your code makes it pass (or break the line, see it fail, restore it).
- Never change an expected value to match the output without a reason you can state.
- Slow tests (> 5 s, real DEM, network): mark `@pytest.mark.slow`; they are skipped by default,
  run them with `uv run pytest -m slow`.
- Network calls (e.g. JPL Horizons) are never in default tests: record a response once into
  `tests/<module>/fixtures/` and test against it.

## Performance

No numbers from intuition: if something is "slow", time it (`time.perf_counter`, a few repeats)
and report the measurement. Cache expensive per-site results on disk under `data/cache/`.
