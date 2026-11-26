# ABOUTME: API tests of accounts (D45): guest sessions, login, private sites, proposals, review
# ABOUTME: Owner: Gian. Placeholder modules; one TestClient is one browser (it keeps cookies)

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from lunarnav.accounts import AccountStore
from lunarnav.api.accounts import COOKIE_NAME
from lunarnav.api.main import build_app
from lunarnav.api.wiring import build_services

PASSWORD = "correct horse battery"
START = datetime(2027, 1, 1, tzinfo=UTC)
WINDOW = {
    "start_utc": START.isoformat(),
    "end_utc": (START + timedelta(days=2)).isoformat(),
    "step_minutes": 240,
}


def _site(slug: str = "my-crater") -> dict[str, object]:
    return {
        "id": f"user-{slug}",
        "name": slug.replace("-", " ").title(),
        "location": {"lat_deg": -85.0, "lon_deg": 30.0},
        "origin": "user",
        "status": "custom",
        "description": "A quiet rim.",
    }


@pytest.fixture
def store(tmp_path: Path) -> AccountStore:
    return AccountStore(tmp_path / "accounts.sqlite3")


@pytest.fixture
def browser(store: AccountStore):  # type: ignore[no-untyped-def]
    """Make a new browser (TestClient with its own cookie jar) on one shared app."""
    app = build_app(*build_services(use_real=False), accounts=store)
    return lambda: TestClient(app)


def _own(client: TestClient) -> list[str]:
    return [s["id"] for s in client.get("/api/sites").json() if s["origin"] == "user"]


def test_visitor_without_saves_has_no_account(browser) -> None:  # type: ignore[no-untyped-def]
    client = browser()
    assert client.get("/api/auth/me").json() == {"user": None}
    assert client.get("/api/sites").status_code == 200
    assert COOKIE_NAME not in client.cookies


def test_first_save_starts_a_private_guest_session(browser) -> None:  # type: ignore[no-untyped-def]
    alice, bob = browser(), browser()
    saved = alice.post("/api/sites", json=_site())
    assert saved.status_code == 200
    assert COOKIE_NAME in alice.cookies
    set_cookie = saved.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie
    assert "max-age" not in set_cookie  # a guest cookie ends with the browser session
    assert alice.get("/api/auth/me").json()["user"]["is_guest"] is True
    assert _own(alice) == ["user-my-crater"]
    assert _own(bob) == []  # sites are no longer shared between visitors
    assert bob.delete("/api/sites/user-my-crater").status_code == 404


def test_guest_site_can_be_evaluated_by_its_owner_only(browser) -> None:  # type: ignore[no-untyped-def]
    alice, bob = browser(), browser()
    alice.post("/api/sites", json=_site())
    body = {"site_id": "user-my-crater", "window": WINDOW}
    assert alice.post("/api/evaluate", json=body).status_code == 200
    assert bob.post("/api/evaluate", json=body).status_code == 404


def test_register_keeps_guest_sites_and_sets_a_lasting_cookie(browser) -> None:  # type: ignore[no-untyped-def]
    client = browser()
    client.post("/api/sites", json=_site())
    registered = client.post("/api/auth/register", json={"username": "gian", "password": PASSWORD})
    assert registered.status_code == 201
    assert "max-age" in registered.headers["set-cookie"].lower()
    assert registered.json()["user"] == {"username": "gian", "is_guest": False, "is_admin": False}
    assert _own(client) == ["user-my-crater"]


def test_login_from_another_browser_and_merge(browser) -> None:  # type: ignore[no-untyped-def]
    home = browser()
    home.post("/api/auth/register", json={"username": "gian", "password": PASSWORD})
    home.post("/api/sites", json=_site("from-home"))
    phone = browser()
    phone.post("/api/sites", json=_site("from-phone"))
    assert (
        phone.post("/api/auth/login", json={"username": "GIAN", "password": PASSWORD}).status_code
        == 200
    )
    assert sorted(_own(phone)) == ["user-from-home", "user-from-phone"]
    assert sorted(_own(home)) == ["user-from-home", "user-from-phone"]


def test_wrong_login_and_taken_username(browser) -> None:  # type: ignore[no-untyped-def]
    client = browser()
    client.post("/api/auth/register", json={"username": "gian", "password": PASSWORD})
    wrong = browser().post("/api/auth/login", json={"username": "gian", "password": "nope-nope"})
    assert wrong.status_code == 401
    taken = browser().post("/api/auth/register", json={"username": "Gian", "password": PASSWORD})
    assert taken.status_code == 409
    weak = browser().post("/api/auth/register", json={"username": "other", "password": "short"})
    assert weak.status_code == 422


def test_logout_and_delete_account(browser) -> None:  # type: ignore[no-untyped-def]
    client = browser()
    client.post("/api/auth/register", json={"username": "gian", "password": PASSWORD})
    client.post("/api/sites", json=_site())
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").json() == {"user": None}
    assert _own(client) == []
    client.post("/api/auth/login", json={"username": "gian", "password": PASSWORD})
    wrong = client.post("/api/auth/delete-account", json={"password": "not-my-password"})
    assert wrong.status_code == 401
    assert client.post("/api/auth/delete-account", json={"password": PASSWORD}).status_code == 204
    assert (
        client.post("/api/auth/login", json={"username": "gian", "password": PASSWORD}).status_code
        == 401
    )


def test_shared_sites_stay_read_only(browser) -> None:  # type: ignore[no-untyped-def]
    client = browser()
    curated = next(s["id"] for s in client.get("/api/sites").json() if s["origin"] != "user")
    assert client.delete(f"/api/sites/{curated}").status_code == 403
    taken = {**_site(), "id": curated}
    assert client.post("/api/sites", json=taken).status_code == 409


def test_proposal_review_flow(browser, store: AccountStore) -> None:  # type: ignore[no-untyped-def]
    friend = browser()
    friend.post("/api/auth/register", json={"username": "friend", "password": PASSWORD})
    friend.post("/api/sites", json=_site())
    guest = browser()
    assert guest.post("/api/proposals", json={"site_id": "user-my-crater"}).status_code == 401
    proposed = friend.post(
        "/api/proposals", json={"site_id": "user-my-crater", "note": "Lit most of the year."}
    )
    assert proposed.status_code == 201
    proposal_id = proposed.json()["id"]
    assert friend.get("/api/admin/proposals").status_code == 403

    admin = browser()
    admin.post("/api/auth/register", json={"username": "gian", "password": PASSWORD})
    store.set_admins(["gian"])
    pending = admin.get("/api/admin/proposals", params={"status": "pending"}).json()
    assert [p["id"] for p in pending] == [proposal_id]
    approved = admin.post(
        f"/api/admin/proposals/{proposal_id}/approve",
        json={"name": "Quiet Rim", "sources": ["https://example.org/rim"], "admin_note": "Added"},
    )
    assert approved.status_code == 200
    site_id = approved.json()["community_site_id"]

    # Everyone now sees the site in the shared catalog, read-only.
    visitor = browser()
    shared = {s["id"]: s for s in visitor.get("/api/sites").json()}
    assert shared[site_id]["name"] == "Quiet Rim"
    assert shared[site_id]["sources"] == ["https://example.org/rim"]
    assert visitor.delete(f"/api/sites/{site_id}").status_code == 403
    assert friend.get("/api/proposals").json()[0]["status"] == "approved"
    assert admin.post(f"/api/admin/proposals/{proposal_id}/reject", json={}).status_code == 409

    assert admin.delete(f"/api/admin/community-sites/{site_id}").status_code == 204
    assert site_id not in {s["id"] for s in visitor.get("/api/sites").json()}


def test_own_sites_join_the_ranking(browser) -> None:  # type: ignore[no-untyped-def]
    client = browser()
    client.post("/api/sites", json=_site())
    ranking = client.post("/api/rank", json={"window": WINDOW, "min_illumination_fraction": 0.1})
    assert ranking.status_code == 200
