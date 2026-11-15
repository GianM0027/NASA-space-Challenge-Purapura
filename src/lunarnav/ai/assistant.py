# ABOUTME: AI assistant (spec AI-1, AI-3, AI-5): chat to requirements, ranking, explanations
# ABOUTME: Owner: Gian. The LLM reads only values the user stated; all other numbers come from code

"""Chat assistant over the deterministic ranking.

Pipeline of one ``ask``:

1. Extraction (LLM): from the conversation, the archetype that fits, the named region if any
   (spec AI-7), the values the user stated and the fields the user dropped. The LLM never
   supplies a value the user did not give.
2. Merge (code): archetype values, then region bounds, then user values, then fields the user
   locked in the GUI;
   the window comes from the stated dates, else the archetype duration, else the GUI window.
3. Ranking (code), or a question back when the conversation gives no archetype and no value.

``explain`` adds a one-sentence rationale per site: the LLM writes it for the top sites, every
number in it is checked against the ranking (``lunarnav.ai.numbers``), and a deterministic
sentence replaces any text that fails the check, or the whole call if the LLM fails.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lunarnav.ai.archetypes import Archetype
from lunarnav.ai.llm import LlmClient, LlmError
from lunarnav.ai.numbers import numbers_in, unsupported_numbers
from lunarnav.ai.ranking import (
    CRITERIA,
    Criterion,
    Ranker,
    margin_and_shortfall,
    set_criteria,
    window_hours,
)
from lunarnav.ai.regions import Region
from lunarnav.contracts import (
    AiAnswer,
    AiRequest,
    MissionRequirements,
    OperationsArea,
    RequirementSource,
    SiteCatalog,
    SiteRanking,
    SiteScore,
    TimeWindow,
)

logger = logging.getLogger(__name__)

AREA_FIELDS = (
    "landing_precision_m",
    "operating_range_m",
    "traverse_slope_limit_deg",
    "observer_height_above_ground_m",
)
SCALAR_FIELDS = (
    *(c.field for c in CRITERIA),
    "latitude_min_deg",
    "latitude_max_deg",
    "longitude_min_deg",
    "longitude_max_deg",
)
USER_FIELDS = SCALAR_FIELDS + AREA_FIELDS
# Duration criteria that an archetype may set "for the whole stay" (see _follow_whole_stay).
WHOLE_STAY_FIELDS = ("min_continuous_light_h", "min_continuous_earth_visibility_h")
EXPLAINED_SITES = 5
MAX_ATTEMPTS = 2

_FIELD_HELP = {
    "min_illumination_fraction": "minimum share of time in sunlight, fraction 0-1",
    "min_continuous_light_h": "minimum longest continuous sunlit period, hours",
    "max_continuous_dark_h": "maximum longest darkness the vehicle survives, hours",
    "min_sun_elevation_deg": "minimum mean Sun elevation while visible, degrees",
    "min_earth_visibility_fraction": "minimum share of time with Earth visible, fraction 0-1",
    "min_continuous_earth_visibility_h": "minimum longest continuous Earth contact, hours",
    "max_earth_outage_h": "maximum longest period without Earth in view, hours",
    "min_sun_and_earth_visible_fraction": "minimum share of time with Sun and Earth both "
    "visible, fraction 0-1",
    "max_slope_deg": "maximum slope over the landing disk, degrees",
    "latitude_min_deg": "southern latitude bound, degrees (south negative)",
    "latitude_max_deg": "northern latitude bound, degrees (south negative)",
    "longitude_min_deg": "western longitude bound, east-positive degrees -180 to 180",
    "longitude_max_deg": "eastern longitude bound, east-positive degrees -180 to 180",
    "landing_precision_m": "landing precision radius, meters",
    "operating_range_m": "operating range around the landing point, meters",
    "traverse_slope_limit_deg": "steepest slope rovers or crews may cross, degrees",
    "observer_height_above_ground_m": "height of solar panels or antenna above ground, meters",
}


class _StatedValue(BaseModel):
    """One value the user stated, as returned by the extraction call."""

    model_config = ConfigDict(extra="forbid")

    name: Literal[USER_FIELDS]
    value: float
    rationale: str = Field(max_length=300)


class _Extraction(BaseModel):
    """Answer of the extraction call, validated before use."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["rank", "ask", "other"]
    reply: str = Field(max_length=1000)
    archetype_id: str | None
    region_id: str | None = None
    start_utc: str | None
    duration_h: float | None = Field(gt=0.0)
    fields: list[_StatedValue]
    cleared: list[Literal[USER_FIELDS]]


def _extraction_schema(
    archetype_ids: Sequence[str], region_ids: Sequence[str] = ()
) -> dict[str, Any]:
    """JSON Schema of the extraction answer, given to the CLI for validation.

    Args:
        archetype_ids: Archetype ids the model may pick.
        region_ids: Region ids the model may pick.
    """
    names = list(USER_FIELDS)
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "action",
            "reply",
            "archetype_id",
            "region_id",
            "start_utc",
            "duration_h",
            "fields",
            "cleared",
        ],
        "properties": {
            "action": {"type": "string", "enum": ["rank", "ask", "other"]},
            "reply": {"type": "string"},
            "archetype_id": {"type": ["string", "null"], "enum": [*archetype_ids, None]},
            "region_id": {"type": ["string", "null"], "enum": [*region_ids, None]},
            "start_utc": {"type": ["string", "null"]},
            "duration_h": {"type": ["number", "null"]},
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "value", "rationale"],
                    "properties": {
                        "name": {"type": "string", "enum": names},
                        "value": {"type": "number"},
                        "rationale": {"type": "string"},
                    },
                },
            },
            "cleared": {"type": "array", "items": {"type": "string", "enum": names}},
        },
    }


_EXPLAIN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["items"],
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["site_id", "text"],
                "properties": {"site_id": {"type": "string"}, "text": {"type": "string"}},
            },
        }
    },
}


def extraction_system_prompt(
    archetypes: Mapping[str, Archetype], regions: Mapping[str, Region] | None = None
) -> str:
    """Return the task instructions of the extraction call.

    Args:
        archetypes: Archetypes by id; their summaries tell the model what each one is.
        regions: Named regions by id; only names and summaries are shown, never their bounds.
    """
    fields = "\n".join(f"- {name}: {_FIELD_HELP[name]}" for name in USER_FIELDS)
    kinds = "\n".join(f"- {a.id}: {a.name}. {a.summary}" for a in archetypes.values())
    places = "\n".join(f"- {r.id}: {r.label}. {r.summary}" for r in (regions or {}).values())
    return f"""You turn a conversation about a lunar landing mission into search parameters for a
tool that ranks candidate landing sites from a fixed catalog. The tool computes every lunar
quantity itself; you only read what the user wants.

Parameters you may set (field: meaning, unit):
{fields}

Mission archetypes (the tool fills their typical values itself, with sources):
{kinds}

Named regions of the Moon (the tool applies their bounds itself, with sources):
{places or "- none available"}

Rules:
1. Never invent a number. Put a field in "fields" only when the user stated its value, or an
   unambiguous equivalent (e.g. "two weeks" -> 336 hours, "half the time" -> 0.5). Fractions are
   0-1, never percentages. Report every value stated anywhere in the conversation, earlier turns
   included, unless the user withdrew it. Give each one a short "rationale" quoting the user.
2. "archetype_id": the archetype that matches the mission described, or null if none fits.
   "region_id": the named region the user places the mission in ("near the south pole", "on the
   far side"), or null when the user names none or none in the list fits. Keep the current region
   unless the user changes or drops it. Never turn a region into latitude or longitude numbers.
3. "start_utc": ISO 8601 date-time in UTC only if the user gave a date; "duration_h": mission
   duration in hours only if the user gave one. Otherwise null (the tool uses the archetype or
   the window shown in the GUI).
4. "cleared": fields the user explicitly asked to drop or ignore.
5. Fields listed as locked were set by hand in the GUI: do not put them in "fields".
6. "action": "rank" when the user wants landing sites and the conversation gives an archetype
   or at least one value; "ask" when the user wants sites but neither is known (then "reply" is
   ONE short question about the mission type or its key need); "other" when the message is not
   about choosing landing sites.
7. "reply": one or two short sentences in the user's language saying what you understood. Use no
   numbers except those the user wrote.
"""


def _current_value(requirements: MissionRequirements, field: str) -> float | None:
    """Return the value of a user-settable field, None when unset (area defaults count as unset)."""
    if field in AREA_FIELDS:
        area = requirements.area
        if area is None or field not in area.model_fields_set:
            return None
        return float(getattr(area, field))
    value = getattr(requirements, field)
    return None if value is None else float(value)


def _parse_start(text: str) -> datetime:
    """Parse an ISO 8601 date or date-time; a naive value is read as UTC."""
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def merge_requirements(
    extraction: _Extraction,
    request: AiRequest,
    archetypes: Mapping[str, Archetype],
    regions: Mapping[str, Region] | None = None,
) -> MissionRequirements:
    """Build the requirements of one turn: archetype, region, user values, then locked fields.

    Args:
        extraction: Validated answer of the extraction call.
        request: The request (current parameters, locked fields, GUI window).
        archetypes: Archetypes by id.
        regions: Named regions by id (spec AI-7).

    Returns:
        Validated requirements with sources and rationale per field.

    Raises:
        ValueError: If the values do not fit the contract (e.g. a fraction above 1).
    """
    values: dict[str, float | None] = {}
    sources: dict[str, RequirementSource] = {}
    rationale: dict[str, str] = {}
    archetype = archetypes.get(extraction.archetype_id or "")
    if archetype is not None:
        for field in USER_FIELDS:
            value = _current_value(archetype.requirements, field)
            if value is not None:
                values[field] = value
                sources[field] = RequirementSource.ARCHETYPE
                rationale[field] = f"{archetype.name}: {archetype.source_of(field) or 'typical'}"
    region = (regions or {}).get(extraction.region_id or "")
    if region is not None:
        for field, value in region.bounds().items():
            values[field] = value
            sources[field] = RequirementSource.REGION
            rationale[field] = f"{region.label}: {region.source}"
    for stated in extraction.fields:
        values[stated.name] = stated.value
        sources[stated.name] = RequirementSource.USER
        rationale[stated.name] = stated.rationale
    for field in extraction.cleared:
        values[field] = None
        sources.pop(field, None)
        rationale.pop(field, None)
    current = request.requirements
    locked = set(request.locked_fields)
    if current is not None:
        for field in locked & set(USER_FIELDS):
            values[field] = _current_value(current, field)
            sources[field] = RequirementSource.USER
            rationale[field] = current.rationale.get(field, "Set by hand in the GUI.")

    window = _window(extraction, request, archetype, sources)
    if archetype is not None:
        _follow_whole_stay(archetype, window, values, sources, rationale)
    area_values = {f: values[f] for f in AREA_FIELDS if values.get(f) is not None}
    for field in AREA_FIELDS:
        if field not in area_values:
            sources.pop(field, None)
            rationale.pop(field, None)
    scalars = {f: values.get(f) for f in SCALAR_FIELDS}
    for field, value in scalars.items():
        if value is None:
            sources.pop(field, None)
            rationale.pop(field, None)
    return MissionRequirements(
        window=window,
        area=OperationsArea(**area_values) if area_values else None,
        **scalars,
        archetype_id=archetype.id if archetype is not None else None,
        region_id=region.id if region is not None else None,
        field_sources=sources,
        rationale=rationale,
        source_request=request.text,
    )


def _follow_whole_stay(
    archetype: Archetype,
    window: TimeWindow,
    values: dict[str, float | None],
    sources: dict[str, RequirementSource],
    rationale: dict[str, str],
) -> None:
    """Stretch "for the whole stay" archetype values to the actual mission window.

    An archetype duration value equal to its mission duration means "for the whole stay" (e.g.
    the short crewed stay needs continuous light for its 156 h); when the user asks for another
    duration, that value follows the window. Values the user stated are left alone.

    Args:
        archetype: The archetype of the turn.
        window: The mission window of the turn.
        values: Field values being merged; updated in place.
        sources: Field sources; only fields still sourced from the archetype change.
        rationale: Field rationale; updated in place for the fields that change.
    """
    stay_h = window_hours(window)
    duration_h = archetype.mission_duration_h
    if duration_h is None or stay_h == duration_h:
        return
    for field in WHOLE_STAY_FIELDS:
        if sources.get(field) == RequirementSource.ARCHETYPE and values.get(field) == duration_h:
            values[field] = stay_h
            rationale[field] = (
                f"{archetype.name}: for the whole stay ({archetype.source_of(field) or 'typical'})"
            )


def _window(
    extraction: _Extraction,
    request: AiRequest,
    archetype: Archetype | None,
    sources: dict[str, RequirementSource],
) -> TimeWindow:
    """Return the window of the turn and record its source in ``sources``."""
    current = request.requirements
    if "window" in request.locked_fields and current is not None and current.window is not None:
        sources["window"] = RequirementSource.USER
        return current.window
    default = request.default_window
    start = _parse_start(extraction.start_utc) if extraction.start_utc else default.start_utc
    if extraction.duration_h is not None:
        hours = extraction.duration_h
    elif archetype is not None and archetype.mission_duration_h is not None:
        hours = archetype.mission_duration_h
    else:
        hours = window_hours(default)
    if extraction.start_utc or extraction.duration_h is not None:
        sources["window"] = RequirementSource.USER
    elif archetype is not None and archetype.mission_duration_h is not None:
        sources["window"] = RequirementSource.ARCHETYPE
    else:
        sources["window"] = RequirementSource.DEFAULT
    return TimeWindow(
        start_utc=start, end_utc=start + timedelta(hours=hours), step_minutes=default.step_minutes
    )


def requirement_numbers(requirements: MissionRequirements) -> list[float]:
    """Every number of ``requirements`` (thresholds, area, window length), for the number check."""
    numbers = [v for f in USER_FIELDS if (v := _current_value(requirements, f)) is not None]
    if requirements.window is not None:
        numbers.append(window_hours(requirements.window))
    return numbers


def format_value(criterion: Criterion, value: float) -> str:
    """Format a criterion value for the user: percent, whole hours or one-decimal degrees."""
    if criterion.unit == "fraction":
        return f"{value * 100:.0f}%"
    if criterion.unit == "h":
        return f"{value:.0f} h"
    return f"{value:.1f} deg"


def _comparisons(score: SiteScore, requirements: MissionRequirements) -> list[dict[str, Any]]:
    """Per set criterion of one site: label, value and threshold as text, met, margin, shortfall."""
    assert requirements.window is not None
    window_h = window_hours(requirements.window)
    rows = []
    for criterion in set_criteria(requirements):
        threshold = float(getattr(requirements, criterion.field))
        value = score.criterion_values.get(criterion.field)
        met, margin, shortfall = margin_and_shortfall(criterion, value, threshold, window_h)
        rows.append(
            {
                "field": criterion.field,
                "label": criterion.label,
                "value": "undefined" if value is None else format_value(criterion, value),
                "required": ("at least " if criterion.kind == "min" else "at most ")
                + format_value(criterion, threshold),
                "met": met,
                "margin": margin,
                "shortfall": shortfall,
            }
        )
    return rows


def template_rationale(score: SiteScore, requirements: MissionRequirements) -> str:
    """Deterministic one-sentence explanation, used when the LLM text is missing or fails."""
    rows = _comparisons(score, requirements)
    if score.all_constraints_met:
        best = max(rows, key=lambda r: r["margin"])
        return (
            f"Meets all {len(rows)} constraints; largest margin on {best['label']} "
            f"({best['value']}, {best['required']})."
        )
    failed = [r for r in rows if not r["met"]]
    worst = max(failed, key=lambda r: r["shortfall"])
    return (
        f"Misses {len(failed)} of {len(rows)} constraints; worst is {worst['label']} "
        f"({worst['value']}, {worst['required']})."
    )


def _allowed_numbers(score: SiteScore, requirements: MissionRequirements) -> list[float]:
    """Numbers an explanation of ``score`` may cite."""
    allowed = list(score.criterion_values.values()) + requirement_numbers(requirements)
    allowed += [float(score.rank), float(len(score.constraints_met))]
    allowed.append(float(sum(score.constraints_met.values())))
    return allowed


class ChatAssistant:
    """Conversation to requirements, ranking and explanations (spec AI-1, AI-3).

    Attributes:
        ranker: Deterministic ranking.
        catalog: Site catalog, for site names in explanations.
        llm: Language model client.
        archetypes: Mission archetypes by id.
        regions: Named regions by id (spec AI-7); empty when the table does not exist yet.
    """

    def __init__(
        self,
        ranker: Ranker,
        catalog: SiteCatalog,
        llm: LlmClient,
        archetypes: Mapping[str, Archetype],
        regions: Mapping[str, Region] | None = None,
    ) -> None:
        """Store the collaborators.

        Args:
            ranker: Deterministic ranking.
            catalog: Site catalog.
            llm: Language model client.
            archetypes: Mission archetypes by id.
            regions: Named regions by id; None means no regions.
        """
        self.ranker = ranker
        self.catalog = catalog
        self.llm = llm
        self.archetypes = archetypes
        self.regions: Mapping[str, Region] = regions or {}

    def _extraction_prompt(self, request: AiRequest) -> str:
        """Return the data of the extraction call as JSON text."""
        current: dict[str, Any] = {}
        if request.requirements is not None:
            # Only fields with a source are set: an area sent back by the GUI also carries the
            # contract defaults of the fields nobody chose.
            for field, source in request.requirements.field_sources.items():
                value = (
                    _current_value(request.requirements, field) if field in USER_FIELDS else None
                )
                if value is not None:
                    current[field] = {"value": value, "source": str(source)}
        payload = {
            "conversation": [m.model_dump() for m in request.history],
            "new_message": request.text,
            "current_parameters": current,
            "current_archetype": request.requirements.archetype_id
            if request.requirements
            else None,
            "current_region": request.requirements.region_id if request.requirements else None,
            "locked_fields": request.locked_fields,
            "gui_window_start_utc": request.default_window.start_utc.isoformat(),
        }
        return json.dumps(payload, ensure_ascii=False, indent=1)

    def _extract(self, request: AiRequest) -> tuple[_Extraction, MissionRequirements]:
        """Run the extraction call, retrying once with the error when the answer is invalid.

        Raises:
            LlmError: If no valid answer is obtained in ``MAX_ATTEMPTS`` calls.
        """
        system = extraction_system_prompt(self.archetypes, self.regions)
        schema = _extraction_schema(list(self.archetypes), list(self.regions))
        prompt = self._extraction_prompt(request)
        error: Exception | None = None
        for _ in range(MAX_ATTEMPTS):
            attempt = (
                prompt
                if error is None
                else (f"{prompt}\n\nYour previous answer was invalid: {error}. Answer again.")
            )
            raw = self.llm.complete_json(system, attempt, schema)
            try:
                extraction = _Extraction.model_validate(raw)
                return extraction, merge_requirements(
                    extraction, request, self.archetypes, self.regions
                )
            except (ValidationError, ValueError) as invalid:
                error = invalid
        raise LlmError(f"the AI could not read the request into valid parameters: {error}")

    def _checked_reply(
        self, reply: str, request: AiRequest, requirements: MissionRequirements
    ) -> str:
        """Return the LLM reply if every number in it comes from the user or the parameters."""
        stated = " ".join([request.text, *(m.text for m in request.history)])
        allowed = requirement_numbers(requirements)
        allowed += [number for number, _ in numbers_in(stated)]
        if unsupported_numbers(reply, allowed):
            logger.warning("AI reply dropped, unsupported numbers: %r", reply)
            return "Parameters updated from your request."
        return reply.strip()

    def _summary(self, ranking: SiteRanking) -> str:
        """Deterministic sentence on the ranking outcome."""
        if not ranking.results:
            return "No catalog site is in the search scope."
        names = {site.id: site.name for site in self.catalog.list_sites()}
        best = ranking.results[0]
        name = names.get(best.site_id, best.site_id)
        passing = sum(score.all_constraints_met for score in ranking.results)
        if passing == 0:
            return f"No site meets every constraint; the closest is {name}."
        return f"{passing} of {len(ranking.results)} sites meet every constraint; best: {name}."

    def ask(self, request: AiRequest) -> AiAnswer:
        """Answer one chat turn.

        Args:
            request: The new message with the conversation and the GUI state.

        Returns:
            Updated requirements, the ranking (None when the assistant asks back or the message
            is not about sites) and a short message.

        Raises:
            LlmError: If the LLM gives no valid answer.
        """
        extraction, requirements = self._extract(request)
        reply = self._checked_reply(extraction.reply, request, requirements)
        if extraction.action != "rank" or not set_criteria(requirements):
            if extraction.action == "rank":
                reply = (
                    "Which kind of mission is it, or what does it need most "
                    "(light, Earth contact, flat ground)?"
                )
            return AiAnswer(requirements=requirements, ranking=None, message=reply)
        ranking = self.ranker.rank(requirements)
        return AiAnswer(
            requirements=requirements, ranking=ranking, message=f"{reply} {self._summary(ranking)}"
        )

    def explain(self, ranking: SiteRanking, language_hint: str = "") -> SiteRanking:
        """Add a one-sentence rationale to every result.

        The top ``EXPLAINED_SITES`` get an LLM sentence that passes the number check; every other
        result, and any failing sentence, gets ``template_rationale``.

        Args:
            ranking: A ranking from the deterministic engine.
            language_hint: The user's latest message, so the text matches their language.

        Returns:
            The same ranking with ``rationale`` set on every result.
        """
        requirements = ranking.requirements
        names = {site.id: site.name for site in self.catalog.list_sites()}
        top = ranking.results[:EXPLAINED_SITES]
        written: dict[str, str] = {}
        if top and requirements.window is not None:
            payload = {
                "language_of": language_hint,
                "sites": [
                    {
                        "site_id": s.site_id,
                        "name": names.get(s.site_id, s.site_id),
                        "rank": s.rank,
                        "meets_all_constraints": s.all_constraints_met,
                        "criteria": [
                            {k: r[k] for k in ("label", "value", "required", "met")}
                            for r in _comparisons(s, requirements)
                        ],
                    }
                    for s in top
                ],
            }
            system = (
                "You explain a ranking of lunar landing sites to a mission planner. For each site "
                "write one sentence of at most 25 words saying why it ranks where it does, citing "
                "its strongest point or its main violation. Copy numbers exactly as given in "
                "'value' and 'required'; write no other number. Use the language of 'language_of' "
                "(English if empty). Answer for every site_id."
            )
            try:
                answer = self.llm.complete_json(
                    system, json.dumps(payload, ensure_ascii=False), _EXPLAIN_SCHEMA
                )
                for item in answer.get("items", []):
                    if isinstance(item, dict):
                        written[str(item.get("site_id"))] = str(item.get("text", "")).strip()
            except LlmError:
                logger.exception("explanations: LLM failed, using deterministic sentences")
        by_id = {s.site_id: s for s in top}
        results = []
        for score in ranking.results:
            text = written.get(score.site_id, "")
            if (
                score.site_id not in by_id
                or not text
                or len(text) > 400
                or unsupported_numbers(text, _allowed_numbers(score, requirements))
            ):
                text = template_rationale(score, requirements)
            results.append(score.model_copy(update={"rationale": text}))
        return ranking.model_copy(update={"results": results})
