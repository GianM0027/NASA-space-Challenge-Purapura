<!-- ABOUTME: Named lunar regions with sourced latitude/longitude bounds, for the AI search scope (spec AI-7) -->
<!-- ABOUTME: Owner: Michael. Machine-readable bounds live in the JSON block between the REGIONS_JSON markers -->

# Named regions (AI-7)

When a request names a region ("near the south pole", "far side", "equatorial"), the LLM picks
**only the region id**; code applies the bounds below as the search scope. Every bound has a
source (Michael's decisions, 2026-11-16).

| id | bounds | source |
|----|--------|--------|
| `south-pole` | latitude <= -84 deg | NASA: Artemis candidate regions lie "within six degrees of latitude of the lunar South Pole" (2022-08-19 release); HLS Overview 2025, p. 21: "Land within 6 deg latitude of the South Pole" |
| `north-pole` | latitude >= 80 deg | Mazarico et al. 2011, Icarus 211, 1066-1081: LOLA illumination study of both polar regions down to 80 deg latitude (a study extent, not an official definition; NASA gives no north-pole definition) |
| `equatorial` | -5 deg <= latitude <= 5 deg | NASA 1967 technical memorandum: the Apollo zone of interest spans 5 deg north and south of the lunar equator |
| `apollo-zone` | -5 <= latitude <= 5 deg and -45 <= longitude <= 45 deg | same NASA 1967 memorandum: Apollo zone bounded by 5 deg N/S latitude and 45 deg E/W longitude |
| `near-side` | -90 <= longitude <= 90 deg | NASA LRO lunar coordinate white paper (2008): Mean Earth / Polar Axis frame, prime meridian = mean direction to Earth, so the Earth-facing hemisphere is centered on longitude 0 |
| `far-side` | longitude >= 90 or <= -90 deg | same white paper: the hemisphere opposite the mean Earth direction |

Notes:

- Near and far side are the geometric hemispheres. Libration lets an observer on Earth see about
  59 % of the Moon over time, so sites just beyond +/-90 deg can see the Earth low on the horizon
  part of the time; the engine computes that exactly, the region only sets the search scope.
- Catalog consequences of `south-pole`: IM-1 (-80.13 deg) is "near the south pole" in common speech
  but outside the 6 deg band; the approximate point of "Peak near Cabeus B" (IAU center of Cabeus B,
  -82.26 deg) also falls outside, although NASA places the region itself within 6 deg.
- Not included: a south-polar region wider than the Artemis one, a "mid-latitude" band, or named
  maria: no citable bounds were chosen. Add rows only with a source.

## How to read the JSON (for the AI module)

Extract the block with this regex (DOTALL); it matches exactly once:

```
<!--\s*REGIONS_JSON_BEGIN\s*-->\s*```json\s*(.*?)\s*```\s*<!--\s*REGIONS_JSON_END\s*-->
```

Each region: `id`, `name`, `aliases` (words a user may write, for the LLM prompt), `lat_min_deg`,
`lat_max_deg` (inclusive; `null` = no bound), `lon_min_deg`, `lon_max_deg` (inclusive, east-positive
in [-180, 180); `null` = all longitudes). **When `lon_min_deg > lon_max_deg` the range wraps through
180 deg** (far side: 90..180 and -180..-90). `sources` maps each bound to its citation.

`tests/domain/test_regions.py` checks the block, the bounds and the AI-7 acceptance case on the
catalog: "near the south pole" keeps only sites at latitude <= -84 deg (not Chang'e 4, Chang'e 6 or
Luna 13).

<!-- REGIONS_JSON_BEGIN -->
```json
{
  "schema_version": 1,
  "regions": [
    {
      "id": "south-pole",
      "name": "Lunar south pole",
      "aliases": ["south pole", "south polar", "near the south pole", "Artemis region", "lunar south"],
      "lat_min_deg": -90,
      "lat_max_deg": -84,
      "lon_min_deg": null,
      "lon_max_deg": null,
      "sources": {
        "lat_max_deg": "NASA 2022-08-19, 'NASA Identifies Candidate Regions for Landing Next Americans on Moon': regions within six degrees of latitude of the lunar South Pole, https://www.nasa.gov/news-release/nasa-identifies-candidate-regions-for-landing-next-americans-on-Moon/; NASA HLS Overview, Space Apps 2025, p. 21: land within 6 deg latitude of the South Pole, https://ntrs.nasa.gov/api/citations/20250009323/downloads/ArtemisOverview2025IntSPAPPSChallenge.pdf",
        "lat_min_deg": "the pole itself"
      }
    },
    {
      "id": "north-pole",
      "name": "Lunar north pole",
      "aliases": ["north pole", "north polar", "near the north pole", "lunar north"],
      "lat_min_deg": 80,
      "lat_max_deg": 90,
      "lon_min_deg": null,
      "lon_max_deg": null,
      "sources": {
        "lat_min_deg": "Mazarico et al. 2011, 'Illumination conditions of the lunar polar regions using LOLA topography', Icarus 211, 1066-1081: polar regions modelled down to 80 deg latitude (study extent; NASA gives no north-pole definition), https://pgda.gsfc.nasa.gov/products/69",
        "lat_max_deg": "the pole itself"
      }
    },
    {
      "id": "equatorial",
      "name": "Equatorial band",
      "aliases": ["equatorial", "equator", "near the equator", "low latitude"],
      "lat_min_deg": -5,
      "lat_max_deg": 5,
      "lon_min_deg": null,
      "lon_max_deg": null,
      "sources": {
        "lat_min_deg": "NASA technical memorandum (1967): Apollo zone of interest bounded by 5 deg north and south latitude, https://ntrs.nasa.gov/api/citations/19680004281/downloads/19680004281.pdf",
        "lat_max_deg": "NASA technical memorandum (1967), as above"
      }
    },
    {
      "id": "apollo-zone",
      "name": "Apollo zone",
      "aliases": ["Apollo zone", "Apollo-like", "like the Apollo landings", "central near side"],
      "lat_min_deg": -5,
      "lat_max_deg": 5,
      "lon_min_deg": -45,
      "lon_max_deg": 45,
      "sources": {
        "lat_min_deg": "NASA technical memorandum (1967): Apollo zone bounded by 5 deg N/S latitude and 45 deg E/W longitude, https://ntrs.nasa.gov/api/citations/19680004281/downloads/19680004281.pdf",
        "lat_max_deg": "NASA technical memorandum (1967), as above",
        "lon_min_deg": "NASA technical memorandum (1967), as above",
        "lon_max_deg": "NASA technical memorandum (1967), as above"
      }
    },
    {
      "id": "near-side",
      "name": "Near side",
      "aliases": ["near side", "nearside", "Earth-facing side", "visible side"],
      "lat_min_deg": null,
      "lat_max_deg": null,
      "lon_min_deg": -90,
      "lon_max_deg": 90,
      "sources": {
        "lon_min_deg": "NASA LRO Project, 'A Standardized Lunar Coordinate System for the Lunar Reconnaissance Orbiter and Lunar Datasets' (2008): Mean Earth/Polar Axis frame, prime meridian = mean Earth direction, so the Earth-facing hemisphere spans longitudes -90..90, https://science.nasa.gov/wp-content/uploads/2024/01/luncoordwhitepaper-10-08.pdf",
        "lon_max_deg": "NASA LRO coordinate white paper (2008), as above"
      }
    },
    {
      "id": "far-side",
      "name": "Far side",
      "aliases": ["far side", "farside", "dark side", "hidden side", "back of the Moon"],
      "lat_min_deg": null,
      "lat_max_deg": null,
      "lon_min_deg": 90,
      "lon_max_deg": -90,
      "sources": {
        "lon_min_deg": "NASA LRO coordinate white paper (2008): hemisphere opposite the mean Earth direction (longitudes beyond +/-90, range wraps through 180), https://science.nasa.gov/wp-content/uploads/2024/01/luncoordwhitepaper-10-08.pdf",
        "lon_max_deg": "NASA LRO coordinate white paper (2008), as above"
      }
    }
  ]
}
```
<!-- REGIONS_JSON_END -->
