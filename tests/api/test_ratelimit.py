# ABOUTME: Tests of the per-client rate limiting (decision D44): windows, groups, 429 answers
# ABOUTME: Owner: Gian. A fake clock drives the sliding window; no test sleeps

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from lunarnav.api.main import build_app
from lunarnav.api.ratelimit import (
    DEFAULT_LIMITS,
    RateLimiter,
    parse_limits,
    route_group,
)
from lunarnav.api.wiring import build_services


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_window_allows_the_limit_then_waits_until_the_oldest_hit_expires() -> None:
    clock = _Clock()
    limiter = RateLimiter({"default": 3}, window_s=60, clock=clock)
    for _ in range(3):
        assert limiter.check("a", ["default"]) == 0
        clock.now += 10
    assert limiter.check("a", ["default"]) == pytest.approx(30)  # first hit at 1000, now 1030
    clock.now += 30
    assert limiter.check("a", ["default"]) == 0


def test_clients_are_counted_separately() -> None:
    limiter = RateLimiter({"default": 1}, clock=_Clock())
    assert limiter.check("a", ["default"]) == 0
    assert limiter.check("b", ["default"]) == 0
    assert limiter.check("a", ["default"]) > 0


def test_a_refused_request_is_not_counted_in_any_group() -> None:
    clock = _Clock()
    limiter = RateLimiter({"default": 10, "heavy": 1}, clock=clock)
    assert limiter.check("a", ["default", "heavy"]) == 0
    assert limiter.check("a", ["default", "heavy"]) > 0
    # The refused heavy request did not use a default slot: 9 light requests still pass.
    for _ in range(9):
        assert limiter.check("a", ["default"]) == 0
    assert limiter.check("a", ["default"]) > 0


def test_oldest_client_is_forgotten_beyond_the_cap() -> None:
    limiter = RateLimiter({"default": 1}, clock=_Clock(), max_clients=2)
    for client in ("a", "b", "c"):
        assert limiter.check(client, ["default"]) == 0
    assert limiter.check("a", ["default"]) == 0  # "a" was forgotten, so it starts again


@pytest.mark.parametrize(
    ("method", "path", "group"),
    [
        ("POST", "/api/evaluate", "heavy"),
        ("POST", "/api/mission-analysis", "heavy"),
        ("POST", "/api/rank", "heavy"),
        ("POST", "/api/ai/ask", "ai"),
        ("POST", "/api/tradeoff/export", "ai"),
        ("POST", "/api/sites", "write"),
        ("DELETE", "/api/sites/user-x", "write"),
        ("GET", "/api/sites", None),
        ("GET", "/api/sky", None),
    ],
)
def test_route_groups(method: str, path: str, group: str | None) -> None:
    assert route_group(method, path) == group


def test_parse_limits() -> None:
    assert parse_limits(None) == DEFAULT_LIMITS
    assert parse_limits("off") is None
    assert parse_limits("ai=5, heavy=10") == {**DEFAULT_LIMITS, "ai": 5, "heavy": 10}
    with pytest.raises(ValueError, match="unknown"):
        parse_limits("login=3")
    with pytest.raises(ValueError, match="positive"):
        parse_limits("ai=0")


def test_api_answers_429_with_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUNARNAV_RATE_LIMITS", "default=3")
    api = TestClient(build_app(*build_services(use_real=False)))
    for _ in range(3):
        assert api.get("/api/sites").status_code == 200
    refused = api.get("/api/sites")
    assert refused.status_code == 429
    assert int(refused.headers["retry-after"]) >= 1
    assert "Too many requests" in refused.json()["detail"]
    # Health checks and the frontend never count.
    assert api.get("/api/health").status_code == 200


def test_limits_can_be_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUNARNAV_RATE_LIMITS", "off")
    api = TestClient(build_app(*build_services(use_real=False)))
    assert all(api.get("/api/sites").status_code == 200 for _ in range(400))
