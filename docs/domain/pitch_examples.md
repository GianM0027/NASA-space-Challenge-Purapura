<!-- ABOUTME: Measured examples for the pitch (problem slide), with the exact inputs to reproduce them in the app -->
<!-- ABOUTME: Owner: Michael. Every number comes from the engine (JPL Horizons ephemerides, LOLA terrain) -->

# Pitch examples

## Problem slide: Shackleton floor vs rim (chosen by the team)

"10 km apart: 0 % Sun versus 90 %. But where the Sun is, the ground is too steep."

| | Shackleton floor | Shackleton rim, 10.5 km away |
|---|---|---|
| Coordinates (lat, lon) | -89.67, 129.78 | -89.37518, 106.70877 |
| Height | -2789 m | +1183 m |
| Sun visible | 0 % (dark all 14 days) | 90 % (longest darkness 33 h) |
| Earth visible | 0 % | 71 % |
| Landing slope (100 m disk) | 9.6 deg | 20.9 deg (Artemis limit 10 deg) |

Alternative rim point, closer to a landable site: -89.74077, 58.95593: Sun 84 %, Earth 80 %, landing
slope 11.3 deg.

**Inputs to reproduce** (in the app: type the coordinates with all their decimals in the coordinates
box; a click on the globe or rounded coordinates give different numbers, because light and shadow
change within a few hundred meters on the rim):

- window 2026-11-20 00:00 UTC to 2026-12-04 00:00 UTC, step 60 min;
- landing precision 100 m, operating range 0;
- observer height 2 m (no crewed archetype active);
- engine: JPL Horizons ephemerides, LOLA LDEM_85S_20M (20 m) terrain, measured 2026-11-15.

Crater center: IAU/USGS Gazetteer of Planetary Nomenclature, Shackleton (-89.67, 129.78, 20.92 km),
https://planetarynames.wr.usgs.gov/Feature/5450. The rim point is 10.5 km from it toward azimuth
315 deg (great circle on the 1737.4 km sphere).

Caveat for Q&A: the values hold for this 14-day window; polar light changes with the season, but the
floor of Shackleton is a permanently shadowed region, so the contrast stays.
