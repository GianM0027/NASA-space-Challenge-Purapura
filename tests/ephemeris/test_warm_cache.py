# ABOUTME: Tests for the EPH-3 warm-up script and the cache's in-memory reuse of parsed files
# ABOUTME: No network: the provider is replaced by a recorder

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

import pytest

from lunarnav.contracts import EphemerisSeries, GeoPoint, TimeWindow
from lunarnav.ephemeris import EphemerisCache

SCRIPT = Path(__file__).parents[2] / "scripts" / "ephemeris_warm_cache.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("ephemeris_warm_cache", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Recorder:
    calls: ClassVar[list[tuple[GeoPoint, TimeWindow]]] = []

    def __init__(self) -> None:
        _Recorder.calls = []

    def sun_earth(self, location: GeoPoint, window: TimeWindow) -> None:
        if location.lat_deg == -84.7906:  # IM-2: simulate one failing target
            raise RuntimeError("Horizons down")
        _Recorder.calls.append((location, window))


def test_warm_up_covers_sites_and_globe(monkeypatch: pytest.MonkeyPatch) -> None:
    script = _load_script()
    monkeypatch.setattr(script, "HorizonsEphemerisProvider", _Recorder)
    failures = script.main(["--start", "2026-12-01", "--days", "2", "--sites", "apollo-11", "im-2"])
    assert failures == 1  # IM-2 failed, the run continued
    (site, w_site), (globe, w_globe) = _Recorder.calls
    assert (site.lat_deg, site.lon_deg) == (0.67416, 23.47314)
    assert (globe.lat_deg, globe.lon_deg) == (0.0, 0.0)
    start = datetime(2026, 12, 1, tzinfo=UTC)
    assert w_site == TimeWindow(start_utc=start, end_utc=start + timedelta(days=2), step_minutes=10)
    assert w_globe.step_minutes == 1


def test_warm_up_rejects_unknown_site() -> None:
    with pytest.raises(SystemExit, match="unknown site ids"):
        _load_script().main(["--sites", "not-a-site", "--no-globe"])


def test_cache_parses_each_file_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    t0 = datetime(2026, 12, 1, tzinfo=UTC)
    w = TimeWindow(start_utc=t0, end_utc=t0 + timedelta(minutes=20), step_minutes=10)
    times = [t0 + timedelta(minutes=10 * i) for i in range(3)]
    series = EphemerisSeries(
        location=GeoPoint(lat_deg=0.0, lon_deg=0.0),
        times_utc=times,
        sun_azimuth_deg=[90.0] * 3,
        sun_elevation_deg=[1.0, 2.0, 3.0],
        earth_azimuth_deg=[270.0] * 3,
        earth_elevation_deg=[80.0] * 3,
        source="test",
    )
    cache = EphemerisCache(tmp_path)
    cache.put(series, w)
    parses = []
    original = EphemerisSeries.model_validate_json
    monkeypatch.setattr(
        EphemerisSeries,
        "model_validate_json",
        classmethod(lambda cls, data: parses.append(1) or original(data)),
    )
    assert cache.get(series.location, w) == series
    assert cache.get(series.location, w) == series
    assert len(parses) == 1
