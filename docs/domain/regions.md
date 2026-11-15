<!-- ABOUTME: Named lunar regions with sourced latitude/longitude bounds, for the AI search scope (spec AI-7) -->
<!-- ABOUTME: Owner: Michael. Machine-readable bounds live in the JSON block between the REGIONS_JSON markers -->

# Named regions (AI-7)

When a request names a region ("near the south pole", "far side", "equatorial"), the LLM picks
**only the region id**; code applies the bounds below as the search scope. Every bound has a
source (Michael's decisions, 2026-11-16).

| id | bounds | source |
|----|--------|--------|
| `south-pole` | latitude <= -84 deg | NASA: Artemis candidate regions lie "within six degrees of latitude of the lunar South Pole" (2022-08-19 release); HLS Overview 2025, p. 21: "Land within 6 deg latitude of the South Pole" |
| `south-polar-region` | latitude <= -80 deg | Mazarico et al. 2011, Icarus 211, 1066-1081: LOLA illumination study of the polar regions down to 80 deg latitude (study extent). For generic requests "near the south pole"; `south-pole` is for "at the south pole" (Michael's decision) |
| `north-pole` | latitude >= 80 deg | Mazarico et al. 2011, Icarus 211, 1066-1081: LOLA illumination study of both polar regions down to 80 deg latitude (a study extent, not an official definition; NASA gives no north-pole definition) |
| `equatorial` | -5 deg <= latitude <= 5 deg | NASA 1967 technical memorandum: the Apollo zone of interest spans 5 deg north and south of the lunar equator |
| `apollo-zone` | -5 <= latitude <= 5 deg and -45 <= longitude <= 45 deg | same NASA 1967 memorandum: Apollo zone bounded by 5 deg N/S latitude and 45 deg E/W longitude |
| `near-side` | -90 <= longitude <= 90 deg | NASA LRO lunar coordinate white paper (2008): Mean Earth / Polar Axis frame, prime meridian = mean direction to Earth, so the Earth-facing hemisphere is centered on longitude 0 |
| `far-side` | longitude >= 90 or <= -90 deg | same white paper: the hemisphere opposite the mean Earth direction |

Notes:

- Near and far side are the geometric hemispheres. Libration lets an observer on Earth see about
  59 % of the Moon over time, so sites just beyond +/-90 deg can see the Earth low on the horizon
  part of the time; the engine computes that exactly, the region only sets the search scope.
- Two south-polar scopes (Michael's decision): "at the south pole" -> `south-pole` (Artemis band,
  <= -84 deg); "near the south pole" -> `south-polar-region` (<= -80 deg). The wider one adds IM-1
  (-80.13 deg) and the approximate point of "Peak near Cabeus B" (IAU center of Cabeus B, -82.26 deg),
  which the Artemis band leaves out although NASA places that region within 6 deg.
- Not included: a "mid-latitude" band or named maria: no citable bounds were chosen. Add rows only
  with a source.

## How to read the JSON (for the AI module)

Extract the block with this regex (DOTALL); it matches exactly once:

```
<!--\s*REGIONS_JSON_BEGIN\s*-->\s*```json\s*(.*?)\s*```\s*<!--\s*REGIONS_JSON_END\s*-->
```

Schema agreed with Gian: each region has `id`, `label`, `summary` (the sentence the LLM reads to
recognize the region; the LLM sees only `id` and `summary`), `latitude_min_deg`,
`latitude_max_deg`, `lon_min_deg`, `lon_max_deg` (degrees, south negative, east-positive longitude
in [-180, 180), inclusive; `null` = no limit) and `source` (citations for every bound).
**`far-side` crosses +/-180: `lon_min_deg` 90 > `lon_max_deg` -90 means 90..180 plus -180..-90.**

`tests/domain/test_regions.py` checks the block, the bounds and the AI-7 acceptance case on the
catalog: "near the south pole" keeps only south-polar sites (<= -80 deg; not Chang'e 4, Chang'e 6,
Luna 13 or Chandrayaan-3), and "at the south pole" only those within the Artemis band.

<!-- REGIONS_JSON_BEGIN -->
```json
{
  "schema_version": 1,
  "regions": [
    {
      "id": "south-pole",
      "label": "Lunar south pole",
      "summary": "At the lunar south pole: within 6 degrees of the pole, the band of NASA's Artemis candidate landing regions. Use for 'at the south pole' or 'Artemis region'.",
      "latitude_min_deg": null,
      "latitude_max_deg": -84,
      "lon_min_deg": null,
      "lon_max_deg": null,
      "source": "NASA 2022-08-19, 'NASA Identifies Candidate Regions for Landing Next Americans on Moon': regions within six degrees of latitude of the lunar South Pole, https://www.nasa.gov/news-release/nasa-identifies-candidate-regions-for-landing-next-americans-on-Moon/; NASA HLS Overview, Space Apps 2025, p. 21: land within 6 deg latitude of the South Pole, https://ntrs.nasa.gov/api/citations/20250009323/downloads/ArtemisOverview2025IntSPAPPSChallenge.pdf"
    },
    {
      "id": "south-polar-region",
      "label": "Near the lunar south pole",
      "summary": "Near or around the lunar south pole: the south polar region down to 80 degrees south. Use for generic requests 'near the south pole' or 'south polar'.",
      "latitude_min_deg": null,
      "latitude_max_deg": -80,
      "lon_min_deg": null,
      "lon_max_deg": null,
      "source": "Mazarico et al. 2011, 'Illumination conditions of the lunar polar regions using LOLA topography', Icarus 211, 1066-1081: polar regions modelled down to 80 deg latitude (study extent, same bound as north-pole), https://pgda.gsfc.nasa.gov/products/69"
    },
    {
      "id": "north-pole",
      "label": "Lunar north pole",
      "summary": "Near or at the lunar north pole: the north polar region down to 80 degrees north.",
      "latitude_min_deg": 80,
      "latitude_max_deg": null,
      "lon_min_deg": null,
      "lon_max_deg": null,
      "source": "Mazarico et al. 2011, 'Illumination conditions of the lunar polar regions using LOLA topography', Icarus 211, 1066-1081: polar regions modelled down to 80 deg latitude (study extent; NASA gives no north-pole definition), https://pgda.gsfc.nasa.gov/products/69"
    },
    {
      "id": "equatorial",
      "label": "Equatorial band",
      "summary": "Near the lunar equator: within 5 degrees of latitude, all longitudes. Use for 'equatorial', 'near the equator', 'low latitude'.",
      "latitude_min_deg": -5,
      "latitude_max_deg": 5,
      "lon_min_deg": null,
      "lon_max_deg": null,
      "source": "NASA technical memorandum (1967): Apollo zone of interest bounded by 5 deg north and south latitude, https://ntrs.nasa.gov/api/citations/19680004281/downloads/19680004281.pdf"
    },
    {
      "id": "apollo-zone",
      "label": "Apollo zone",
      "summary": "The Apollo zone: within 5 degrees of the equator and 45 degrees of longitude from the center of the near side. Use for 'like the Apollo landings' or 'central near side'.",
      "latitude_min_deg": -5,
      "latitude_max_deg": 5,
      "lon_min_deg": -45,
      "lon_max_deg": 45,
      "source": "NASA technical memorandum (1967): Apollo zone bounded by 5 deg N/S latitude and 45 deg E/W longitude, https://ntrs.nasa.gov/api/citations/19680004281/downloads/19680004281.pdf"
    },
    {
      "id": "near-side",
      "label": "Near side",
      "summary": "The near side, the hemisphere always facing Earth (longitudes -90 to +90). Use for 'near side', 'Earth-facing side', 'visible side'.",
      "latitude_min_deg": null,
      "latitude_max_deg": null,
      "lon_min_deg": -90,
      "lon_max_deg": 90,
      "source": "NASA LRO Project, 'A Standardized Lunar Coordinate System for the Lunar Reconnaissance Orbiter and Lunar Datasets' (2008): Mean Earth/Polar Axis frame, prime meridian = mean Earth direction, so the Earth-facing hemisphere spans longitudes -90..90, https://science.nasa.gov/wp-content/uploads/2024/01/luncoordwhitepaper-10-08.pdf"
    },
    {
      "id": "far-side",
      "label": "Far side",
      "summary": "The far side, the hemisphere facing away from Earth (longitudes beyond +/-90, across 180). Use for 'far side', 'dark side', 'hidden side', 'back of the Moon'.",
      "latitude_min_deg": null,
      "latitude_max_deg": null,
      "lon_min_deg": 90,
      "lon_max_deg": -90,
      "source": "NASA LRO coordinate white paper (2008): hemisphere opposite the mean Earth direction (longitudes beyond +/-90, range wraps through 180), https://science.nasa.gov/wp-content/uploads/2024/01/luncoordwhitepaper-10-08.pdf"
    }
  ]
}
```
<!-- REGIONS_JSON_END -->
