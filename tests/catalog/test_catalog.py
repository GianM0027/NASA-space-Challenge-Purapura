# ABOUTME: Tests for the site catalog (CAT-1 file content, CAT-2 JsonSiteCatalog behaviour)
# ABOUTME: Uses the real curated file read-only and tmp_path for user sites

import json
import shutil
from pathlib import Path

import pytest

from lunarnav.catalog import JsonSiteCatalog, build_catalog
from lunarnav.contracts import GeoPoint, Origin, Site

CURATED = Path(__file__).parents[2] / "data" / "catalog" / "sites.json"


def _user_site(site_id: str = "my-crater") -> Site:
    return Site(
        id=site_id,
        name="My crater",
        location=GeoPoint(lat_deg=-85.0, lon_deg=30.0),
        origin=Origin.USER,
        status="custom",
    )


@pytest.fixture
def catalog(tmp_path: Path) -> JsonSiteCatalog:
    return JsonSiteCatalog(curated_path=CURATED, user_path=tmp_path / "user" / "sites.json")


# --- CAT-1: curated file ---------------------------------------------------------------------


def test_curated_file_has_enough_sourced_sites(catalog: JsonSiteCatalog) -> None:
    sites = catalog.list_sites()
    assert len(sites) >= 20
    assert all(s.sources for s in sites)
    assert all(s.origin is not Origin.USER for s in sites)


def test_curated_file_covers_required_programs(catalog: JsonSiteCatalog) -> None:
    origins = {s.origin for s in catalog.list_sites()}
    required = {"apollo", "luna", "surveyor", "change", "chandrayaan", "slim", "clps", "artemis"}
    assert required <= {o.value for o in origins}


def test_artemis_regions_are_flagged_approximate(catalog: JsonSiteCatalog) -> None:
    regions = [s for s in catalog.list_sites() if s.origin is Origin.ARTEMIS]
    assert len(regions) == 9  # NASA list of 2024-10-28
    for s in regions:
        assert s.status == "candidate"
        assert "APPROXIMATE" in s.description
        assert s.location.lat_deg < -80  # all near the south pole
    # Crater-floor points found by Federico's terrain check are flagged for the AI and the UI
    for site_id in ("artemis-haworth", "artemis-de-gerlache-rim-2"):
        assert "NOT REPRESENTATIVE" in catalog.get_site(site_id).description
    # Known answer: IAU gazetteer center of Mons Malapert (feature 16338)
    malapert = catalog.get_site("artemis-malapert-massif")
    assert (malapert.location.lat_deg, malapert.location.lon_deg) == (-85.98, -1.67)


def test_curated_file_spans_whole_moon(catalog: JsonSiteCatalog) -> None:
    sites = catalog.list_sites()
    assert any(s.location.lat_deg < -80 for s in sites)  # south polar region
    assert any(abs(s.location.lon_deg) > 90 for s in sites)  # far side


def test_apollo_11_matches_lroc_coordinates(catalog: JsonSiteCatalog) -> None:
    # Known answer: LROC 2016 coordinates update, Apollo 11 LM (0.67416 N, 23.47314 E)
    site = catalog.get_site("apollo-11")
    assert (site.location.lat_deg, site.location.lon_deg) == (0.67416, 23.47314)


def test_east_longitudes_converted_to_signed_range(catalog: JsonSiteCatalog) -> None:
    # Known answer: LROC gives Surveyor 1 at 316.6602 E, i.e. -43.3398 in [-180, 180)
    assert catalog.get_site("surveyor-1").location.lon_deg == pytest.approx(316.6602 - 360.0)


# --- CAT-2: behaviour ------------------------------------------------------------------------


def test_get_unknown_site_raises_key_error(catalog: JsonSiteCatalog) -> None:
    with pytest.raises(KeyError):
        catalog.get_site("does-not-exist")


def test_add_user_site_lists_it_after_curated(catalog: JsonSiteCatalog) -> None:
    n = len(catalog.list_sites())
    added = catalog.add_user_site(_user_site())
    sites = catalog.list_sites()
    assert len(sites) == n + 1
    assert sites[-1] == added
    assert catalog.get_site("my-crater") == added


def test_duplicate_id_rejected(catalog: JsonSiteCatalog) -> None:
    catalog.add_user_site(_user_site())
    with pytest.raises(ValueError, match="already exists"):
        catalog.add_user_site(_user_site())
    with pytest.raises(ValueError, match="already exists"):
        catalog.add_user_site(_user_site("apollo-11"))  # clashes with a curated id


def test_user_file_round_trip(tmp_path: Path) -> None:
    user = tmp_path / "user" / "sites.json"
    JsonSiteCatalog(curated_path=CURATED, user_path=user).add_user_site(_user_site())
    assert user.exists()
    reloaded = JsonSiteCatalog(curated_path=CURATED, user_path=user)
    assert reloaded.get_site("my-crater") == _user_site()
    assert reloaded.list_sites()[-1].id == "my-crater"


def test_duplicate_ids_across_files_rejected(tmp_path: Path) -> None:
    user = tmp_path / "sites.json"
    curated_first = json.loads(CURATED.read_text(encoding="utf-8"))[0]
    user.write_text(json.dumps([curated_first]), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate site id"):
        JsonSiteCatalog(curated_path=CURATED, user_path=user)


def test_invalid_file_names_the_path(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('[{"id": "x"}]', encoding="utf-8")
    with pytest.raises(ValueError, match=r"bad\.json"):
        JsonSiteCatalog(curated_path=bad, user_path=tmp_path / "u.json")


def test_build_catalog_reads_repo_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "data" / "catalog").mkdir(parents=True)
    shutil.copy(CURATED, tmp_path / "data" / "catalog" / "sites.json")
    monkeypatch.chdir(tmp_path)  # factory paths are relative to the working directory
    catalog = build_catalog()
    assert catalog.get_site("apollo-11").origin is Origin.APOLLO
