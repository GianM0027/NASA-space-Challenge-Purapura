# ABOUTME: Tests of the admin site update (D46): status from the deploy file and GitHub, requests
# ABOUTME: Owner: Gian. GitHub is faked; the control folder is pytest's tmp_path

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from lunarnav.accounts import AccountStore
from lunarnav.api import site_update
from lunarnav.api.main import build_app
from lunarnav.api.site_update import REQUEST_FILE, STATUS_FILE, SiteUpdater, UpdateError, _title
from lunarnav.api.wiring import build_services

LIVE = "a" * 40
NEW = "b" * 40
PASSWORD = "correct horse battery"


def _commit(sha: str, message: str) -> dict[str, Any]:
    return {
        "sha": sha,
        "commit": {"message": message, "committer": {"date": "2026-11-26T21:00:00Z"}},
    }


class _GitHub:
    def __init__(self, head: str = NEW) -> None:
        self.head = head
        self.calls: list[str] = []
        self.down = False

    def __call__(self, url: str) -> Any:
        self.calls.append(url)
        if self.down:
            raise OSError("no network")
        if url.endswith("/commits/main"):
            return _commit(
                self.head, "Merge pull request #50 from x/y\n\nfix(frontend): usable PDF report"
            )
        if "/compare/" in url:
            return {
                "commits": [
                    _commit("c1", "fix(frontend): usable PDF report on phones\n\nbody"),
                    _commit("c2", "Merge origin/main into gian-report-mobile"),
                    _commit(
                        "c3", "Merge pull request #50 from x/y\n\nfix(frontend): usable PDF report"
                    ),
                ]
            }
        raise AssertionError(url)


def _write_status(folder: Path, **fields: Any) -> None:
    data = {"version": LIVE, "deployed_at": "2026-11-26T20:00:00Z", "state": "idle", "message": ""}
    (folder / STATUS_FILE).write_text(json.dumps({**data, **fields}))


@pytest.fixture
def github() -> _GitHub:
    return _GitHub()


@pytest.fixture
def updater(tmp_path: Path, github: _GitHub) -> SiteUpdater:
    _write_status(tmp_path)
    return SiteUpdater(tmp_path, "owner/repo", fetch=github, clock=lambda: 0.0)


def test_titles_skip_branch_merges_and_name_pull_requests() -> None:
    assert _title("Merge pull request #48 from a/b\n\nfeat: tabs") == "feat: tabs (#48)"
    assert _title("Merge origin/main into gian-x") is None
    assert _title("fix: one thing\n\ndetails") == "fix: one thing"


def test_status_shows_live_latest_and_changes(updater: SiteUpdater) -> None:
    status = updater.status()
    assert status.enabled and status.update_available
    assert status.live is not None and status.live.sha == LIVE
    assert status.latest is not None and status.latest.sha == NEW
    assert status.changes == [
        "fix(frontend): usable PDF report (#50)",
        "fix(frontend): usable PDF report on phones",
    ]
    assert status.state == "idle"


def test_no_update_when_live_is_latest(tmp_path: Path) -> None:
    _write_status(tmp_path)
    updater = SiteUpdater(tmp_path, "owner/repo", fetch=_GitHub(head=LIVE), clock=lambda: 0.0)
    status = updater.status()
    assert not status.update_available and status.changes == []
    with pytest.raises(UpdateError, match="already runs the latest"):
        updater.request("gian")


def test_request_writes_the_file_once(updater: SiteUpdater, tmp_path: Path) -> None:
    status = updater.request("GianM0027")
    assert status.state == "requested"
    request = json.loads((tmp_path / REQUEST_FILE).read_text())
    assert request["target"] == NEW and request["requested_by"] == "GianM0027"
    with pytest.raises(UpdateError, match="already in progress"):
        updater.request("GianM0027")


def test_running_and_failed_states(updater: SiteUpdater, tmp_path: Path) -> None:
    _write_status(tmp_path, state="running")
    assert updater.status().state == "running"
    with pytest.raises(UpdateError, match="in progress"):
        updater.request("gian")
    _write_status(tmp_path, state="failed", message="Tests failed: back to the previous version.")
    status = updater.status()
    assert status.state == "failed" and "Tests failed" in status.message


def test_github_down_is_reported_not_raised(updater: SiteUpdater, github: _GitHub) -> None:
    github.down = True
    status = updater.status()
    assert status.latest is None and not status.update_available
    assert "GitHub" in status.message
    with pytest.raises(UpdateError, match="unknown"):
        updater.request("gian")


def test_github_answers_are_cached(tmp_path: Path, github: _GitHub) -> None:
    _write_status(tmp_path)
    now = [0.0]
    updater = SiteUpdater(tmp_path, "owner/repo", fetch=github, clock=lambda: now[0])
    updater.status()
    updater.status()
    assert len(github.calls) == 2  # head + compare, once
    now[0] = site_update.GITHUB_CACHE_S + 1
    updater.status()
    assert len(github.calls) == 4


def test_routes_are_admin_only_and_off_without_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _GitHub
) -> None:
    store = AccountStore(tmp_path / "accounts.sqlite3")
    store.set_admins(["gian"])
    monkeypatch.delenv("LUNARNAV_CONTROL_DIR", raising=False)
    off = TestClient(build_app(*build_services(use_real=False), accounts=store))
    off.post("/api/auth/register", json={"username": "gian", "password": PASSWORD})
    assert off.get("/api/admin/site-update").json()["enabled"] is False
    assert off.post("/api/admin/site-update").status_code == 503

    control = tmp_path / "control"
    control.mkdir()
    _write_status(control)
    monkeypatch.setenv("LUNARNAV_CONTROL_DIR", str(control))
    monkeypatch.setattr(site_update, "github_fetch", github)
    app = build_app(*build_services(use_real=False), accounts=store)
    admin, friend = TestClient(app), TestClient(app)
    admin.post("/api/auth/login", json={"username": "gian", "password": PASSWORD})
    friend.post("/api/auth/register", json={"username": "friend", "password": PASSWORD})
    assert friend.get("/api/admin/site-update").status_code == 403
    assert TestClient(app).post("/api/admin/site-update").status_code == 401
    assert admin.get("/api/admin/site-update").json()["update_available"] is True
    assert admin.post("/api/admin/site-update").status_code == 202
    assert (control / REQUEST_FILE).exists()
    assert admin.post("/api/admin/site-update").status_code == 409
    assert github.calls and all("owner" not in c for c in github.calls)  # the fake, no network
