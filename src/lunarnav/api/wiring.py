# ABOUTME: API composition root: each module's factory when it exists, a placeholder otherwise
# ABOUTME: Owner: Gian. Factory names are a contract (spec IF-5), added by each module owner

"""Automatic wiring of the LunarNav modules (spec IF-5).

Each module owner exposes one factory function from the module's package ``__init__``:

* ``catalog.build_catalog()`` -> ``SiteCatalog``
* ``ephemeris.build_ephemeris_provider()`` -> ``EphemerisProvider``
* ``terrain.build_terrain_provider()`` -> ``TerrainProvider``
* ``evaluation.build_evaluator(ephemeris, terrain)`` -> ``Evaluator``
* ``mission_analysis.build_mission_analyzer(evaluator)`` -> ``MissionAnalyzer``
* ``ai.build_ranker(catalog, evaluator)`` -> ``Ranker``
* ``ai.build_assistant(ranker, catalog)`` -> ``Assistant``

When the factory exists the API uses it; when it is missing, cannot be imported (dependency
group not installed) or raises, the API falls back to the placeholder and reports why in
``GET /api/modules``. So an owner sees their module in the GUI by adding the factory on their
own branch, without touching ``lunarnav.api``.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from typing import Any

from lunarnav.api.services import (
    ExampleAnalyzer,
    ExampleAssistant,
    ExampleCatalog,
    ExampleEphemerisProvider,
    ExampleEvaluator,
    ExampleRanker,
    ExampleTerrainProvider,
    Services,
)

logger = logging.getLogger(__name__)

ModuleStatus = dict[str, str]


def find_factory(package: str, name: str) -> Callable[..., Any] | None:
    """Return the factory ``lunarnav.<package>.<name>`` if it can be imported.

    Args:
        package: Subpackage of ``lunarnav`` (e.g. "terrain").
        name: Factory function name (e.g. "build_terrain_provider").

    Returns:
        The callable, or None when the package does not import or has no such attribute.
    """
    try:
        module = importlib.import_module(f"lunarnav.{package}")
    except ImportError as error:
        logger.warning("lunarnav.%s not importable, using the placeholder: %s", package, error)
        return None
    factory = getattr(module, name, None)
    return factory if callable(factory) else None


def _build[T](
    status: ModuleStatus,
    key: str,
    package: str,
    name: str,
    placeholder: Callable[[], T],
    *args: object,
    use_real: bool = True,
) -> T:
    """Build one service with its real factory, or the placeholder, recording which in ``status``.

    Args:
        status: Mapping updated in place: ``key`` -> "real", "example" or "error: <reason>".
        key: Name of the service in the status report.
        package: Subpackage of ``lunarnav`` owning the factory.
        name: Factory function name.
        placeholder: Zero-argument callable building the fallback.
        *args: Arguments passed to the real factory.
        use_real: When False the factory is not looked up; the placeholder is always used.

    Returns:
        The real service when its factory exists and succeeds, the placeholder otherwise.
    """
    factory = find_factory(package, name) if use_real else None
    if factory is None:
        status[key] = "example"
        return placeholder()
    try:
        service: T = factory(*args)
    except Exception as error:  # an owner's bug must not take the whole app down
        logger.exception("lunarnav.%s.%s failed, using the placeholder", package, name)
        status[key] = f"error: {type(error).__name__}: {error}"
        return placeholder()
    status[key] = "real"
    return service


def build_services(use_real: bool = True) -> tuple[Services, ModuleStatus]:
    """Build every service, preferring real modules over placeholders.

    Args:
        use_real: When False only placeholders are built: no real module is imported, so nothing
            touches the network or the disk cache. Tests of the API itself use this.

    Returns:
        The services, and for each of them whether it is "real", "example" or "error: ...".
    """
    status: ModuleStatus = {}

    def build[T](
        key: str, package: str, name: str, placeholder: Callable[[], T], *args: object
    ) -> T:
        """Build one service with this call's ``status`` and ``use_real``."""
        return _build(status, key, package, name, placeholder, *args, use_real=use_real)

    catalog = build("catalog", "catalog", "build_catalog", ExampleCatalog)
    ephemeris = build(
        "ephemeris", "ephemeris", "build_ephemeris_provider", ExampleEphemerisProvider
    )
    terrain = build("terrain", "terrain", "build_terrain_provider", ExampleTerrainProvider)
    evaluator = build(
        "evaluation",
        "evaluation",
        "build_evaluator",
        lambda: ExampleEvaluator(ephemeris, terrain),
        ephemeris,
        terrain,
    )
    analyzer = build(
        "mission_analysis",
        "mission_analysis",
        "build_mission_analyzer",
        ExampleAnalyzer,
        evaluator,
    )
    ranker = build("ranking", "ai", "build_ranker", ExampleRanker, catalog, evaluator)
    assistant = build("assistant", "ai", "build_assistant", ExampleAssistant, ranker, catalog)
    return Services(catalog, ephemeris, evaluator, analyzer, ranker, assistant), status
