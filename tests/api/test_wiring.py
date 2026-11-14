# ABOUTME: Tests of the API composition root: real module factories are used when present
# ABOUTME: Owner: Gian; placeholders are the fallback when a factory is missing or fails

import sys
import types

import pytest

pytest.importorskip("fastapi")

from lunarnav.api import wiring
from lunarnav.api.services import ExampleCatalog, ExampleEvaluator
from lunarnav.contracts import EphemerisProvider, Site, TerrainProvider


def _fake_module(monkeypatch: pytest.MonkeyPatch, name: str, **attrs: object) -> None:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)


PACKAGES = ("catalog", "ephemeris", "terrain", "evaluation", "mission_analysis", "ai")


@pytest.fixture(autouse=True)
def _no_real_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    # Start every test from "no module has a factory", whatever is merged in the repo; each test
    # then adds the fake module it is about.
    for package in PACKAGES:
        _fake_module(monkeypatch, f"lunarnav.{package}")


class _RealCatalog(ExampleCatalog):
    """Stands in for Michael's catalog: same behaviour, different class."""


def test_find_factory_returns_none_when_module_has_no_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_module(monkeypatch, "lunarnav.catalog")
    assert wiring.find_factory("catalog", "build_catalog") is None


def test_find_factory_returns_the_factory_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_module(monkeypatch, "lunarnav.catalog", build_catalog=_RealCatalog)
    assert wiring.find_factory("catalog", "build_catalog") is _RealCatalog


def test_find_factory_returns_none_when_import_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    # None in sys.modules makes `import lunarnav.terrain` raise ImportError, like a missing
    # dependency group would.
    monkeypatch.setitem(sys.modules, "lunarnav.terrain", None)
    assert wiring.find_factory("terrain", "build_terrain_provider") is None


def test_build_services_falls_back_to_examples_everywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wiring, "find_factory", lambda module, name: None)
    services, status = wiring.build_services()
    assert isinstance(services.catalog, ExampleCatalog)
    assert isinstance(services.evaluator, ExampleEvaluator)
    assert set(status.values()) == {"example"}
    assert set(status) == {
        "catalog",
        "ephemeris",
        "terrain",
        "evaluation",
        "mission_analysis",
        "ranking",
        "assistant",
    }


def test_build_services_uses_a_real_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_module(monkeypatch, "lunarnav.catalog", build_catalog=_RealCatalog)
    services, status = wiring.build_services()
    assert isinstance(services.catalog, _RealCatalog)
    assert status["catalog"] == "real"


def test_real_evaluator_receives_ephemeris_and_terrain(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, object] = {}

    def build_evaluator(ephemeris: EphemerisProvider, terrain: TerrainProvider) -> ExampleEvaluator:
        received["ephemeris"] = ephemeris
        received["terrain"] = terrain
        return ExampleEvaluator(ephemeris, terrain)

    _fake_module(monkeypatch, "lunarnav.evaluation", build_evaluator=build_evaluator)
    _, status = wiring.build_services()
    assert status["evaluation"] == "real"
    # Upstream modules are absent here, so the evaluator gets the example providers.
    assert hasattr(received["ephemeris"], "sun_earth")
    assert hasattr(received["terrain"], "horizon_mask")
    assert status["ephemeris"] == "example"
    assert status["terrain"] == "example"


def test_a_failing_factory_falls_back_and_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def build_catalog() -> Site:
        raise RuntimeError("sites.json is broken")

    _fake_module(monkeypatch, "lunarnav.catalog", build_catalog=build_catalog)
    services, status = wiring.build_services()
    assert isinstance(services.catalog, ExampleCatalog)
    assert status["catalog"].startswith("error")
    assert "sites.json is broken" in status["catalog"]


def test_use_real_false_ignores_existing_factories(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_module(monkeypatch, "lunarnav.catalog", build_catalog=_RealCatalog)
    services, status = wiring.build_services(use_real=False)
    assert type(services.catalog) is ExampleCatalog
    assert status["catalog"] == "example"
