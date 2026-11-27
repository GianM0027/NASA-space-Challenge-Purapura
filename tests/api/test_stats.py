# ABOUTME: Tests of the internal usage statistics (D47): what is counted, and that no ID is stored
# ABOUTME: Owner: Gian. A fake clock moves days; the database is pytest's tmp_path

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from lunarnav.accounts import AccountStore
from lunarnav.api.main import build_app
from lunarnav.api.stats import Stats
from lunarnav.api.wiring import build_services

DAY = 86_400.0
START = 1_800_000_000.0  # a fixed instant, 2027-01-15 UTC
PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile"
DESKTOP = "Mozilla/5.0 (X11; Linux x86_64) Chrome/158"


class _Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> _Clock:
    return _Clock()


@pytest.fixture
def stats(tmp_path: Path, clock: _Clock) -> Stats:
    return Stats(tmp_path / "stats.sqlite3", clock=clock)


def test_visits_visitors_and_devices(stats: Stats) -> None:
    for _ in range(3):
        stats.record_request("GET", "/api/modules", 200, "203.0.113.5", PHONE)
    stats.record_request("GET", "/api/modules", 200, "198.51.100.7", DESKTOP)
    summary = stats.summary(1)
    assert summary["visits"] == [4]
    assert summary["visitors"] == [2]  # the same phone counts once a day
    assert {d["name"]: d["count"] for d in summary["devices"]} == {"phone": 3, "desktop": 1}


def test_a_visitor_counts_again_the_next_day_only(stats: Stats, clock: _Clock) -> None:
    stats.record_request("GET", "/api/modules", 200, "203.0.113.5", PHONE)
    clock.now += DAY
    stats.record_request("GET", "/api/modules", 200, "203.0.113.5", PHONE)
    summary = stats.summary(2)
    assert summary["visitors"] == [1, 1]
    assert len(summary["days"]) == 2


def test_features_errors_and_failed_requests(stats: Stats) -> None:
    stats.record_request("POST", "/api/evaluate", 200, "a", DESKTOP)
    stats.record_request("POST", "/api/evaluate", 422, "a", DESKTOP)  # failed: not a use
    stats.record_request("POST", "/api/ai/ask", 200, "a", DESKTOP)
    stats.record_request("POST", "/api/rank", 500, "a", DESKTOP)
    stats.record_request("GET", "/api/sites", 429, "a", DESKTOP)
    summary = stats.summary(1)
    assert {f["name"]: f["count"] for f in summary["features"]} == {
        "site evaluation": 1,
        "AI question": 1,
    }
    assert {e["name"]: e["count"] for e in summary["errors"]} == {
        "server error": 1,
        "rate limited": 1,
    }


def test_no_address_or_user_agent_reaches_the_database(stats: Stats, tmp_path: Path) -> None:
    stats.record_request("GET", "/api/modules", 200, "203.0.113.5", PHONE)
    stats.flush()
    raw = (tmp_path / "stats.sqlite3").read_bytes()
    assert b"203.0.113.5" not in raw
    assert b"iPhone" not in raw


def test_summary_covers_every_day_and_drops_old_data(stats: Stats, clock: _Clock) -> None:
    stats.record("visits")
    clock.now += 3 * DAY
    summary = stats.summary(5)
    assert len(summary["days"]) == 5 and summary["visits"] == [0, 1, 0, 0, 0]
    clock.now += 500 * DAY
    stats.record("visits")
    stats.flush()
    assert sum(stats.summary(365)["visits"]) == 1  # the old day was deleted


def test_api_counts_requests_and_shows_stats_to_admins_only(tmp_path: Path) -> None:
    store = AccountStore(tmp_path / "accounts.sqlite3")
    store.set_admins(["gian"])
    stats = Stats(tmp_path / "stats.sqlite3")
    app = build_app(*build_services(use_real=False), accounts=store, stats=stats)
    visitor, admin = TestClient(app), TestClient(app)
    visitor.get("/api/modules", headers={"User-Agent": PHONE})
    site = next(s["id"] for s in visitor.get("/api/sites").json())
    window = {
        "start_utc": "2027-01-01T00:00:00Z",
        "end_utc": "2027-01-02T00:00:00Z",
        "step_minutes": 240,
    }
    assert (
        visitor.post("/api/evaluate", json={"site_id": site, "window": window}).status_code == 200
    )
    assert visitor.post("/api/stats/event", json={"name": "pdf_report"}).status_code == 204
    assert visitor.post("/api/stats/event", json={"name": "anything"}).status_code == 204  # ignored
    assert visitor.get("/api/admin/stats").status_code == 401
    admin.post("/api/auth/register", json={"username": "gian", "password": "correct horse battery"})
    summary = admin.get("/api/admin/stats", params={"days": 7}).json()
    assert summary["visits"][-1] == 1
    features = {f["name"]: f["count"] for f in summary["features"]}
    assert features["site evaluation"] == 1 and features["PDF report"] == 1
    assert "anything" not in features
    assert summary["sites"] == [{"name": site, "count": 1}]
