# ABOUTME: ai module: natural-language requests to parameters, catalog ranking, explanations
# ABOUTME: Owner: Gian (MISSION.md section 4); public API uses lunarnav.contracts types only

"""Natural-language mission requests to parameters, catalog ranking and explanations.

Factories (spec IF-5, picked up by ``lunarnav.api.wiring``):

* ``build_ranker(catalog, evaluator)``: deterministic ranking (spec AI-2).
* ``build_assistant(ranker, catalog)``: chat assistant over an LLM (spec AI-1, AI-3, AI-4).
"""

from __future__ import annotations

from lunarnav.ai.archetypes import load_archetypes
from lunarnav.ai.assistant import ChatAssistant
from lunarnav.ai.llm import build_llm_client
from lunarnav.ai.ranking import CatalogRanker, Ranker
from lunarnav.ai.regions import load_regions
from lunarnav.contracts import Evaluator, SiteCatalog


def build_ranker(catalog: SiteCatalog, evaluator: Evaluator) -> CatalogRanker:
    """Build the deterministic ranker over the catalog, with the mission archetypes' weights."""
    return CatalogRanker(catalog, evaluator, load_archetypes())


def build_assistant(ranker: Ranker, catalog: SiteCatalog) -> ChatAssistant:
    """Build the chat assistant with the LLM chosen by ``LUNARNAV_LLM_PROVIDER``.

    Raises:
        RuntimeError: If the configured LLM is not available (e.g. Claude CLI not installed).
    """
    return ChatAssistant(ranker, catalog, build_llm_client(), load_archetypes(), load_regions())


__all__ = ["build_assistant", "build_ranker"]
