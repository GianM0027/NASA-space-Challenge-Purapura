# ABOUTME: Tests of the AI routes with and without a user's Anthropic API key (decision D43)
# ABOUTME: Owner: Gian. Server without LLM: the app degrades; a key answers that request only

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from lunarnav.ai import llm
from lunarnav.ai.archetypes import load_archetypes
from lunarnav.ai.assistant import ChatAssistant
from lunarnav.ai.regions import load_regions
from lunarnav.api.main import API_KEY_HEADER, build_app
from lunarnav.api.wiring import build_services

START = datetime(2027, 1, 1, tzinfo=UTC)
WINDOW = {
    "start_utc": START.isoformat(),
    "end_utc": (START + timedelta(days=2)).isoformat(),
    "step_minutes": 240,
}
KEY = "sk-ant-api03-user-key"
REQUIREMENTS = json.loads(
    (Path(__file__).parents[2] / "data/examples/site_ranking.json").read_text()
)["requirements"]
CHAT = {"text": "hello", "history": [], "locked_fields": [], "default_window": WINDOW}
REPLY = {
    "action": "other",
    "reply": "Hello! Describe your mission.",
    "archetype_id": None,
    "region_id": None,
    "start_utc": None,
    "duration_h": None,
    "fields": [],
    "cleared": [],
}


class _FakeLlm:
    """Answers every call with ``answer`` (or raises it), recording the key it was built for."""

    provider = "api"

    def __init__(self, key: str, answer: Any) -> None:
        self.key = key
        self.answer = answer

    def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


@pytest.fixture
def setup() -> tuple[TestClient, ChatAssistant]:
    """The real chat assistant on placeholder modules, with no server LLM."""
    services, status = build_services(use_real=False)
    assistant = ChatAssistant(
        services.ranker,
        services.catalog,
        llm.UnavailableLlmClient(),
        load_archetypes(),
        load_regions(),
    )
    app = build_app(dataclasses.replace(services, assistant=assistant), status)
    return TestClient(app), assistant


def _use_fake(monkeypatch: pytest.MonkeyPatch, answer: Any) -> list[_FakeLlm]:
    built: list[_FakeLlm] = []

    def fake(key: str) -> _FakeLlm:
        client = _FakeLlm(llm.validate_api_key(key), answer)
        built.append(client)
        return client

    monkeypatch.setattr(llm, "api_client_for_key", fake)
    return built


def test_config_reports_no_server_llm(setup: tuple[TestClient, ChatAssistant]) -> None:
    api, _ = setup
    config = api.get("/api/ai/config").json()
    assert config == {"server_llm": "none", "accepts_user_key": True, "key_header": API_KEY_HEADER}


def test_chat_without_key_is_503(setup: tuple[TestClient, ChatAssistant]) -> None:
    api, _ = setup
    answer = api.post("/api/ai/ask", json=CHAT)
    assert answer.status_code == 503
    assert "API key" in answer.json()["detail"]


def test_explanations_without_key_are_deterministic(
    setup: tuple[TestClient, ChatAssistant],
) -> None:
    api, _ = setup
    ranking = api.post("/api/rank", json=REQUIREMENTS).json()
    body = {"ranking": ranking, "language_hint": ""}
    explained = api.post("/api/ai/explain", json=body)
    assert explained.status_code == 200
    assert all(score["rationale"] for score in explained.json()["results"])


def test_analysis_comment_without_key_is_null(setup: tuple[TestClient, ChatAssistant]) -> None:
    api, _ = setup
    scenario = {"location": {"lat_deg": -89.5, "lon_deg": 0}, "window": WINDOW}
    report = api.post("/api/mission-analysis", json=scenario).json()
    commented = api.post("/api/ai/comment-analysis", json={"report": report, "site_name": "X"})
    assert commented.status_code == 200
    assert commented.json()["ai_comment"] is None


def test_tradeoff_without_key_has_no_comment(setup: tuple[TestClient, ChatAssistant]) -> None:
    api, _ = setup
    scenario = {"location": {"lat_deg": 0, "lon_deg": 0}, "window": WINDOW}
    body = {"scenarios": [scenario, scenario], "settings": {"labels": ["A", "B"]}}
    result = api.post("/api/tradeoff", json=body)
    assert result.status_code == 200
    assert result.json()["ai_comment"] is None


def test_chat_with_key_answers_with_that_key(
    setup: tuple[TestClient, ChatAssistant], monkeypatch: pytest.MonkeyPatch
) -> None:
    api, assistant = setup
    built = _use_fake(monkeypatch, REPLY)
    answer = api.post("/api/ai/ask", json=CHAT, headers={API_KEY_HEADER: f" {KEY} "})
    assert answer.status_code == 200
    assert answer.json()["message"] == REPLY["reply"]
    assert [client.key for client in built] == [KEY]
    # The shared assistant keeps no key: the next request without one still gets 503.
    assert isinstance(assistant.llm, llm.UnavailableLlmClient)
    assert api.post("/api/ai/ask", json=CHAT).status_code == 503


def test_rejected_key_is_401_and_never_echoed_or_logged(
    setup: tuple[TestClient, ChatAssistant],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    api, _ = setup
    _use_fake(monkeypatch, llm.LlmAuthError("Anthropic rejected the API key: invalid x-api-key"))
    with caplog.at_level(logging.DEBUG):
        answer = api.post("/api/ai/ask", json=CHAT, headers={API_KEY_HEADER: KEY})
    assert answer.status_code == 401
    assert KEY not in answer.text
    assert KEY not in caplog.text


def test_key_of_impossible_shape_is_422(setup: tuple[TestClient, ChatAssistant]) -> None:
    api, _ = setup
    answer = api.post("/api/ai/ask", json=CHAT, headers={API_KEY_HEADER: "not a key"})
    assert answer.status_code == 422
    assert "not a key" not in answer.text


def test_blank_key_header_counts_as_no_key(setup: tuple[TestClient, ChatAssistant]) -> None:
    api, _ = setup
    assert api.post("/api/ai/ask", json=CHAT, headers={API_KEY_HEADER: "  "}).status_code == 503


def test_placeholder_assistant_cannot_take_a_key() -> None:
    api = TestClient(build_app(*build_services(use_real=False)))
    assert api.get("/api/ai/config").json()["server_llm"] == "example"
    answer = api.post("/api/ai/ask", json=CHAT, headers={API_KEY_HEADER: KEY})
    assert answer.status_code == 501
