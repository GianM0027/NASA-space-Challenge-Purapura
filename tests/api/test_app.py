# ABOUTME: Smoke tests of the REST API (spec IF-4): endpoints answer with contract-valid payloads
# ABOUTME: Owner: Gian; skipped automatically when the api dependency group is not installed

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from lunarnav.api.main import build_app
from lunarnav.contracts import (
    AiAnswer,
    Evaluation,
    RobustnessReport,
    Site,
    SiteRanking,
)

START = datetime(2027, 1, 1, tzinfo=UTC)
WINDOW = {
    "start_utc": START.isoformat(),
    "end_utc": (START + timedelta(days=2)).isoformat(),
    "step_minutes": 240,
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_app())


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_sites_returns_contract_sites(client: TestClient) -> None:
    response = client.get("/api/sites")
    assert response.status_code == 200
    sites = [Site.model_validate(item) for item in response.json()]
    assert sites


def test_evaluate_by_site_id(client: TestClient) -> None:
    site_id = client.get("/api/sites").json()[0]["id"]
    response = client.post("/api/evaluate", json={"site_id": site_id, "window": WINDOW})
    assert response.status_code == 200
    assert Evaluation.model_validate(response.json()).site_id == site_id


def test_evaluate_by_location(client: TestClient) -> None:
    body = {"location": {"lat_deg": -85.0, "lon_deg": 30.0}, "window": WINDOW}
    response = client.post("/api/evaluate", json=body)
    assert response.status_code == 200
    evaluation = Evaluation.model_validate(response.json())
    assert evaluation.site_id is None
    assert evaluation.location.lat_deg == -85.0


def test_evaluate_requires_exactly_one_of_site_id_and_location(client: TestClient) -> None:
    neither = client.post("/api/evaluate", json={"window": WINDOW})
    both = client.post(
        "/api/evaluate",
        json={"site_id": "x", "location": {"lat_deg": 0, "lon_deg": 0}, "window": WINDOW},
    )
    assert neither.status_code == 422
    assert both.status_code == 422


def test_unknown_site_is_404(client: TestClient) -> None:
    response = client.post("/api/evaluate", json={"site_id": "no-such-site", "window": WINDOW})
    assert response.status_code == 404


def test_compare_accepts_two_to_four_scenarios(client: TestClient) -> None:
    scenario = {"location": {"lat_deg": 0, "lon_deg": 0}, "window": WINDOW}
    ok = client.post("/api/compare", json={"scenarios": [scenario, scenario]})
    too_few = client.post("/api/compare", json={"scenarios": [scenario]})
    assert ok.status_code == 200
    assert len([Evaluation.model_validate(e) for e in ok.json()]) == 2
    assert too_few.status_code == 422


def test_add_user_site(client: TestClient) -> None:
    site = {
        "id": "my-site",
        "name": "My site",
        "location": {"lat_deg": 10, "lon_deg": 20},
        "origin": "user",
        "status": "custom",
    }
    response = client.post("/api/sites", json=site)
    assert response.status_code == 200
    assert Site.model_validate(response.json()).id == "my-site"
    assert "my-site" in [s["id"] for s in client.get("/api/sites").json()]


def test_rank(client: TestClient) -> None:
    response = client.post("/api/rank", json={"min_illumination_fraction": 0.5})
    assert response.status_code == 200
    SiteRanking.model_validate(response.json())


def test_ai_ask(client: TestClient) -> None:
    response = client.post("/api/ai/ask", json={"text": "polar rover, recharge often"})
    assert response.status_code == 200
    AiAnswer.model_validate(response.json())


def test_mission_analysis(client: TestClient) -> None:
    body = {"location": {"lat_deg": 0, "lon_deg": 0}, "window": WINDOW, "shifts_days": [1, 7]}
    response = client.post("/api/mission-analysis", json=body)
    assert response.status_code == 200
    RobustnessReport.model_validate(response.json())
