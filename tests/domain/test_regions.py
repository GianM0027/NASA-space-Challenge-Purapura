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
BOUNDS = ("lat_min_deg", "lat_max_deg", "lon_min_deg", "lon_max_deg")


def _regions() -> dict[str, dict]:
    matches = PATTERN.findall((ROOT / "docs/domain/regions.md").read_text(encoding="utf-8"))
    assert len(matches) == 1, "exactly one REGIONS_JSON block expected"
    data = json.loads(matches[0])
    assert data["schema_version"] == 1
    return {r["id"]: r for r in data["regions"]}


def inside(region: dict, lat: float, lon: float) -> bool:
    """Reference implementation of the documented rule (inclusive bounds, wrap when min > max)."""
    if region["lat_min_deg"] is not None and lat < region["lat_min_deg"]:
        return False
    if region["lat_max_deg"] is not None and lat > region["lat_max_deg"]:
        return False
    lo, hi = region["lon_min_deg"], region["lon_max_deg"]
    if lo is None:
        return True
    return lo <= lon <= hi if lo <= hi else (lon >= lo or lon <= hi)


def _catalog() -> list[dict]:
    return json.loads((ROOT / "data/catalog/sites.json").read_text(encoding="utf-8"))


REGIONS = _regions()


@pytest.mark.parametrize("region", REGIONS.values(), ids=lambda r: r["id"])
def test_bounds_are_valid_and_sourced(region: dict) -> None:
    assert region["name"] and region["aliases"]
    for key in BOUNDS:
        value = region[key]
        if value is None:
            continue
        limit = 90 if key.startswith("lat") else 180
        assert -limit <= value <= limit, f"{region['id']}.{key} out of range"
        assert region["sources"].get(key, "").strip(), f"{region['id']}.{key} has no source"
    if region["lat_min_deg"] is not None and region["lat_max_deg"] is not None:
        assert region["lat_min_deg"] < region["lat_max_deg"]


def test_ai7_acceptance_south_pole_keeps_only_polar_sites() -> None:
    # Spec AI-7: "two-week robotic lander near the south pole" ranks only south-polar sites.
    sites = _catalog()
    polar = {s["id"] for s in sites if inside(REGIONS["south-pole"], **_ll(s))}
    assert polar, "no catalog site in the south-polar region"
    assert all(s["location"]["lat_deg"] <= -84 for s in sites if s["id"] in polar)
    assert {"change-6", "change-4", "luna-13", "chandrayaan-3"}.isdisjoint(polar)
    assert {"im-2", "artemis-malapert-massif"} <= polar
    assert "im-1" not in polar  # -80.13 deg: south-polar in common speech, outside the 6 deg band


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
    assert not any(
        inside(REGIONS["north-pole"], **ll) for ll in by_id.values()
    )  # none so far north


def _ll(site: dict) -> dict:
    return {"lat": site["location"]["lat_deg"], "lon": site["location"]["lon_deg"]}
