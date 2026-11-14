# ABOUTME: Tests of the sky state (subsolar and sub-Earth points) from an ephemeris provider
# ABOUTME: Owner: Gian; known answers from hand-built directions and from the toy placeholder model

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from lunarnav.api.main import build_app
from lunarnav.api.services import SYNODIC_MONTH_DAYS, ExampleEphemerisProvider
from lunarnav.api.sky import sky_state, sub_point_from_origin
from lunarnav.api.wiring import build_services
from lunarnav.contracts import SkyState

EPOCH = datetime(2000, 1, 1, tzinfo=UTC)


def test_body_at_zenith_of_origin_has_sub_point_at_origin() -> None:
    assert sub_point_from_origin(azimuth_deg=0.0, elevation_deg=90.0) == pytest.approx((0.0, 0.0))


def test_body_on_northern_horizon_is_over_the_north_pole() -> None:
    lat, _ = sub_point_from_origin(azimuth_deg=0.0, elevation_deg=0.0)
    assert lat == pytest.approx(90.0)


def test_body_due_east_at_60_elevation_is_30_degrees_east() -> None:
    assert sub_point_from_origin(azimuth_deg=90.0, elevation_deg=60.0) == pytest.approx((0.0, 30.0))


def test_body_due_west_below_horizon_is_on_the_western_far_side() -> None:
    # 30 degrees below the western horizon: 90 + 30 = 120 degrees west of the origin.
    assert sub_point_from_origin(azimuth_deg=270.0, elevation_deg=-30.0) == pytest.approx(
        (0.0, -120.0)
    )


def test_longitude_is_wrapped_into_minus180_180() -> None:
    _, lon = sub_point_from_origin(azimuth_deg=90.0, elevation_deg=-90.0)
    assert -180.0 <= lon < 180.0


def test_sky_state_matches_the_toy_model() -> None:
    # A quarter of a synodic month after the toy epoch the subsolar point is 90 degrees west;
    # the toy sub-Earth point is always (0, 0). The instant is truncated to the whole minute,
    # which moves the subsolar point by at most 360 deg / (29.53 d * 1440 min/d) = 0.0085 deg.
    time = EPOCH + timedelta(days=SYNODIC_MONTH_DAYS / 4)
    state = sky_state(ExampleEphemerisProvider(), time)
    assert state.time_utc == time.replace(second=0, microsecond=0)
    assert state.subsolar.lat_deg == pytest.approx(0.0, abs=1e-6)
    assert state.subsolar.lon_deg == pytest.approx(-90.0, abs=0.0085)
    assert state.sub_earth.lat_deg == pytest.approx(0.0, abs=1e-6)
    assert state.sub_earth.lon_deg == pytest.approx(0.0, abs=1e-6)


def test_sky_endpoint() -> None:
    client = TestClient(build_app(*build_services(use_real=False)))
    response = client.get("/api/sky", params={"time_utc": "2027-01-01T00:00:00Z"})
    assert response.status_code == 200
    SkyState.model_validate(response.json())


def test_sky_endpoint_rejects_naive_time() -> None:
    client = TestClient(build_app(*build_services(use_real=False)))
    assert client.get("/api/sky", params={"time_utc": "2027-01-01T00:00:00"}).status_code == 422


def test_sky_state_truncates_to_the_whole_minute() -> None:
    time = datetime(2027, 1, 1, 12, 30, 45, 123456, tzinfo=UTC)
    state = sky_state(ExampleEphemerisProvider(), time)
    assert state.time_utc == datetime(2027, 1, 1, 12, 30, tzinfo=UTC)
