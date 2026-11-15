# ABOUTME: Renders the contract and API request models as TypeScript types for the frontend
# ABOUTME: Owner: Gian. Written to the frontend by scripts/api_export_types.py; a test checks it

"""TypeScript type generation from the Pydantic models.

Covers exactly the JSON Schema features our models produce (objects, arrays, enums, nullable
unions, references, string-keyed maps, primitives); anything else raises, so a new construct in
the contracts is noticed here instead of silently becoming ``unknown`` in the frontend.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaMode, models_json_schema

from lunarnav import contracts
from lunarnav.api import requests

HEADER = """\
// ABOUTME: TypeScript types of the LunarNav contracts and API requests, generated from Pydantic
// ABOUTME: Do not edit: run `uv run python scripts/api_export_types.py` after a contract change
"""

_PRIMITIVES = {"string": "string", "number": "number", "integer": "number", "boolean": "boolean"}


def _models() -> list[tuple[type[BaseModel], JsonSchemaMode]]:
    """Return the models to export: contracts as received, API requests as sent."""
    received = [
        value
        for name in contracts.__all__
        if isinstance(value := getattr(contracts, name), type) and issubclass(value, BaseModel)
    ]
    sent = [
        requests.EvaluateRequest,
        requests.CompareRequest,
        requests.MissionAnalysisRequest,
        requests.ExplainRequest,
        requests.UpdateSiteRequest,
    ]
    return [(model, "serialization") for model in received] + [
        (model, "validation") for model in sent
    ]


def _name(ref: str) -> str:
    """Return the TypeScript name of a ``#/$defs/...`` reference.

    A model whose request and response schemas differ appears twice: "A-Output" (what the
    backend sends, the one the frontend mostly reads) becomes "A", "A-Input" becomes "AInput".
    """
    key = ref.rsplit("/", 1)[-1]
    if key.endswith("-Output"):
        return key.removesuffix("-Output")
    return key.replace("-", "")


def _type(node: dict[str, Any]) -> str:
    """Return the TypeScript type expression of one JSON Schema node.

    Args:
        node: A JSON Schema fragment produced by Pydantic.

    Returns:
        A TypeScript type expression.

    Raises:
        ValueError: If the node uses a construct this generator does not cover.
    """
    if "$ref" in node:
        return _name(node["$ref"])
    if "anyOf" in node:
        return " | ".join(_type(option) for option in node["anyOf"])
    if "enum" in node:
        return " | ".join(json.dumps(value) for value in node["enum"])
    if "const" in node:
        return json.dumps(node["const"])
    kind = node.get("type")
    if kind == "null":
        return "null"
    if kind in _PRIMITIVES:
        return _PRIMITIVES[kind]
    if kind == "array":
        item = _type(node["items"])
        return f"({item})[]" if " | " in item else f"{item}[]"
    if kind == "object":
        if "properties" in node:
            return _object(node)
        extra = node.get("additionalProperties")
        if isinstance(extra, dict):
            return f"Record<string, {_type(extra)}>"
    raise ValueError(f"unsupported JSON Schema node: {node}")


def _object(node: dict[str, Any]) -> str:
    """Return the TypeScript object type of an object schema; optional keys get ``?``."""
    required = set(node.get("required", []))
    lines = [
        f"  {key}{'' if key in required else '?'}: {_type(prop)}"
        for key, prop in node["properties"].items()
    ]
    return "{\n" + "\n".join(lines) + "\n}"


def render_typescript() -> str:
    """Render every exported model as a TypeScript ``export type``.

    Returns:
        The full content of ``frontend/src/api/contracts.ts``.
    """
    _, schema = models_json_schema(_models())
    blocks = [
        f"export type {_name(key)} = {_type(node)}" for key, node in sorted(schema["$defs"].items())
    ]
    return HEADER + "\n" + "\n\n".join(blocks) + "\n"
