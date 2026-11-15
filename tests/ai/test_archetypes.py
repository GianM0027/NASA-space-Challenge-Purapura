# ABOUTME: Tests of the mission archetype loader against Michael's docs/domain/mission_archetypes.md
# ABOUTME: Owner: Gian. Checks the values reach MissionRequirements unchanged, with their sources

from __future__ import annotations

import pytest

from lunarnav.ai.archetypes import load_archetypes, parse_archetypes


def test_loads_every_archetype_of_the_document() -> None:
    archetypes = load_archetypes()
    assert "short-crewed-stay" in archetypes
    assert "small-robotic-lander" in archetypes


def test_short_crewed_stay_values_and_area() -> None:
    crew = load_archetypes()["short-crewed-stay"]
    assert crew.mission_duration_h == 156
    assert crew.requirements.min_continuous_light_h == 156
    assert crew.requirements.max_slope_deg == 10
    area = crew.requirements.area
    assert area is not None
    assert area.landing_precision_m == 100
    assert area.observer_height_above_ground_m == 10
    assert area.traverse_slope_limit_deg == 20
    assert crew.source_of("landing_precision_m") is not None
    assert crew.source_of("observer_height_above_ground_m") is not None


def test_proposed_fields_now_in_the_contract_become_requirements() -> None:
    outpost = load_archetypes()["long-duration-outpost"]
    assert outpost.requirements.max_continuous_dark_h == 192


def test_missing_block_is_an_error() -> None:
    with pytest.raises(ValueError, match="not found"):
        parse_archetypes("# nothing here")
