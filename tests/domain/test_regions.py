# ABOUTME: Checks docs/domain/regions.md (AI-7): JSON block extractable, bounds valid and sourced
# ABOUTME: Owner: Michael; includes the AI-7 acceptance case on the real catalog (south pole only)

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
PATTERN = re.compile(
    r"<!--\s*REGIONS_JSON_BEGIN\s*-->\s*```json\s*(.*?)\s*```\s*<!--\s*REGIONS_JSON_END\s*-->",
    re.DOTALL,
)
KEYS = {
    "id",
    "label",
    "summary",
    "latitude_min_deg",
    "latitude_max_deg",
    "lon_min_deg",
    "lon_max_deg",
    "source",
}


def _regions() -> dict[str, dict]:
    matches = PATTERN.findall((ROOT / "docs/domain/regions.md").read_text(encoding="utf-8"))
    assert len(matches) == 1, "exactly one REGIONS_JSON block expected"
    data = json.loads(matches[0])
    assert data["schema_version"] == 1
    return {r["id"]: r for r in data["regions"]}


def inside(region: dict, lat: float, lon: float) -> bool:
    """Reference implementation of the documented rule (inclusive, null = no limit, wrap)."""
    lo_lat, hi_lat = region["latitude_min_deg"], region["latitude_max_deg"]
    if (lo_lat is not None and lat < lo_lat) or (hi_lat is not None and lat > hi_lat):
        return False
    lo, hi = region["lon_min_deg"], region["lon_max_deg"]
    if lo is None and hi is None:
        return True
    lo = -180.0 if lo is None else lo
    hi = 180.0 if hi is None else hi
    return lo <= lon <= hi if lo <= hi else (lon >= lo or lon <= hi)


def _catalog() -> list[dict]:
    return json.loads((ROOT / "data/catalog/sites.json").read_text(encoding="utf-8"))


def _ll(site: dict) -> dict:
    return {"lat": site["location"]["lat_deg"], "lon": site["location"]["lon_deg"]}


REGIONS = _regions()


@pytest.mark.parametrize("region", REGIONS.values(), ids=lambda r: r["id"])
def test_schema_bounds_and_source(region: dict) -> None:
    assert set(region) == KEYS, set(region) ^ KEYS
    assert region["label"].strip() and region["summary"].strip() and region["source"].strip()
    for key in ("latitude_min_deg", "latitude_max_deg"):
        if region[key] is not None:
            assert -90 <= region[key] <= 90
    for key in ("lon_min_deg", "lon_max_deg"):
        if region[key] is not None:
            assert -180 <= region[key] < 180 or region[key] == 180
    bounds = [region[k] for k in KEYS if k.endswith("_deg")]
    assert any(b is not None for b in bounds), "a region needs at least one bound"


def test_ai7_acceptance_south_pole_keeps_only_polar_sites() -> None:
    # Spec AI-7: "two-week robotic lander near the south pole" ranks only south-polar sites.
    sites = _catalog()
    near = {s["id"] for s in sites if inside(REGIONS["south-polar-region"], **_ll(s))}
    at = {s["id"] for s in sites if inside(REGIONS["south-pole"], **_ll(s))}
    assert {"change-6", "change-4", "luna-13", "chandrayaan-3"}.isdisjoint(near)
    assert all(s["location"]["lat_deg"] <= -80 for s in sites if s["id"] in near)
    assert all(s["location"]["lat_deg"] <= -84 for s in sites if s["id"] in at)
    assert at < near  # "at" is the stricter Artemis band
    assert {"im-2", "artemis-malapert-massif"} <= at
    # IM-1 (-80.13) and the approximate Cabeus B point (-82.26): near the pole, not at it
    assert {"im-1", "artemis-peak-near-cabeus-b"} <= near - at


def test_summaries_steer_near_and_at_the_south_pole() -> None:
    assert "near the south pole" in REGIONS["south-polar-region"]["summary"]
    assert "at the south pole" in REGIONS["south-pole"]["summary"]
    assert REGIONS["south-pole"]["latitude_max_deg"] == -84  # NASA Artemis: within 6 deg


def test_known_sites_fall_in_the_expected_regions() -> None:
    by_id = {s["id"]: _ll(s) for s in _catalog()}
    assert inside(REGIONS["near-side"], **by_id["apollo-11"])
    assert not inside(REGIONS["far-side"], **by_id["apollo-11"])
    for far in ("change-4", "change-6"):  # far-side landings, lon about 178 E and 154 W
        assert inside(REGIONS["far-side"], **by_id[far])
        assert not inside(REGIONS["near-side"], **by_id[far])
    assert inside(REGIONS["apollo-zone"], **by_id["apollo-11"])
    assert not inside(REGIONS["apollo-zone"], **by_id["apollo-16"])  # -8.97 deg, outside +/-5
    assert inside(REGIONS["equatorial"], **by_id["luna-16"])
    assert not any(inside(REGIONS["north-pole"], **ll) for ll in by_id.values())
