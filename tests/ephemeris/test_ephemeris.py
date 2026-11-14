# ABOUTME: Tests for the ephemeris module (EPH-1, EPH-2) against recorded JPL Horizons replies
# ABOUTME: No network: a mock transport serves the recorded fixtures; one live test is marked slow

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from lunarnav.contracts import EphemerisProvider, GeoPoint, TimeWindow
from lunarnav.ephemeris import (
    EphemerisCache,
    HorizonsEphemerisProvider,
    HorizonsError,
    build_ephemeris_provider,
)
from lunarnav.ephemeris.horizons import (
    EARTH_ID,
    SUN_ID,
    _parse_time,
    parse_result,
    sample_times,
    split_chunks,
)

FIXTURES = Path(__file__).parent / "fixtures"
APOLLO_11 = GeoPoint(lat_deg=0.67408, lon_deg=23.47297)  # site used when recording the fixtures
T0 = datetime(2026, 12, 1, 0, 0, tzinfo=UTC)

# Known answers: first row of each recorded reply (Horizons, 2026-12-01 00:00 UTC, Apollo 11 site)
SUN_T0 = (268.648693, -13.422167)
EARTH_T0 = (272.422555, 73.109032)


def _fixture_result(target: str) -> str:
    name = {SUN_ID: "sun", EARTH_ID: "earth"}[target]
    return json.loads((FIXTURES / f"horizons_apollo11_{name}_20261201.json").read_text())["result"]


class FakeHorizons:
    """Mock transport: answers from the fixtures, keeping only rows inside START..STOP."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        p = request.url.params
        start = datetime.fromisoformat(p["START_TIME"].strip("'")).replace(tzinfo=UTC)
        stop = datetime.fromisoformat(p["STOP_TIME"].strip("'")).replace(tzinfo=UTC)
        text = _fixture_result(p["COMMAND"].strip("'"))
        head, rest = text.split("$$SOE")
        body, tail = rest.split("$$EOE")
        keep = [
            line
            for line in body.strip().splitlines()
            if start <= _parse_time(line.split(",")[0].strip()) <= stop
        ]
        result = head + "$$SOE\n" + "\n".join(keep) + "\n$$EOE" + tail
        return httpx.Response(200, json={"result": result})


def _provider(tmp_path: Path | None, fake: FakeHorizons, **kw) -> HorizonsEphemerisProvider:
    return HorizonsEphemerisProvider(
        cache_dir=tmp_path, client=httpx.Client(transport=httpx.MockTransport(fake)), **kw
    )


def _window(minutes: int = 60, step: float = 10, start: datetime = T0) -> TimeWindow:
    return TimeWindow(
        start_utc=start, end_utc=start + timedelta(minutes=minutes), step_minutes=step
    )


# --- horizons helpers ------------------------------------------------------------------------


def test_parse_result_reads_recorded_rows() -> None:
    rows = parse_result(_fixture_result(SUN_ID))
    assert len(rows.times_utc) == 7
    assert rows.times_utc[0] == T0
    assert rows.times_utc[-1] == T0 + timedelta(hours=1)
    assert (rows.azimuth_deg[0], rows.elevation_deg[0]) == SUN_T0


def test_parse_result_raises_on_horizons_error_text() -> None:
    with pytest.raises(HorizonsError, match=r"max\. is 90000"):
        parse_result("\nOutput length exceeded, 109800 times requested, max. is 90000\n")


def test_parse_time_handles_minutes_and_seconds() -> None:
    assert _parse_time("2026-Dec-01 00:10") == datetime(2026, 12, 1, 0, 10, tzinfo=UTC)
    assert _parse_time("2027-Jan-05 23:59:30") == datetime(2027, 1, 5, 23, 59, 30, tzinfo=UTC)


def test_sample_times_inclusive_end_and_utc_conversion() -> None:
    cet = timezone(timedelta(hours=1))
    w = TimeWindow(
        start_utc=datetime(2026, 12, 1, 1, 0, tzinfo=cet),  # = 00:00 UTC
        end_utc=datetime(2026, 12, 1, 1, 25, tzinfo=cet),
        step_minutes=10,
    )
    assert sample_times(w) == [T0, T0 + timedelta(minutes=10), T0 + timedelta(minutes=20)]


def test_sample_times_rejects_fractional_step() -> None:
    with pytest.raises(ValueError, match="whole number of minutes"):
        sample_times(_window(step=2.5))


def test_split_chunks_balanced_and_complete() -> None:
    times = list(range(7))
    chunks = split_chunks(times, max_rows=3)
    assert [len(c) for c in chunks] == [3, 2, 2]
    assert [t for c in chunks for t in c] == times
    assert split_chunks(times, max_rows=100) == [times]


def test_one_year_at_10_min_is_one_request_per_body() -> None:
    # 365 days * 144 samples/day + 1 = 52,561 rows, under the 80,000-row chunk limit
    times = sample_times(_window(minutes=365 * 24 * 60))
    assert len(times) == 52_561
    assert len(split_chunks(times)) == 1


# --- provider (EPH-1) ------------------------------------------------------------------------


def test_provider_matches_recorded_horizons_values(tmp_path: Path) -> None:
    fake = FakeHorizons()
    s = _provider(tmp_path, fake).sun_earth(APOLLO_11, _window())
    assert s.times_utc == sample_times(_window())
    # Tolerance: exact to the 1e-6 deg Horizons prints; we pass its values through unchanged.
    assert (s.sun_azimuth_deg[0], s.sun_elevation_deg[0]) == SUN_T0
    assert (s.earth_azimuth_deg[0], s.earth_elevation_deg[0]) == EARTH_T0
    assert all(0.0 <= a < 360.0 for a in s.sun_azimuth_deg + s.earth_azimuth_deg)
    assert "Horizons" in s.source


def test_provider_sends_topocentric_moon_query(tmp_path: Path) -> None:
    fake = FakeHorizons()
    _provider(tmp_path, fake).sun_earth(APOLLO_11, _window())
    targets = sorted(r.url.params["COMMAND"] for r in fake.requests)
    assert targets == ["'10'", "'399'"]
    p = fake.requests[0].url.params
    assert p["CENTER"] == "'coord@301'"
    assert p["SITE_COORD"] == "'23.472970,0.674080,0.0000'"  # E-lon, lat, height km
    assert p["QUANTITIES"] == "'4'"
    assert p["STEP_SIZE"] == "'10m'"


def test_provider_splits_long_windows(tmp_path: Path) -> None:
    fake = FakeHorizons()
    s = _provider(tmp_path, fake, max_rows=3).sun_earth(APOLLO_11, _window())
    assert len(fake.requests) == 6  # 3 chunks x (Sun, Earth)
    whole = _provider(None, FakeHorizons()).sun_earth(APOLLO_11, _window())
    assert s.sun_elevation_deg == whole.sun_elevation_deg
    assert s.earth_azimuth_deg == whole.earth_azimuth_deg


def test_provider_single_sample_window(tmp_path: Path) -> None:
    s = _provider(tmp_path, FakeHorizons()).sun_earth(APOLLO_11, _window(minutes=5))
    assert s.times_utc == [T0]
    assert (s.sun_azimuth_deg[0], s.sun_elevation_deg[0]) == SUN_T0


def test_provider_reports_missing_samples(tmp_path: Path) -> None:
    late = T0 + timedelta(hours=2)  # outside the recorded hour: the fake returns no rows
    with pytest.raises(HorizonsError, match="lacks"):
        _provider(tmp_path, FakeHorizons()).sun_earth(APOLLO_11, _window(start=late))


def test_provider_wraps_http_errors(tmp_path: Path) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="maintenance")

    p = HorizonsEphemerisProvider(
        cache_dir=tmp_path, client=httpx.Client(transport=httpx.MockTransport(down))
    )
    with pytest.raises(HorizonsError, match="503"):
        p.sun_earth(APOLLO_11, _window())


def test_provider_satisfies_port() -> None:
    provider: EphemerisProvider = HorizonsEphemerisProvider(cache_dir=None)
    assert callable(provider.sun_earth)


# --- cache (EPH-2) ---------------------------------------------------------------------------


def test_second_call_makes_no_request(tmp_path: Path) -> None:
    fake = FakeHorizons()
    p = _provider(tmp_path, fake)
    first = p.sun_earth(APOLLO_11, _window())
    n = len(fake.requests)
    second = p.sun_earth(APOLLO_11, _window())
    assert len(fake.requests) == n
    assert second == first


def test_cache_serves_sub_window_on_same_grid(tmp_path: Path) -> None:
    fake = FakeHorizons()
    p = _provider(tmp_path, fake)
    full = p.sun_earth(APOLLO_11, _window())
    n = len(fake.requests)
    sub = p.sun_earth(APOLLO_11, _window(minutes=20, start=T0 + timedelta(minutes=30)))
    assert len(fake.requests) == n
    assert sub.times_utc == full.times_utc[3:6]
    assert sub.earth_elevation_deg == full.earth_elevation_deg[3:6]


def test_cache_misses_other_grid_site_or_step(tmp_path: Path) -> None:
    fake = FakeHorizons()
    _provider(tmp_path, fake).sun_earth(APOLLO_11, _window())
    cache = EphemerisCache(tmp_path)
    assert cache.get(APOLLO_11, _window(minutes=20, start=T0 + timedelta(minutes=5))) is None
    assert cache.get(APOLLO_11, _window(step=15)) is None  # 10 does not divide 15
    assert cache.get(GeoPoint(lat_deg=0.0, lon_deg=23.47297), _window()) is None
    assert cache.get(APOLLO_11, _window(minutes=70)) is None  # extends past the cached end


def test_cache_serves_coarser_step_by_striding(tmp_path: Path) -> None:
    fake = FakeHorizons()
    full = _provider(tmp_path, fake).sun_earth(APOLLO_11, _window())
    coarse = EphemerisCache(tmp_path).get(APOLLO_11, _window(step=20))
    assert coarse is not None
    assert coarse.times_utc == full.times_utc[::2]
    assert coarse.sun_elevation_deg == full.sun_elevation_deg[::2]


def test_one_minute_window_works(tmp_path: Path) -> None:
    # The globe asks for a 1-minute window at every date change (default step 60 -> one sample).
    p = _provider(tmp_path, FakeHorizons())
    one = p.sun_earth(GeoPoint(lat_deg=0.0, lon_deg=0.0), _window(minutes=1, step=60))
    assert one.times_utc == [T0]
    assert len(one.sun_azimuth_deg) == len(one.earth_elevation_deg) == 1


def test_build_ephemeris_provider_returns_port() -> None:
    provider = build_ephemeris_provider()
    assert isinstance(provider, HorizonsEphemerisProvider)


# --- live (network) --------------------------------------------------------------------------


@pytest.mark.slow
def test_live_horizons_matches_recording(tmp_path: Path) -> None:
    s = HorizonsEphemerisProvider(cache_dir=None).sun_earth(APOLLO_11, _window())
    assert s.sun_azimuth_deg[0] == pytest.approx(SUN_T0[0], abs=1e-5)
    assert s.sun_elevation_deg[0] == pytest.approx(SUN_T0[1], abs=1e-5)
    assert s.earth_elevation_deg[0] == pytest.approx(EARTH_T0[1], abs=1e-5)
