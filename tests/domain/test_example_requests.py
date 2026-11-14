# ABOUTME: Checks docs/domain/example_requests.md: JSON block valid and consistent with archetypes
# ABOUTME: Owner: Michael; the AI module (Gian) runs these requests through the LLM in its own tests

import json
import re
from pathlib import Path

import pytest

from lunarnav.contracts import MissionRequirements

DOMAIN = Path(__file__).parents[2] / "docs" / "domain"
EXAMPLES = re.compile(
    r"<!--\s*EXAMPLES_JSON_BEGIN\s*-->\s*```json\s*(.*?)\s*```\s*<!--\s*EXAMPLES_JSON_END\s*-->",
    re.DOTALL,
)
ARCHETYPES = re.compile(
    r"<!--\s*ARCHETYPES_JSON_BEGIN\s*-->\s*```json\s*(.*?)\s*```\s*<!--\s*ARCHETYPES_JSON_END\s*-->",
    re.DOTALL,
)


def _block(pattern: re.Pattern[str], name: str) -> dict:
    matches = pattern.findall((DOMAIN / name).read_text(encoding="utf-8"))
    assert len(matches) == 1, f"exactly one JSON block expected in {name}"
    return json.loads(matches[0])


REQUESTS = _block(EXAMPLES, "example_requests.md")["requests"]
ARCH = {a["id"]: a for a in _block(ARCHETYPES, "mission_archetypes.md")["archetypes"]}


def test_ids_unique_and_spec_minimum_met() -> None:
    ids = [r["id"] for r in REQUESTS]
    assert len(ids) == len(set(ids)) >= 5  # spec AI-1: 5 scripted requests
    assert {r["kind"] for r in REQUESTS} >= {"normal", "explicit-numbers", "vague", "out-of-domain"}


@pytest.mark.parametrize("req", REQUESTS, ids=lambda r: r["id"])
def test_expectation_is_valid_and_references_an_archetype(req: dict) -> None:
    MissionRequirements.model_validate(req["expect"]["requirements"])
    assert req["expected_archetype"] in ARCH
    assert req["text"].strip()


@pytest.mark.parametrize(
    "req", [r for r in REQUESTS if r["kind"] == "normal"], ids=lambda r: r["id"]
)
def test_normal_cases_equal_archetype_values(req: dict) -> None:
    arch = ARCH[req["expected_archetype"]]
    assert req["expect"]["requirements"] == arch["requirements"]
    assert req["expect"]["proposed_fields"] == arch["proposed_fields"]
    assert req["expect"].get("mission_duration_h") == arch.get("mission_duration_h")


def test_hard_cases_follow_the_documented_rules() -> None:
    by_id = {r["id"]: r for r in REQUESTS}
    # R6: user numbers override the archetype, the rest is inherited
    r6 = by_id["R6"]["expect"]["requirements"]
    assert r6["min_illumination_fraction"] == 0.8
    assert r6["max_slope_deg"] == 5
    assert r6["min_continuous_light_h"] == ARCH["small-robotic-lander"]["mission_duration_h"]
    # R8: one week = 168 h, lit throughout; out-of-domain words must be named in the message
    r8 = by_id["R8"]
    assert r8["expect"]["mission_duration_h"] == 168
    assert r8["expect"]["requirements"]["min_continuous_light_h"] == 168
    assert set(r8["message_must_mention"]) == {"temperature", "titanium"}
    # R7: vague request maps to the outpost with no extra numbers
    assert by_id["R7"]["expect"]["requirements"] == {}
