# ABOUTME: Loads the mission archetypes (spec AI-5) from Michael's docs/domain/mission_archetypes.md
# ABOUTME: Owner: Gian (code); the content and its sources belong to Michael

"""Mission archetypes as typed objects: sourced typical requirements and a priority order."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lunarnav.contracts import MissionRequirements, OperationsArea

ARCHETYPES_PATH = Path(__file__).resolve().parents[3] / "docs" / "domain" / "mission_archetypes.md"

# The extraction regex is the one documented in mission_archetypes.md ("How to read the JSON").
_BLOCK = re.compile(
    r"<!--\s*ARCHETYPES_JSON_BEGIN\s*-->\s*```json\s*(.*?)\s*```\s*<!--\s*ARCHETYPES_JSON_END\s*-->",
    re.DOTALL,
)


@dataclass(frozen=True)
class Archetype:
    """One mission archetype, ready to seed ``MissionRequirements``.

    Attributes:
        id: Slug used by the AI (``MissionRequirements.archetype_id``).
        name: Display name.
        summary: One-paragraph description, given to the LLM.
        mission_duration_h: Typical surface duration, hours; None when the source gives none.
        requirements: Typical values (window unset); ``proposed_fields`` that exist in the
            contract are included, and the observer height goes into ``area``.
        priority: Criterion field names, most important group first; empty when no source
            orders them (equal weights).
        sources: Field name (or ``area.<field>``, ``priority``) -> citation.
        notes: Sourced qualitative constraints with no number.
    """

    id: str
    name: str
    summary: str
    mission_duration_h: float | None
    requirements: MissionRequirements
    priority: tuple[tuple[str, ...], ...]
    sources: dict[str, str]
    notes: tuple[str, ...]

    def source_of(self, field: str) -> str | None:
        """Return the citation of one requirement field, looking in every key form used."""
        for key in (field, f"area.{field}", f"proposed_fields.{field}"):
            if key in self.sources:
                return self.sources[key]
        if field == "observer_height_above_ground_m":
            return self.sources.get("observer_height_m")
        return None


def _requirements(raw: dict[str, Any]) -> MissionRequirements:
    """Build the archetype requirements from its JSON entry.

    Args:
        raw: One element of the ``archetypes`` list of the JSON block.

    Returns:
        Requirements with the archetype values; ``proposed_fields`` unknown to the contract
        are ignored, as the document allows.
    """
    values: dict[str, Any] = dict(raw.get("requirements", {}))
    area: dict[str, Any] = dict(values.pop("area", {}))
    for key, value in raw.get("proposed_fields", {}).items():
        if key in MissionRequirements.model_fields:
            values.setdefault(key, value)
        elif key in OperationsArea.model_fields:
            area.setdefault(key, value)
    if "observer_height_m" in raw:
        area.setdefault("observer_height_above_ground_m", raw["observer_height_m"])
    if area:
        values["area"] = OperationsArea(**area)
    return MissionRequirements(**values)


def parse_archetypes(markdown: str) -> dict[str, Archetype]:
    """Parse the archetypes from the content of ``mission_archetypes.md``.

    Args:
        markdown: Full text of the document.

    Returns:
        Archetypes by id, in document order.

    Raises:
        ValueError: If the JSON block is missing or a value does not fit the contract.
    """
    match = _BLOCK.search(markdown)
    if match is None:
        raise ValueError("mission archetypes: JSON block not found")
    data = json.loads(match.group(1))
    archetypes: dict[str, Archetype] = {}
    for raw in data["archetypes"]:
        archetypes[raw["id"]] = Archetype(
            id=raw["id"],
            name=raw["name"],
            summary=raw["summary"],
            mission_duration_h=raw.get("mission_duration_h"),
            requirements=_requirements(raw),
            priority=tuple(tuple(group) for group in raw.get("priority", [])),
            sources=dict(raw.get("sources", {})),
            notes=tuple(raw.get("notes", [])),
        )
    return archetypes


def load_archetypes(path: Path = ARCHETYPES_PATH) -> dict[str, Archetype]:
    """Load the archetypes from the domain document.

    Args:
        path: The markdown file; defaults to ``docs/domain/mission_archetypes.md``.

    Returns:
        Archetypes by id.

    Raises:
        OSError: If the file cannot be read.
        ValueError: If its JSON block is missing or invalid.
    """
    return parse_archetypes(path.read_text(encoding="utf-8"))
