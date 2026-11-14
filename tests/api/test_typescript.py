# ABOUTME: Tests of the TypeScript type generation: known shapes, and the committed file is current
# ABOUTME: Owner: Gian; a contract change without regenerating frontend types fails here

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from lunarnav.api.typescript import _type, render_typescript

GENERATED = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "contracts.ts"


def test_nullable_number() -> None:
    assert _type({"anyOf": [{"type": "number"}, {"type": "null"}]}) == "number | null"


def test_array_of_union_is_parenthesized() -> None:
    node = {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "null"}]}}
    assert _type(node) == "(string | null)[]"


def test_string_map() -> None:
    node = {"type": "object", "additionalProperties": {"type": "boolean"}}
    assert _type(node) == "Record<string, boolean>"


def test_enum_and_reference() -> None:
    assert _type({"enum": ["landed", "planned"], "type": "string"}) == '"landed" | "planned"'
    assert _type({"$ref": "#/$defs/GeoPoint"}) == "GeoPoint"


def test_unknown_construct_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        _type({"type": "object"})


def test_rendered_types_cover_the_main_models() -> None:
    text = render_typescript()
    for name in ("Site", "Evaluation", "MissionRequirements", "AiAnswer", "EvaluateRequest"):
        assert f"export type {name} = " in text


def test_committed_frontend_types_are_current() -> None:
    committed = GENERATED.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert committed == render_typescript(), "run: uv run python scripts/api_export_types.py"


def test_defaults_are_required_in_responses_but_optional_in_requests() -> None:
    text = render_typescript()
    window = text[text.index("export type TimeWindow = ") :]
    assert "  step_minutes: number" in window.split("}")[0]
    request = text[text.index("export type EvaluateRequest = ") :]
    assert "  area?: OperationsArea" in request.split("}")[0]
