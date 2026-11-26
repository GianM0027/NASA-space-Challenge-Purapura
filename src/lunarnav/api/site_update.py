# ABOUTME: Admin "update the site" (D46): live version vs GitHub main, and an update request
# ABOUTME: Owner: Gian. The app only writes a request file; a server service runs the deploy

"""Site updates from the admin panel.

The app never runs the deploy itself (it has no rights to). It reads two things and writes one:

* ``status.json`` in ``LUNARNAV_CONTROL_DIR``, written by the deploy script: the live commit, when
  it was deployed, and whether a deploy is running or failed;
* the latest commit of ``main`` on GitHub (``LUNARNAV_GITHUB_REPO``, public API, cached);
* ``update-request``: created when an admin asks for an update. A service of the server's owner
  watches for it and runs the usual deploy script (tests, maintenance page, automatic rollback),
  which can only publish what is already on ``main``.

Without ``LUNARNAV_CONTROL_DIR`` the feature is off.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

STATUS_FILE = "status.json"
REQUEST_FILE = "update-request"
# Seconds a GitHub answer is reused: the admin panel may poll, the public API allows 60 calls/h.
GITHUB_CACHE_S = 60.0
MAX_CHANGES = 15


class UpdateError(RuntimeError):
    """An update cannot be requested now; the message is safe to show."""


class Commit(BaseModel):
    """A commit as the admin panel shows it."""

    sha: str
    date: str | None
    title: str


class SiteUpdateStatus(BaseModel):
    """``GET /api/admin/site-update``: live version, latest version, what changed, deploy state."""

    enabled: bool
    live: Commit | None
    deployed_at: str | None
    latest: Commit | None
    update_available: bool
    changes: list[str]
    state: Literal["idle", "requested", "running", "failed", "unknown"]
    message: str


def _title(message: str) -> str | None:
    """A readable one-line summary of a commit message, or None for a branch-sync merge."""
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    if not lines:
        return None
    first = lines[0]
    if first.startswith("Merge pull request"):
        number = first.split()[3] if len(first.split()) > 3 else ""
        title = lines[1] if len(lines) > 1 else first
        return f"{title} ({number})" if number.startswith("#") else title
    if first.startswith(("Merge origin/", "Merge remote-tracking", "Merge branch")):
        return None
    return first


Fetch = Callable[[str], Any]


def github_fetch(url: str) -> Any:
    """GET a GitHub API URL and return the decoded JSON (raises on any failure)."""
    import httpx

    answer = httpx.get(
        url,
        timeout=6.0,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "lunarnav-site-update"},
    )
    answer.raise_for_status()
    return answer.json()


@dataclass
class SiteUpdater:
    """Reads the deploy status and GitHub, and writes update requests.

    Attributes:
        control_dir: Folder shared with the deploy service.
        repo: GitHub repository, "owner/name".
        fetch: Function returning the JSON of a GitHub API URL (replaceable in tests).
        clock: Monotonic time, seconds (replaceable in tests).
    """

    control_dir: Path
    repo: str
    fetch: Fetch = github_fetch
    clock: Callable[[], float] = time.monotonic

    def __post_init__(self) -> None:
        """Start with an empty GitHub cache."""
        self._cache: dict[str, tuple[float, Any]] = {}

    def _github(self, path: str) -> Any:
        url = f"https://api.github.com/repos/{self.repo}/{path}"
        hit = self._cache.get(url)
        if hit is not None and self.clock() - hit[0] < GITHUB_CACHE_S:
            return hit[1]
        value = self.fetch(url)
        self._cache[url] = (self.clock(), value)
        return value

    def _read_status(self) -> dict[str, Any]:
        try:
            data = json.loads((self.control_dir / STATUS_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def status(self) -> SiteUpdateStatus:
        """Everything the admin panel shows."""
        recorded = self._read_status()
        live_sha = str(recorded.get("version") or "") or None
        state = str(recorded.get("state") or "unknown")
        message = str(recorded.get("message") or "")
        if state not in {"idle", "running", "failed"}:
            state = "unknown"
        if state != "running" and (self.control_dir / REQUEST_FILE).exists():
            state = "requested"
        latest: Commit | None = None
        changes: list[str] = []
        live: Commit | None = Commit(sha=live_sha, date=None, title="") if live_sha else None
        try:
            head = self._github("commits/main")
            latest = Commit(
                sha=head["sha"],
                date=head["commit"]["committer"]["date"],
                title=_title(head["commit"]["message"]) or "",
            )
            if live_sha and live_sha != latest.sha:
                compare = self._github(f"compare/{live_sha}...{latest.sha}")
                titles = [_title(c["commit"]["message"]) for c in compare.get("commits", [])]
                changes = [t for t in reversed(titles) if t][:MAX_CHANGES]
        except Exception:  # GitHub unreachable or rate-limited: show what is known locally
            if not message:
                message = "GitHub could not be reached: the latest version is unknown."
        return SiteUpdateStatus(
            enabled=True,
            live=live,
            deployed_at=recorded.get("deployed_at"),
            latest=latest,
            update_available=latest is not None and live_sha != latest.sha,
            changes=changes,
            state=state,  # type: ignore[arg-type]
            message=message,
        )

    def request(self, username: str) -> SiteUpdateStatus:
        """Ask the deploy service to publish the latest ``main``.

        Raises:
            UpdateError: No update available, one already requested or running, or GitHub unknown.
        """
        current = self.status()
        if current.state in {"requested", "running"}:
            raise UpdateError("An update is already in progress.")
        if current.latest is None:
            raise UpdateError("The latest version on GitHub is unknown right now: try again later.")
        if not current.update_available:
            raise UpdateError("The site already runs the latest version.")
        payload = {
            "requested_at": datetime.now(UTC).isoformat(),
            "requested_by": username,
            "target": current.latest.sha,
        }
        target = self.control_dir / REQUEST_FILE
        temporary = self.control_dir / f".{REQUEST_FILE}.tmp"
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        temporary.replace(target)  # atomic: the watcher never sees half a file
        return self.status()


def updater_from_env() -> SiteUpdater | None:
    """The updater configured by ``LUNARNAV_CONTROL_DIR`` and ``LUNARNAV_GITHUB_REPO``, or None."""
    folder = os.environ.get("LUNARNAV_CONTROL_DIR")
    repo = os.environ.get("LUNARNAV_GITHUB_REPO", "GianM0027/NASA-space-Challenge-Purapura")
    # github_fetch is looked up here, at call time, so tests can replace it.
    return SiteUpdater(Path(folder), repo, fetch=github_fetch) if folder else None


DISABLED = SiteUpdateStatus(
    enabled=False,
    live=None,
    deployed_at=None,
    latest=None,
    update_available=False,
    changes=[],
    state="unknown",
    message="Updating from the app is not configured on this server.",
)
