<!-- ABOUTME: Scripted natural-language requests with expected MissionRequirements, for testing the AI (AI-1) -->
<!-- ABOUTME: Owner: Michael. Expected values come from mission_archetypes.md; JSON between EXAMPLES_JSON markers -->

# Example requests for the AI (AI-1 acceptance)

Spec AI-1 asks that "5 scripted requests produce valid requirements". These 8 requests, written by
Michael (domain), give the input text and the expected `MissionRequirements`, so the AI module can
be tested on realistic cases. Values come from [mission_archetypes.md](mission_archetypes.md).

## How to check an AI answer ("fields + values", Michael's decision)

For each request:

1. **Expected fields with values**: every field in `expect.requirements` (and `area.<field>`) must be
   set, equal to the expected value within the tolerance below. `expect.mission_duration_h` checks
   the window length (`end_utc - start_utc`). `expect.proposed_fields` applies once Gian adds those
   fields to the contract; skip them until then.
2. **No invented constraints**: every other numeric field of `MissionRequirements` must be unset
   (`None`). This catches numbers the LLM makes up.
3. `message_must_mention`: words the answer message must contain (case-insensitive), e.g. to say
   that a requested constraint cannot be evaluated.
4. `rationale_required`: the AI must explain its choice in `rationale` (non-empty).

Tolerances: fractions +/- 0.01; durations +/- 1 h; every other number +/- 2 %.

The JSON block sits between the HTML comments EXAMPLES_JSON_BEGIN and EXAMPLES_JSON_END; extract it
with this regex (DOTALL), which matches exactly once:

```
<!--\s*EXAMPLES_JSON_BEGIN\s*-->\s*```json\s*(.*?)\s*```\s*<!--\s*EXAMPLES_JSON_END\s*-->
```

`tests/domain/test_example_requests.py` checks the block parses, every expectation validates
against `MissionRequirements`, and the normal cases match the archetype values.

## The requests

| id | kind | request |
|----|------|---------|
| R1 | normal | Plan a short crewed stay near the lunar south pole, Artemis style. |
| R2 | normal | Where could astronauts live for a month in a long-duration outpost? |
| R3 | normal | A solar-powered rover prospecting for water ice near the south pole during the polar summer. |
| R4 | normal | A small commercial lander that only needs to work for one lunar day. |
| R5 | normal | We want to mine water ice and make propellant robotically. |
| R6 | explicit numbers | A small lander for one lunar day, but it must see the Sun at least 80% of the time and land on slopes under 5 degrees. |
| R7 | vague | Find me a good place for a Moon base. |
| R8 | out of domain | A one-week crewed landing near the south pole where the surface stays warmer than -50 C and the soil is rich in titanium. |

Notes on the hard cases:

- **R6**: the user's numbers win over the archetype (illumination 80 %, slope 5 deg); what the user
  did not say comes from the archetype (one lunar day, lit throughout).
- **R7**: the AI picks the long-duration outpost and must say so in `rationale`; no numbers beyond
  the archetype's.
- **R8**: "one week" is the user's duration (168 h), so continuous light covers 168 h; crewed
  landing values come from the archetype. Temperature and soil composition cannot be evaluated by
  the engine: no field, and the message must say so instead of inventing anything.

<!-- EXAMPLES_JSON_BEGIN -->
```json
{
  "schema_version": 1,
  "requests": [
    {
      "id": "R1",
      "kind": "normal",
      "text": "Plan a short crewed stay near the lunar south pole, Artemis style.",
      "expected_archetype": "short-crewed-stay",
      "expect": {
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
        "proposed_fields": {}
      },
      "message_must_mention": [],
      "rationale_required": true
    },
    {
      "id": "R2",
      "kind": "normal",
      "text": "Where could astronauts live for a month in a long-duration outpost?",
      "expected_archetype": "long-duration-outpost",
      "expect": {
        "mission_duration_h": 720,
        "requirements": {
          "area": {
            "observer_height_above_ground_m": 10
          }
        },
        "proposed_fields": {
          "max_continuous_dark_h": 192
        }
      },
      "message_must_mention": [],
      "rationale_required": true
    },
    {
      "id": "R3",
      "kind": "normal",
      "text": "A solar-powered rover prospecting for water ice near the south pole during the polar summer.",
      "expected_archetype": "polar-rover",
      "expect": {
        "mission_duration_h": 2400,
        "requirements": {
          "area": {
            "operating_range_m": 20000,
            "traverse_slope_limit_deg": 15,
            "observer_height_above_ground_m": 2
          }
        },
        "proposed_fields": {
          "max_continuous_dark_h": 50
        }
      },
      "message_must_mention": [],
      "rationale_required": true
    },
    {
      "id": "R4",
      "kind": "normal",
      "text": "A small commercial lander that only needs to work for one lunar day.",
      "expected_archetype": "small-robotic-lander",
      "expect": {
        "mission_duration_h": 336,
        "requirements": {
          "min_continuous_light_h": 336,
          "area": {
            "observer_height_above_ground_m": 2
          }
        },
        "proposed_fields": {}
      },
      "message_must_mention": [],
      "rationale_required": true
    },
    {
      "id": "R5",
      "kind": "normal",
      "text": "We want to mine water ice and make propellant robotically.",
      "expected_archetype": "robotic-isru",
      "expect": {
        "requirements": {},
        "proposed_fields": {}
      },
      "message_must_mention": [],
      "rationale_required": true
    },
    {
      "id": "R6",
      "kind": "explicit-numbers",
      "text": "A small lander for one lunar day, but it must see the Sun at least 80% of the time and land on slopes under 5 degrees.",
      "expected_archetype": "small-robotic-lander",
      "expect": {
        "mission_duration_h": 336,
        "requirements": {
          "min_continuous_light_h": 336,
          "min_illumination_fraction": 0.8,
          "max_slope_deg": 5,
          "area": {
            "observer_height_above_ground_m": 2
          }
        },
        "proposed_fields": {}
      },
      "message_must_mention": [],
      "rationale_required": true
    },
    {
      "id": "R7",
      "kind": "vague",
      "text": "Find me a good place for a Moon base.",
      "expected_archetype": "long-duration-outpost",
      "expect": {
        "mission_duration_h": 720,
        "requirements": {
          "area": {
            "observer_height_above_ground_m": 10
          }
        },
        "proposed_fields": {
          "max_continuous_dark_h": 192
        }
      },
      "message_must_mention": [],
      "rationale_required": true
    },
    {
      "id": "R8",
      "kind": "out-of-domain",
      "text": "A one-week crewed landing near the south pole where the surface stays warmer than -50 C and the soil is rich in titanium.",
      "expected_archetype": "short-crewed-stay",
      "expect": {
        "mission_duration_h": 168,
        "requirements": {
          "area": {
            "landing_precision_m": 100,
            "operating_range_m": 2000,
            "traverse_slope_limit_deg": 20,
            "observer_height_above_ground_m": 10
          },
          "min_continuous_light_h": 168,
          "min_earth_visibility_fraction": 0.25,
          "max_slope_deg": 10,
          "latitude_max_deg": -84
        },
        "proposed_fields": {}
      },
      "message_must_mention": [
        "temperature",
        "titanium"
      ],
      "rationale_required": true
    }
  ]
}
```
<!-- EXAMPLES_JSON_END -->
