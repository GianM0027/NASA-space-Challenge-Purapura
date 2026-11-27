# ABOUTME: Tests for the Anthropic API adapter, the no-LLM client and provider selection (AI-4)
# ABOUTME: Owner: Gian. The SDK client is replaced by a fake: no test reaches the network

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

anthropic = pytest.importorskip("anthropic")
httpx2 = pytest.importorskip("httpx2")

from lunarnav.ai import llm  # noqa: E402

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["comment"],
    "properties": {"comment": {"type": "string"}},
}
KEY = "sk-ant-api03-test-key"


def _message(text: str | None, stop_reason: str = "end_turn") -> SimpleNamespace:
    content = [SimpleNamespace(type="thinking", thinking="")]
    if text is not None:
        content.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(stop_reason=stop_reason, content=content)


class _FakeSdk:
    """Stands in for ``anthropic.Anthropic``: records the calls, answers or raises."""

    instances: ClassVar[list[_FakeSdk]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.calls: list[dict[str, Any]] = []
        self.outcome: Any = _message('{"comment": "Fine."}')
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        _FakeSdk.instances.append(self)

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def sdk(monkeypatch: pytest.MonkeyPatch) -> type[_FakeSdk]:
    _FakeSdk.instances = []
    monkeypatch.setattr(anthropic, "Anthropic", _FakeSdk)
    return _FakeSdk


def _response(status: int) -> Any:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return httpx2.Response(status, request=request)


def test_call_uses_the_key_the_schema_and_the_default_model(sdk: type[_FakeSdk]) -> None:
    client = llm.AnthropicApiClient(KEY)
    assert client.complete_json("System.", "Prompt.", SCHEMA) == {"comment": "Fine."}
    fake = sdk.instances[0]
    assert fake.kwargs["api_key"] == KEY
    call = fake.calls[0]
    assert call["model"] == llm.DEFAULT_API_MODEL
    assert call["system"] == "System."
    assert call["messages"] == [{"role": "user", "content": "Prompt."}]
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": SCHEMA}
    assert "fallbacks" not in call  # the default (Haiku) has no server-side refusal fallback


def test_opus_and_sonnet_use_the_refusal_fallback(sdk: type[_FakeSdk]) -> None:
    for model in ("claude-opus-5-5", "claude-sonnet-5-5"):
        llm.AnthropicApiClient(KEY, model=model).complete_json("s", "p", SCHEMA)
        call = sdk.instances[-1].calls[0]
        assert call["fallbacks"] == "default"
        assert "thinking" not in call  # these models reject disabled thinking; effort only


def test_model_can_be_chosen(sdk: type[_FakeSdk]) -> None:
    llm.AnthropicApiClient(KEY, model="claude-sonnet-5-5").complete_json("s", "p", SCHEMA)
    assert sdk.instances[0].calls[0]["model"] == "claude-sonnet-5-5"


@pytest.mark.parametrize(
    ("outcome", "message"),
    [
        (_message('{"comment": "x"}', stop_reason="refusal"), "declined"),
        (_message('{"comment": "x', stop_reason="max_tokens"), "cut off"),
        (_message("not json"), "non-JSON"),
        (_message("[1, 2]"), "unexpected"),
        (_message(None), "no text"),
    ],
)
def test_unusable_answers_raise_llm_error(sdk: type[_FakeSdk], outcome: Any, message: str) -> None:
    client = llm.AnthropicApiClient(KEY)
    sdk.instances[0].outcome = outcome
    with pytest.raises(llm.LlmError, match=message):
        client.complete_json("s", "p", SCHEMA)


def test_rejected_key_raises_llm_auth_error(sdk: type[_FakeSdk]) -> None:
    client = llm.AnthropicApiClient(KEY)
    sdk.instances[0].outcome = anthropic.AuthenticationError(
        "invalid x-api-key", response=_response(401), body=None
    )
    with pytest.raises(llm.LlmAuthError) as raised:
        client.complete_json("s", "p", SCHEMA)
    assert KEY not in str(raised.value)


def test_rate_limit_and_network_errors_raise_llm_error(sdk: type[_FakeSdk]) -> None:
    client = llm.AnthropicApiClient(KEY)
    fake = sdk.instances[0]
    fake.outcome = anthropic.RateLimitError("slow down", response=_response(429), body=None)
    with pytest.raises(llm.LlmError, match="rate limit") as raised:
        client.complete_json("s", "p", SCHEMA)
    assert not isinstance(raised.value, llm.LlmAuthError)
    fake.outcome = anthropic.APIConnectionError(request=_response(500).request)
    with pytest.raises(llm.LlmError, match="unreachable"):
        client.complete_json("s", "p", SCHEMA)


def test_repr_never_shows_the_key(sdk: type[_FakeSdk]) -> None:
    assert KEY not in repr(llm.AnthropicApiClient(KEY))


def test_unavailable_client_asks_for_a_key() -> None:
    with pytest.raises(llm.LlmUnavailableError):
        llm.UnavailableLlmClient().complete_json("s", "p", SCHEMA)


@pytest.mark.parametrize("key", ["", "   ", "has space", "è-accented", "x" * 300])
def test_impossible_keys_are_rejected(key: str) -> None:
    with pytest.raises(ValueError, match="not a valid key"):
        llm.validate_api_key(key)


def test_key_is_trimmed() -> None:
    assert llm.validate_api_key(f"  {KEY}\n") == KEY


def test_provider_none_builds_the_unavailable_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUNARNAV_LLM_PROVIDER", "none")
    assert isinstance(llm.build_llm_client(), llm.UnavailableLlmClient)


def test_provider_api_needs_the_server_key(
    monkeypatch: pytest.MonkeyPatch, sdk: type[_FakeSdk]
) -> None:
    monkeypatch.setenv("LUNARNAV_LLM_PROVIDER", "api")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        llm.build_llm_client()
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    client = llm.build_llm_client()
    assert isinstance(client, llm.AnthropicApiClient)
    assert sdk.instances[0].kwargs["api_key"] == KEY


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUNARNAV_LLM_PROVIDER", "openai")
    with pytest.raises(ValueError, match="unknown LLM provider"):
        llm.build_llm_client()


def test_haiku_is_called_without_the_refusal_fallback(sdk: type[_FakeSdk]) -> None:
    llm.AnthropicApiClient(KEY, model="claude-haiku-5-5").complete_json("s", "p", SCHEMA)
    call = sdk.instances[0].calls[0]
    assert "fallbacks" not in call and "betas" not in call


def test_visitor_model_choice(monkeypatch: pytest.MonkeyPatch, sdk: type[_FakeSdk]) -> None:
    monkeypatch.delenv("LUNARNAV_LLM_MODEL", raising=False)
    assert llm.api_client_for_key(KEY).model == "claude-haiku-5-5"  # default: cheapest, enough
    assert llm.api_client_for_key(KEY, "claude-opus-5-5").model == "claude-opus-5-5"
    with pytest.raises(ValueError, match="model must be one of"):
        llm.api_client_for_key(KEY, "claude-something-else")


def test_nullable_types_become_any_of_for_the_api() -> None:
    nullable = {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "when", "hours"],
        "properties": {
            "kind": {"type": ["string", "null"], "enum": ["a", "b", None]},
            "when": {"type": ["string", "null"]},
            "hours": {"type": ["number", "null"], "description": "duration"},
        },
    }
    converted = llm.api_json_schema(nullable)
    props = converted["properties"]
    assert props["kind"] == {"anyOf": [{"type": "string", "enum": ["a", "b"]}, {"type": "null"}]}
    assert props["when"] == {"anyOf": [{"type": "string"}, {"type": "null"}]}
    assert props["hours"] == {
        "description": "duration",
        "anyOf": [{"type": "number"}, {"type": "null"}],
    }
    assert converted["required"] == ["kind", "when", "hours"]
    assert nullable["properties"]["kind"]["enum"] == ["a", "b", None]  # the input is not changed


def test_the_real_extraction_schema_has_no_type_lists_for_the_api() -> None:
    from lunarnav.ai import assistant
    from lunarnav.ai.archetypes import load_archetypes
    from lunarnav.ai.regions import load_regions

    schema = assistant._extraction_schema(list(load_archetypes()), list(load_regions()))
    converted = llm.api_json_schema(schema)

    def check(node: Any) -> None:
        if isinstance(node, dict):
            assert not isinstance(node.get("type"), list), node
            if "enum" in node:
                assert None not in node["enum"], node
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(converted)


def test_the_api_receives_the_converted_schema(sdk: type[_FakeSdk]) -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["x"],
        "properties": {"x": {"type": ["string", "null"]}},
    }
    llm.AnthropicApiClient(KEY).complete_json("s", "p", schema)
    sent = sdk.instances[0].calls[0]["output_config"]["format"]["schema"]
    assert sent["properties"]["x"] == {"anyOf": [{"type": "string"}, {"type": "null"}]}
