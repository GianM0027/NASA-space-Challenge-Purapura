# ABOUTME: Tests of the chat assistant with a scripted fake LLM: merge, questions, retries, numbers
# ABOUTME: Owner: Gian. Also covers the number check and the Claude CLI output parsing

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from lunarnav.ai.archetypes import load_archetypes
from lunarnav.ai.assistant import ChatAssistant, template_rationale
from lunarnav.ai.llm import ClaudeCliClient, LlmError, parse_cli_output
from lunarnav.ai.numbers import unsupported_numbers
from lunarnav.contracts import (
    AiRequest,
    ChatMessage,
    MissionRequirements,
    RequirementSource,
    Site,
    SiteRanking,
    TimeWindow,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "data" / "examples"
START = datetime(2026, 11, 14, tzinfo=UTC)
GUI_WINDOW = TimeWindow(start_utc=START, end_utc=START + timedelta(days=30), step_minutes=60)


class _Llm:
    """Returns scripted answers in order and records the prompts."""

    def __init__(self, *answers: dict[str, Any] | Exception) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []

    def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.prompts.append(prompt)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class _Ranker:
    def __init__(self) -> None:
        self.calls: list[MissionRequirements] = []
        self.example = SiteRanking.model_validate_json((EXAMPLES / "site_ranking.json").read_text())

    def rank(self, requirements: MissionRequirements) -> SiteRanking:
        self.calls.append(requirements)
        return self.example.model_copy(update={"requirements": requirements})


class _Catalog:
    def list_sites(self) -> list[Site]:
        return [Site.model_validate(s) for s in json.loads((EXAMPLES / "sites.json").read_text())]


def _extraction(**update: Any) -> dict[str, Any]:
    answer: dict[str, Any] = {
        "action": "rank",
        "reply": "A short crewed stay.",
        "archetype_id": None,
        "start_utc": None,
        "duration_h": None,
        "fields": [],
        "cleared": [],
    }
    answer.update(update)
    return answer


def _assistant(llm: _Llm) -> tuple[ChatAssistant, _Ranker]:
    ranker = _Ranker()
    return ChatAssistant(ranker, _Catalog(), llm, load_archetypes()), ranker


def test_archetype_values_then_user_values_with_sources() -> None:
    llm = _Llm(
        _extraction(
            archetype_id="short-crewed-stay",
            fields=[{"name": "max_slope_deg", "value": 8, "rationale": "user: under 8 degrees"}],
        )
    )
    assistant, ranker = _assistant(llm)
    answer = assistant.ask(AiRequest(text="crewed, slope under 8 deg", default_window=GUI_WINDOW))
    req = answer.requirements
    assert req.archetype_id == "short-crewed-stay"
    assert req.min_continuous_light_h == 156
    assert req.field_sources["min_continuous_light_h"] == RequirementSource.ARCHETYPE
    assert req.max_slope_deg == 8
    assert req.field_sources["max_slope_deg"] == RequirementSource.USER
    assert req.window is not None
    assert req.window.end_utc - req.window.start_utc == timedelta(hours=156)
    assert req.field_sources["window"] == RequirementSource.ARCHETYPE
    assert req.area is not None and req.area.observer_height_above_ground_m == 10
    assert answer.ranking is not None and ranker.calls == [req]


def test_locked_field_keeps_its_value_and_cleared_field_is_dropped() -> None:
    current = MissionRequirements(
        min_illumination_fraction=0.7, max_slope_deg=5.0, rationale={"max_slope_deg": "by hand"}
    )
    llm = _Llm(
        _extraction(
            fields=[{"name": "max_slope_deg", "value": 12, "rationale": "x"}],
            cleared=["min_illumination_fraction"],
        )
    )
    assistant, _ = _assistant(llm)
    request = AiRequest(
        text="forget the light, slope 12",
        requirements=current,
        locked_fields=["max_slope_deg"],
        default_window=GUI_WINDOW,
        history=[ChatMessage(role="user", text="light 70%")],
    )
    req = assistant.ask(request).requirements
    assert req.max_slope_deg == 5.0
    assert req.rationale["max_slope_deg"] == "by hand"
    assert req.min_illumination_fraction is None
    assert req.window == GUI_WINDOW
    assert req.field_sources["window"] == RequirementSource.DEFAULT


def test_no_archetype_and_no_value_asks_back_without_ranking() -> None:
    assistant, ranker = _assistant(_Llm(_extraction(reply="Which mission?")))
    answer = assistant.ask(AiRequest(text="find me a site", default_window=GUI_WINDOW))
    assert answer.ranking is None
    assert ranker.calls == []
    assert answer.message.endswith("?")


def test_invalid_answer_is_retried_with_the_error_then_reported() -> None:
    bad = _extraction(fields=[{"name": "min_illumination_fraction", "value": 70, "rationale": ""}])
    good = _extraction(
        fields=[{"name": "min_illumination_fraction", "value": 0.7, "rationale": ""}]
    )
    llm = _Llm(bad, good)
    assistant, _ = _assistant(llm)
    answer = assistant.ask(AiRequest(text="light 70%", default_window=GUI_WINDOW))
    assert answer.requirements.min_illumination_fraction == 0.7
    assert "previous answer was invalid" in llm.prompts[1]
    with pytest.raises(LlmError):
        _assistant(_Llm(bad, bad))[0].ask(AiRequest(text="light 70%", default_window=GUI_WINDOW))


def test_reply_with_an_invented_number_is_replaced() -> None:
    llm = _Llm(
        _extraction(
            reply="Malapert gets 87% light.",
            fields=[{"name": "min_illumination_fraction", "value": 0.5, "rationale": ""}],
        )
    )
    answer = _assistant(llm)[0].ask(AiRequest(text="half the time lit", default_window=GUI_WINDOW))
    assert "87" not in answer.message


def _ranking() -> SiteRanking:
    example = SiteRanking.model_validate_json((EXAMPLES / "site_ranking.json").read_text())
    requirements = MissionRequirements(window=GUI_WINDOW, min_illumination_fraction=0.5)
    score = example.results[0].model_copy(
        update={
            "constraints_met": {"min_illumination_fraction": True},
            "criterion_values": {"min_illumination_fraction": 0.62},
        }
    )
    return SiteRanking(requirements=requirements, results=[score])


def test_explanation_keeps_checked_text_and_replaces_invented_numbers() -> None:
    ranking = _ranking()
    site_id = ranking.results[0].site_id
    good = {"items": [{"site_id": site_id, "text": "Lit 62% of the time, above the 50% asked."}]}
    explained = _assistant(_Llm(good))[0].explain(ranking)
    assert explained.results[0].rationale == good["items"][0]["text"]
    bad = {"items": [{"site_id": site_id, "text": "Lit 91% of the time."}]}
    explained = _assistant(_Llm(bad))[0].explain(ranking)
    assert explained.results[0].rationale == template_rationale(
        ranking.results[0], ranking.requirements
    )
    explained = _assistant(_Llm(LlmError("down")))[0].explain(ranking)
    assert "62%" in (explained.results[0].rationale or "")


def test_unsupported_numbers_accepts_rounding_percent_and_days() -> None:
    assert unsupported_numbers("62% light, 156 h or 6.5 days, slope 8.3", [0.623, 156, 8.27]) == []
    assert unsupported_numbers("6,5 giorni", [156]) == []
    assert unsupported_numbers("63% light", [0.623]) == [63.0]


def test_parse_cli_output() -> None:
    ok = json.dumps({"subtype": "success", "is_error": False, "structured_output": {"a": 1}})
    assert parse_cli_output(ok) == {"a": 1}
    with pytest.raises(LlmError, match="Not logged in"):
        parse_cli_output(
            json.dumps({"subtype": "success", "is_error": True, "result": "Not logged in"})
        )
    with pytest.raises(LlmError):
        parse_cli_output("not json")


def test_cli_command_switches_off_every_context_source() -> None:
    command = ClaudeCliClient("claude").command(Path("system.txt"), {"type": "object"})
    for flag in ("--setting-sources", "--strict-mcp-config", "--disable-slash-commands", "--tools"):
        assert flag in command
    assert command[command.index("--tools") + 1] == ""
    assert command[command.index("--setting-sources") + 1] == ""


def test_prompt_lists_only_fields_with_a_source() -> None:
    from lunarnav.contracts import OperationsArea

    area = OperationsArea(
        landing_precision_m=100,
        operating_range_m=0,
        traverse_slope_limit_deg=20,
        observer_height_above_ground_m=2,
    )
    current = MissionRequirements(
        area=area, field_sources={"landing_precision_m": RequirementSource.USER}
    )
    llm = _Llm(_extraction(action="other"))
    _assistant(llm)[0].ask(AiRequest(text="hello", requirements=current, default_window=GUI_WINDOW))
    parameters = json.loads(llm.prompts[0])["current_parameters"]
    assert parameters == {"landing_precision_m": {"value": 100.0, "source": "user"}}
