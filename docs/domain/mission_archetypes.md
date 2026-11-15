<!-- ABOUTME: Mission archetypes with sourced typical requirements, domain knowledge for the AI (spec AI-5) -->
<!-- ABOUTME: Owner: Michael. Machine-readable values live in the JSON block between the ARCHETYPES_JSON markers -->

# Mission archetypes (AI-5)

Domain knowledge for the AI module: typical requirements of a few mission types, so a request
like "a two-week robotic lander" or "a short crewed stay" can be turned into `MissionRequirements`.

Rules (Michael's decisions, 2026-11-14):

- **Only sourced values.** Every number in the JSON has an entry in `sources` for the same key.
  Where no citable number exists, the constraint is left out (meaning "not constrained") and the
  archetype says so in words.
- Values are **typical starting points** for the user to edit in the GUI, not limits of the engine.
- Observer height above ground follows decision D30 (2 m robotic, 10 m crewed lander).
- Durations in hours, distances in meters, angles in degrees (contract conventions).

### Slopes (Michael's decision)

- `max_slope_deg` is the **landing** slope: it must hold over the landing-precision disk, where the
  lander may touch down. It is the only hard slope constraint.
- The operations area is **not** filtered by its maximum slope: a site next to a steep crater wall
  is fine if crews or rovers can avoid the wall. NASA likewise shows slopes > 20 deg as areas
  excluded from EVAs (HLS Overview 2025, p. 24). Instead, `area.traverse_slope_limit_deg`
  (contract D32) is the vehicle limit used to report the **reachable share** of the operations
  area, shown to the user as information. No minimum share is set: no source gives one.
- Reachable, not just traversable: a cell counts only if a path from the landing point reaches it
  through cells below `traverse_slope_limit_deg` with a path length within `operating_range_m`.
  A steep wall across the disk therefore cuts off the far side, and a detour longer than the range
  makes an area unreachable even if it is connected.

### Darkness vs light (why both kinds of constraint exist)

- `min_illumination_fraction`: total share of time in sunlight (energy over the mission).
- `min_continuous_light_h`: longest uninterrupted sunlit period (a short mission that must be lit
  from start to end sets it to its whole duration).
- `max_continuous_dark_h` (contract field since D33): longest darkness the vehicle survives (battery or
  storage). For long missions that cannot avoid night, this is the survival constraint: a site can
  have 70 % light overall and still kill a rover with one 4-day shadow.

### Priority of criteria for the ranking (AI-2)

No archetype has a `priority` list, on purpose (Michael's decision, following Gian's rule "equal
weights rather than an invented order"):

- **Short crewed stay**: NASA lists continuous light for the whole stay, Earth visibility of at
  least 25 % and landing slope under 10 deg all as mandatory requirements (HLS Overview 2025,
  pp. 21, 25, 26) and does not say which matters more; NASA 2022 calls sunlight "critical" but does
  not rank it against communication. Ordering them would be our invention.
- **Long-duration outpost, polar rover, small robotic lander**: each sets a single weighted
  criterion, so an order means nothing.
- **Robotic ISRU**: no numeric criteria.

If a source ranking these criteria is found, add `"priority": [[...], [...]]` (groups from most to
least important, names from the seven ranking criteria, each once) and `sources["priority"]`.
## How to read the JSON (for the AI module)

The JSON block at the end of this file is the single source of the numbers. It sits between two
HTML comments, ARCHETYPES_JSON_BEGIN and ARCHETYPES_JSON_END, that appear nowhere else. Extract it
with this regex (DOTALL); it matches exactly once:

```
<!--\s*ARCHETYPES_JSON_BEGIN\s*-->\s*```json\s*(.*?)\s*```\s*<!--\s*ARCHETYPES_JSON_END\s*-->
```

Structure of each archetype:

| Key | Meaning |
|-----|---------|
| `id`, `name`, `summary` | identifier, display name, one-paragraph description for the LLM |
| `mission_duration_h` | typical surface duration; set `window.end_utc = window.start_utc + duration` |
| `requirements` | a subset of `MissionRequirements` fields, valid as-is (`window` excluded); `area` includes `traverse_slope_limit_deg` and `observer_height_above_ground_m` (D30, D32) |
| `proposed_fields` | values for fields **not yet in the contract** (requested to Gian); ignore if unknown; empty today |
| `priority` | optional ranking order of criteria (none set, see above) |
| `sources` | key (field name, `area.<field>`, or `proposed_fields.<field>`) -> citation |
| `notes` | sourced qualitative constraints with no number |

`tests/domain/test_mission_archetypes.py` checks that the block extracts, parses, validates against
`MissionRequirements`, and that every number has a source.

## Archetypes in short

1. **Short crewed stay** (first Artemis crewed landing): 6.5-day stay near the south pole, lit for
   the whole stay, Earth visible for direct communication, landing within 100 m of the target,
   EVAs within 2 km. Source: NASA HLS overview for Space Apps 2025 and NASA's 2022 region release.
2. **Long-duration outpost** (Artemis Base Camp concept): month-long stays; no site avoids darkness,
   so early systems must store power for up to eight days. Source: NASA Artemis blog, 2020.
3. **Polar rover** (VIPER-class): about 100 Earth days in the polar summer, up to 20 km of driving,
   15 deg slopes, survives at most 50 h of darkness, needs line-of-sight to Earth. Source: NASA VIPER
   mission planning papers.
4. **Small robotic lander** (CLPS-class, e.g. Blue Ghost): operates one lunar day, about 14 Earth
   days, on solar power. Source: NASA Blue Ghost Mission 1 press kit. **Low and middle latitudes
   only** (Michael's decision): its "lit for the whole mission" constraint fits a sunrise-to-sunset
   lander like Blue Ghost (Mare Crisium, 18.6 deg N). Near the south pole no catalog site meets
   336 h of continuous light (engine, December 2027 to January 2028: best IM-2 with 322 h), so
   polar requests use the polar rover (survival = longest darkness) or no archetype.
5. **Robotic ISRU** (water-ice mining): qualitative only. The propellant plant sits in a highly
   illuminated area, the mine in a permanently shadowed region, not co-located with the customer;
   NASA states the exact illumination need depends on the technology. Source: Kleinhenz and
   Sanders, NASA, ASCEND 2022.

Not included: a communication relay archetype (not enough literature for a surface site; Michael's
decision, revisit if sources are found).

<!-- ARCHETYPES_JSON_BEGIN -->
```json
{
  "schema_version": 1,
  "archetypes": [
    {
      "id": "short-crewed-stay",
      "name": "Short crewed stay (first Artemis crewed landing)",
      "summary": "Crewed landing near the lunar south pole with a surface stay of about 6.5 days. The site must be lit for the whole stay, Earth must be visible for direct communication (no relay assumed), the lander must land within 100 m of its target on slopes under 10 deg, and EVAs within 2 km avoid slopes over 20 deg.",
      "mission_duration_h": 156,
      "requirements": {
        "area": {
          "landing_precision_m": 100,
          "operating_range_m": 2000,
          "traverse_slope_limit_deg": 20,
          "observer_height_above_ground_m": 10
        },
        "min_continuous_light_h": 156,
        "min_earth_visibility_fraction": 0.25,
        "max_slope_deg": 10,
        "latitude_max_deg": -84
      },
      "proposed_fields": {},
      "sources": {
        "mission_duration_h": "NASA 2022-08-19, 'NASA Identifies Candidate Regions for Landing Next Americans on Moon': sites with continuous access to sunlight throughout a 6.5-day period, https://www.nasa.gov/news-release/nasa-identifies-candidate-regions-for-landing-next-americans-on-Moon/",
        "min_continuous_light_h": "NASA, L. Ortiz, 'Artemis Human Landing System Overview', Space Apps 2025 (2025-10-04), p. 26: surface lit for the duration of the surface stay; duration 6.5 days per NASA 2022-08-19, https://ntrs.nasa.gov/api/citations/20250009323/downloads/ArtemisOverview2025IntSPAPPSChallenge.pdf",
        "min_earth_visibility_fraction": "NASA HLS Overview 2025, p. 21 (direct with Earth communication, no relay) and p. 25 (areas with Earth visibility < 25% removed)",
        "area.landing_precision_m": "NASA HLS Overview 2025, p. 21: 'Land within 100 m of a target'",
        "area.operating_range_m": "NASA HLS Overview 2025, p. 21: surface slope limit for EVA (2 km)",
        "max_slope_deg": "NASA HLS Overview 2025, p. 21: surface slope for landing (100 m) < 10 deg (applies to the landing-precision disk, see 'Slopes' above)",
        "latitude_max_deg": "NASA HLS Overview 2025, p. 21: land within 6 deg latitude of the South Pole",
        "area.traverse_slope_limit_deg": "NASA HLS Overview 2025, p. 21 and p. 24: surface slope limit for EVA (2 km) < 20 deg; steeper areas are excluded from EVAs, not from the site",
        "area.observer_height_above_ground_m": "Decision D30 (Glaser et al. 2014, Icarus 243, 78: 10 m case)"
      },
      "notes": [
        "Approach lighting along the descent trajectory is beneficial (NASA HLS Overview 2025, p. 27).",
        "Specific sites are chosen per launch date because lighting changes (NASA 2022-08-19)."
      ]
    },
    {
      "id": "long-duration-outpost",
      "name": "Long-duration outpost (Artemis Base Camp concept)",
      "summary": "Fixed south-polar habitat for month-long crew stays, growing to stays of up to two months. No location avoids darkness, so early power systems must store energy for up to eight days of darkness.",
      "mission_duration_h": 720,
      "requirements": {
        "area": {
          "observer_height_above_ground_m": 10
        },
        "max_continuous_dark_h": 192
      },
      "proposed_fields": {},
      "sources": {
        "mission_duration_h": "NASA Artemis blog 2020-10-28, 'Lunar Living: NASA's Artemis Base Camp Concept': habitat for a month-long stay, https://www.nasa.gov/blogs/artemis/2020/10/28/lunar-living-nasas-artemis-base-camp-concept/",
        "area.observer_height_above_ground_m": "Decision D30 (Glaser et al. 2014, Icarus 243, 78: 10 m case)",
        "max_continuous_dark_h": "NASA Artemis blog 2020-10-28: capability to store power for up to eight days (8 x 24 h)"
      },
      "notes": [
        "Long-term goal: stays of up to two months (NASA Artemis blog 2020-10-28).",
        "A fission power unit would remove the dependence on sunlight (NASA Artemis blog 2020-10-28)."
      ]
    },
    {
      "id": "polar-rover",
      "name": "Polar rover (VIPER-class)",
      "summary": "Solar-powered rover prospecting for water ice near the south pole during the polar summer. Limited battery: it can survive about 50 hours of darkness. Needs line-of-sight communication with Earth, drives up to 20 km and climbs slopes up to 15 deg. Its landing slope depends on the delivery lander and is not given.",
      "mission_duration_h": 2400,
      "requirements": {
        "area": {
          "operating_range_m": 20000,
          "traverse_slope_limit_deg": 15,
          "observer_height_above_ground_m": 2
        },
        "max_continuous_dark_h": 50
      },
      "proposed_fields": {},
      "sources": {
        "mission_duration_h": "NASA, T. Fong, 'Volatiles Investigating Polar Exploration Rover' (2026-04-29), p. 22: lunar summer season ~100 Earth days max, https://ntrs.nasa.gov/api/citations/20260002876/downloads/viper-2026-04-29_v2.pdf",
        "area.operating_range_m": "NASA VIPER 2026-04-29, p. 22: 20 km max drive distance (design limit)",
        "area.traverse_slope_limit_deg": "NASA VIPER 2026-04-29, p. 22: 15 deg slopes (design limit)",
        "area.observer_height_above_ground_m": "Decision D30 (Glaser et al. 2014, Icarus 243, 78: 2 m case)",
        "max_continuous_dark_h": "NASA, VIPER mission planning, SpaceOps 2022, p. 3: dark survivability 50 hrs in minimal power mode, https://ntrs.nasa.gov/api/citations/20220008301/downloads/2022-06-02-spaceops-viper-planning.pdf"
      },
      "notes": [
        "Line-of-sight data communications to Earth are required (NASA VIPER 2026-04-29, p. 22); no minimum fraction is given.",
        "Science stops must be in sunlight except planned entries into permanent shadow (NASA SpaceOps 2022, p. 17)."
      ]
    },
    {
      "id": "small-robotic-lander",
      "name": "Small robotic lander (CLPS-class)",
      "summary": "Commercial solar-powered lander carrying science payloads at low or middle latitudes, operating for one lunar day (about 14 Earth days) from sunrise to sunset. NOT for the polar regions (beyond 80 degrees latitude), where the Sun grazes the horizon and terrain shadows break the daylight: for polar requests use the polar rover or no archetype.",
      "mission_duration_h": 336,
      "requirements": {
        "min_continuous_light_h": 336,
        "area": {
          "observer_height_above_ground_m": 2
        }
      },
      "proposed_fields": {},
      "sources": {
        "mission_duration_h": "NASA, Blue Ghost Mission 1 press kit (2025-01), p. 4: operate on the surface for a lunar day (about 14 Earth days), https://www.nasa.gov/wp-content/uploads/2025/01/np-2025-01-001-jsc-clps-firefly-press-kit-screen-508-1-10-25-final.pdf",
        "min_continuous_light_h": "NASA Blue Ghost press kit, p. 4: solar-powered operations for a lunar day (about 14 Earth days)",
        "area.observer_height_above_ground_m": "Decision D30 (Glaser et al. 2014, Icarus 243, 78: 2 m case)"
      },
      "notes": []
    },
    {
      "id": "robotic-isru",
      "name": "Robotic ISRU (water-ice mining)",
      "summary": "Robotic production of propellant from polar water ice. The propellant plant sits in a highly illuminated area for solar power; the mine is in a permanently shadowed region where surface ice is stable; the plant is not co-located with the customer site. No numeric thresholds are published: the exact illumination need depends on the ISRU technology and power architecture.",
      "requirements": {},
      "proposed_fields": {},
      "sources": {},
      "notes": [
        "Plant in a highly illuminated region; mine in a PSR with surface ice stability; plant not co-located with the customer (Kleinhenz and Sanders, NASA, ASCEND 2022, p. 4, https://ntrs.nasa.gov/api/citations/20220012754/downloads/Kleinhenz_ASCEND2022_AretmisRegionISRUeval_inpersonv3.pdf)."
      ]
    }
  ]
}
```
<!-- ARCHETYPES_JSON_END -->
