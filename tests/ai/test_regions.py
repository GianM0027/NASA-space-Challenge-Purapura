# ABOUTME: Tests of the named-region loader (spec AI-7): JSON block parsing and a missing table
# ABOUTME: Owner: Gian. The real table is Michael's docs/domain/regions.md; tests use an inline one

from __future__ import annotations

from pathlib import Path

import pytest

from lunarnav.ai.regions import load_regions, parse_regions

TABLE = (Path(__file__).parent / "data" / "regions.md").read_text(encoding="utf-8")


def test_parse_regions_reads_bounds_and_sources() -> None:
    regions = parse_regions(TABLE)
    assert list(regions) == ["south-pole", "far-side"]
    pole = regions["south-pole"]
    assert (pole.latitude_min_deg, pole.latitude_max_deg) == (None, -84.0)
    assert pole.bounds() == {"latitude_max_deg": -84.0}
    assert regions["far-side"].bounds() == {"longitude_min_deg": 90.0, "longitude_max_deg": -90.0}
    assert pole.source == "test source A"


def test_parse_regions_without_block_is_an_error() -> None:
    with pytest.raises(ValueError):
        parse_regions("# no table here")


def test_missing_table_gives_no_regions(tmp_path: Path) -> None:
    assert load_regions(tmp_path / "regions.md") == {}


def test_load_regions_reads_the_file(tmp_path: Path) -> None:
    path = tmp_path / "regions.md"
    path.write_text(TABLE, encoding="utf-8")
    assert set(load_regions(path)) == {"south-pole", "far-side"}
