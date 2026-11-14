# ABOUTME: Checks docs/domain/mission_archetypes.md (AI-5): JSON block extractable, valid, sourced
# ABOUTME: Owner: Michael; the AI module (Gian) parses the same block with the same regex

import json
import re
from pathlib import Path

import pytest

from lunarnav.contracts import MissionRequirements, OperationsArea

DOC = Path(__file__).parents[2] / "docs" / "domain" / "mission_archetypes.md"
# Same pattern as documented in the file itself.
PATTERN = re.compile(
    r"<!--\s*ARCHETYPES_JSON_BEGIN\s*-->\s*```json\s*(.*?)\s*```\s*<!--\s*ARCHETYPES_JSON_END\s*-->",
    re.DOTALL,
)
KNOWN_PROPOSED = {"max_continuous_dark_h", "traverse_slope_limit_deg"}  # requested to Gian


def _archetypes() -> list[dict]:
    matches = PATTERN.findall(DOC.read_text(encoding="utf-8"))
    assert len(matches) == 1, "exactly one ARCHETYPES_JSON block expected"
    data = json.loads(matches[0])
    assert data["schema_version"] == 1
    return data["archetypes"]


def _numeric_keys(archetype: dict) -> list[str]:
    keys = [k for k in ("mission_duration_h", "observer_height_m") if k in archetype]
    for k, v in archetype["requirements"].items():
        if isinstance(v, dict):
            keys += [f"{k}.{sub}" for sub in v]
        elif isinstance(v, int | float):
            keys.append(k)
    keys += [f"proposed_fields.{k}" for k in archetype["proposed_fields"]]
    return keys


def test_block_extracts_and_ids_are_unique() -> None:
    ids = [a["id"] for a in _archetypes()]
    assert len(ids) == len(set(ids)) == 5
    assert "communication-relay" not in ids  # dropped: not enough literature


@pytest.mark.parametrize("archetype", _archetypes(), ids=lambda a: a["id"])
def test_requirements_validate_against_contract(archetype: dict) -> None:
    MissionRequirements.model_validate(archetype["requirements"])
    if "area" in archetype["requirements"]:
        OperationsArea.model_validate(archetype["requirements"]["area"])
    assert set(archetype["proposed_fields"]) <= KNOWN_PROPOSED


@pytest.mark.parametrize("archetype", _archetypes(), ids=lambda a: a["id"])
def test_every_number_has_a_source(archetype: dict) -> None:
    missing = [k for k in _numeric_keys(archetype) if k not in archetype["sources"]]
    assert not missing, f"{archetype['id']}: numbers without a source: {missing}"
    assert all(archetype["sources"][k].strip() for k in archetype["sources"])


def test_known_values_from_sources() -> None:
    by_id = {a["id"]: a for a in _archetypes()}
    crewed = by_id["short-crewed-stay"]
    # NASA HLS overview 2025, p. 21: within 6 deg of the pole, land within 100 m, EVA 2 km
    assert crewed["requirements"]["latitude_max_deg"] == -84
    assert crewed["requirements"]["area"] == {"landing_precision_m": 100, "operating_range_m": 2000}
    assert crewed["mission_duration_h"] == 156  # 6.5 days
    # Landing slope is the only hard slope limit; the EVA limit only measures traversability
    assert crewed["requirements"]["max_slope_deg"] == 10
    assert crewed["proposed_fields"]["traverse_slope_limit_deg"] == 20
    assert "max_slope_deg" not in by_id["polar-rover"]["requirements"]
    assert by_id["long-duration-outpost"]["proposed_fields"]["max_continuous_dark_h"] == 192
    assert by_id["polar-rover"]["proposed_fields"]["max_continuous_dark_h"] == 50
