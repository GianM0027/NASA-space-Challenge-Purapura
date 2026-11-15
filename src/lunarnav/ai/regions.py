# ABOUTME: Loads the named regions (spec AI-7) from Michael's docs/domain/regions.md
# ABOUTME: Owner: Gian (code); the bounds and their sources belong to Michael

"""Named regions ("near the south pole", "far side") as search-scope bounds with a source.

The LLM only picks a region id from the list; the bounds come from this table, so a region
never brings a number the model made up.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REGIONS_PATH = Path(__file__).resolve().parents[3] / "docs" / "domain" / "regions.md"

_BLOCK = re.compile(
    r"<!--\s*REGIONS_JSON_BEGIN\s*-->\s*```json\s*(.*?)\s*```\s*<!--\s*REGIONS_JSON_END\s*-->",
    re.DOTALL,
)

# Region table key -> MissionRequirements field.
_FIELDS = {
    "latitude_min_deg": "latitude_min_deg",
    "latitude_max_deg": "latitude_max_deg",
    "lon_min_deg": "longitude_min_deg",
    "lon_max_deg": "longitude_max_deg",
}


@dataclass(frozen=True)
class Region:
    """One named region of the Moon, as a search scope.

    Attributes:
        id: Slug the LLM picks (``MissionRequirements.region_id``).
        label: Display name.
        summary: One sentence the LLM reads to recognize the region.
        latitude_min_deg: Southern bound, degrees; None for no bound.
        latitude_max_deg: Northern bound, degrees; None for no bound.
        lon_min_deg: Western bound, east-positive degrees; None for no bound.
        lon_max_deg: Eastern bound, east-positive degrees; None for no bound. A western bound
            greater than the eastern one crosses 180 degrees.
        source: Citation for the bounds.
    """

    id: str
    label: str
    summary: str
    latitude_min_deg: float | None
    latitude_max_deg: float | None
    lon_min_deg: float | None
    lon_max_deg: float | None
    source: str

    def bounds(self) -> dict[str, float]:
        """Return the bounds that are set, keyed by ``MissionRequirements`` field name."""
        return {
            field: float(value)
            for key, field in _FIELDS.items()
            if (value := getattr(self, key)) is not None
        }


def _number(raw: dict[str, Any], key: str) -> float | None:
    """Return a bound from a JSON entry, None when absent or null."""
    value = raw.get(key)
    return None if value is None else float(value)


def parse_regions(markdown: str) -> dict[str, Region]:
    """Parse the regions from the content of ``regions.md``.

    Args:
        markdown: Full text of the document.

    Returns:
        Regions by id, in document order.

    Raises:
        ValueError: If the JSON block is missing.
        KeyError: If an entry lacks ``id``, ``label``, ``summary`` or ``source``.
    """
    match = _BLOCK.search(markdown)
    if match is None:
        raise ValueError("regions: JSON block not found")
    data = json.loads(match.group(1))
    return {
        raw["id"]: Region(
            id=raw["id"],
            label=raw["label"],
            summary=raw["summary"],
            latitude_min_deg=_number(raw, "latitude_min_deg"),
            latitude_max_deg=_number(raw, "latitude_max_deg"),
            lon_min_deg=_number(raw, "lon_min_deg"),
            lon_max_deg=_number(raw, "lon_max_deg"),
            source=raw["source"],
        )
        for raw in data["regions"]
    }


def load_regions(path: Path = REGIONS_PATH) -> dict[str, Region]:
    """Load the regions from the domain document, or none while it does not exist yet.

    Args:
        path: The markdown file; defaults to ``docs/domain/regions.md``.

    Returns:
        Regions by id; empty when the file is missing.

    Raises:
        ValueError: If the file exists but its JSON block is missing or invalid.
    """
    if not path.is_file():
        return {}
    return parse_regions(path.read_text(encoding="utf-8"))
