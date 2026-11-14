# ABOUTME: End-to-end check of the ephemeris chain against an independent historical source
# ABOUTME: Sun and Earth alt/az at the six Apollo landings (ALSJ table), recorded Horizons replies

"""Apollo landing Sun/Earth directions vs the Apollo Lunar Surface Journal (ALSJ).

Reference: ALSJ "Scotti_AltAz.txt",
https://www.nasa.gov/wp-content/uploads/static/history/alsj/Scotti_AltAz.txt
(landing times from Orloff, Apollo by the Numbers, NASA SP-2000-4029; directions interpolated
from the Nautical Almanac lunar ephemeris). Site coordinates are the table's own, so the test
checks time scale, longitude convention, frame and az/el geometry, not the catalog coordinates.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from lunarnav.contracts import GeoPoint, TimeWindow
from lunarnav.ephemeris import HorizonsEphemerisProvider

FIXTURE = Path(__file__).parent / "fixtures" / "horizons_apollo_landings.json"

# mission: (E-lon, lat, landing UT, Earth alt, Earth az, Sun alt, Sun az), degrees, from ALSJ
ALSJ = {
    "apollo-11": (23.4333, 0.6875, "1969-07-20T20:17:39", 59.43, 272.16, 10.65, 88.81),
    "apollo-12": (-23.3856, -3.1975, "1969-11-19T06:54:36", 61.56, 86.95, 5.19, 91.16),
    "apollo-14": (-17.4653, -3.6733, "1971-02-05T09:18:13", 66.10, 96.70, 10.36, 89.54),
    "apollo-15": (3.6528, 26.1008, "1971-07-30T22:16:29", 69.28, 203.00, 12.05, 95.73),
    "apollo-16": (15.5144, -8.9914, "1972-04-21T02:23:35", 77.16, 319.70, 14.76, 86.01),
    "apollo-17": (30.7658, 20.1653, "1972-12-11T19:54:58", 45.52, 240.88, 13.33, 95.83),
}

# Tolerances, degrees. Sun: the table is interpolated from the Nautical Almanac (0.01 deg printed);
# observed differences <= 0.02. Earth elevation: the table uses the sub-Earth point (Moon-center
# direction) while we are topocentric; the parallax R_moon / d_earth = 1737.4 / ~384,400 km
# = 0.26 deg times sin(zenith angle) lowers our value, observed 0.05-0.22.
SUN_TOL = 0.05
EARTH_AZ_TOL = 0.15
EARTH_EL_TOL = 0.30


def _site_key(lon: float, lat: float) -> str:
    return f"'{lon:.6f},{lat:.6f},0.0000'"


def _transport() -> httpx.MockTransport:
    recorded = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_site = {_site_key(v[0], v[1]): k for k, v in ALSJ.items()}

    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.params
        mission = by_site[p["SITE_COORD"]]
        result = recorded[f"{mission}|{p['COMMAND'].strip(chr(39))}"]
        return httpx.Response(200, json={"result": result})

    return httpx.MockTransport(handler)


@pytest.mark.parametrize("mission", list(ALSJ))
def test_landing_directions_match_alsj(mission: str) -> None:
    lon, lat, ut, e_alt, e_az, s_alt, s_az = ALSJ[mission]
    t = datetime.fromisoformat(ut).replace(tzinfo=UTC)
    provider = HorizonsEphemerisProvider(
        cache_dir=None, client=httpx.Client(transport=_transport())
    )
    s = provider.sun_earth(
        GeoPoint(lat_deg=lat, lon_deg=lon),
        TimeWindow(start_utc=t, end_utc=t + timedelta(minutes=1), step_minutes=1),
    )
    assert s.times_utc[0] == t
    assert s.sun_elevation_deg[0] == pytest.approx(s_alt, abs=SUN_TOL)
    assert s.sun_azimuth_deg[0] == pytest.approx(s_az, abs=SUN_TOL)
    assert s.earth_azimuth_deg[0] == pytest.approx(e_az, abs=EARTH_AZ_TOL)
    assert s.earth_elevation_deg[0] == pytest.approx(e_alt, abs=EARTH_EL_TOL)
    assert s.earth_elevation_deg[0] <= e_alt  # topocentric parallax only lowers the Earth


def test_catalog_has_the_same_landing_times() -> None:
    sites = json.loads(
        (Path(__file__).parents[2] / "data" / "catalog" / "sites.json").read_text(encoding="utf-8")
    )
    times = {s["id"]: s["landing_date_utc"] for s in sites}
    for mission, (*_, ut, _ealt, _eaz, _salt, _saz) in ALSJ.items():
        assert times[mission] == ut + "Z"
