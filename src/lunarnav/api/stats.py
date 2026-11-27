# ABOUTME: Internal usage statistics (D47): daily aggregate counters, no cookies, no stored IDs
# ABOUTME: Owner: Gian. Counted from API requests; shown to admins only at GET /api/admin/stats

"""Privacy-friendly usage statistics for the admin dashboard.

What is stored: per UTC day, counters such as "visits", "visitors", one per feature used, per
catalog site evaluated, per error kind and per device class (phone or desktop). Nothing else.

What is never stored: IP addresses, user agents, cookies or any per-visitor identifier. A visitor
is counted once a day through a hash of (address, user agent, a random salt). The salt and the
hashes live in memory for the current day only and are thrown away at midnight UTC (and on a
restart), so nobody can be followed across days, and the database holds counts only. Without
cookies or anything stored on the visitor's device, no consent banner is needed.

A visit is the frontend's first call, ``GET /api/modules``, which it makes once per page load.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
import time
from collections import Counter
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

FLUSH_EVERY_S = 30.0
KEEP_DAYS = 400
MAX_DAYS = 365

# Feature name for each counted route (method, path).
FEATURES: dict[tuple[str, str], str] = {
    ("POST", "/api/evaluate"): "site evaluation",
    ("POST", "/api/mission-analysis"): "mission analysis",
    ("POST", "/api/tradeoff"): "trade-off",
    ("POST", "/api/tradeoff/export"): "Excel export",
    ("POST", "/api/ai/ask"): "AI question",
    ("POST", "/api/rank"): "ranking edit",
    ("POST", "/api/sites"): "site saved",
    ("POST", "/api/proposals"): "site proposed",
    ("POST", "/api/auth/register"): "account created",
    ("POST", "/api/auth/login"): "log in",
}
# Events only the browser knows about (``POST /api/stats/event``).
CLIENT_EVENTS = {"pdf_report": "PDF report"}
PHONE_MARKERS = ("Mobi", "Android", "iPhone", "iPad")


def _today(clock: Callable[[], float]) -> str:
    return datetime.fromtimestamp(clock(), UTC).date().isoformat()


class Stats:
    """Counters buffered in memory and flushed to one SQLite file.

    Attributes:
        path: Database file.
        clock: Time source, seconds since the epoch (replaceable in tests).
    """

    def __init__(self, path: Path, clock: Callable[[], float] = time.time) -> None:
        """Open (and create) the database at ``path``."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self._lock = threading.Lock()
        self._buffer: Counter[tuple[str, str, str]] = Counter()
        self._last_flush = clock()
        self._salt_day = ""
        self._salt = b""
        self._seen: set[bytes] = set()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS daily (day TEXT NOT NULL, metric TEXT NOT NULL, "
                "key TEXT NOT NULL, count INTEGER NOT NULL, PRIMARY KEY (day, metric, key))"
            )

    def record(self, metric: str, key: str = "", n: int = 1) -> None:
        """Add ``n`` to today's counter ``metric``/``key``."""
        with self._lock:
            self._buffer[(_today(self.clock), metric, key[:120])] += n
        if self.clock() - self._last_flush >= FLUSH_EVERY_S:
            self.flush()

    def _new_visitor(self, client: str, user_agent: str) -> bool:
        """True the first time today this (address, user agent) pair is seen."""
        day = _today(self.clock)
        with self._lock:
            if day != self._salt_day:  # new day: forget yesterday's salt and hashes
                self._salt_day, self._salt, self._seen = day, secrets.token_bytes(16), set()
            digest = hashlib.sha256(self._salt + client.encode() + b"|" + user_agent.encode())
            key = digest.digest()[:16]
            if key in self._seen:
                return False
            self._seen.add(key)
            return True

    def record_request(
        self, method: str, path: str, status: int, client: str, user_agent: str
    ) -> None:
        """Count one finished API request."""
        if method == "GET" and path == "/api/modules" and status < 400:
            self.record("visits")
            phone = any(marker in user_agent for marker in PHONE_MARKERS)
            self.record("device", "phone" if phone else "desktop")
            if self._new_visitor(client, user_agent):
                self.record("visitors")
        feature = FEATURES.get((method, path))
        if feature is not None and status < 400:
            self.record("feature", feature)
        if status >= 500:
            self.record("error", "server error")
        elif status == 429:
            self.record("error", "rate limited")

    def flush(self) -> None:
        """Write the buffered counters and drop data older than ``KEEP_DAYS``."""
        with self._lock:
            pending, self._buffer = self._buffer, Counter()
            self._last_flush = self.clock()
        if not pending:
            return
        cutoff = (datetime.fromtimestamp(self.clock(), UTC) - timedelta(days=KEEP_DAYS)).date()
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.executemany(
                "INSERT INTO daily (day, metric, key, count) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (day, metric, key) DO UPDATE SET count = count + excluded.count",
                [(day, metric, key, n) for (day, metric, key), n in pending.items()],
            )
            db.execute("DELETE FROM daily WHERE day < ?", (cutoff.isoformat(),))

    def summary(self, days: int = 30) -> dict[str, Any]:
        """Everything the dashboard shows for the last ``days`` days (today included)."""
        days = max(1, min(days, MAX_DAYS))
        self.flush()
        end = datetime.fromtimestamp(self.clock(), UTC).date()
        dates = [(end - timedelta(days=offset)).isoformat() for offset in range(days - 1, -1, -1)]
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            rows = db.execute(
                "SELECT day, metric, key, count FROM daily WHERE day >= ?", (dates[0],)
            ).fetchall()
        per_day: dict[str, Counter[str]] = {d: Counter() for d in dates}
        totals: dict[str, Counter[str]] = {}
        for day, metric, key, count in rows:
            if day in per_day and metric in {"visits", "visitors"}:
                per_day[day][metric] += count
            totals.setdefault(metric, Counter())[key] += count
        top = lambda metric, n=None: [  # noqa: E731
            {"name": k, "count": c} for k, c in totals.get(metric, Counter()).most_common(n)
        ]
        return {
            "days": dates,
            "visits": [per_day[d]["visits"] for d in dates],
            "visitors": [per_day[d]["visitors"] for d in dates],
            "features": top("feature"),
            "sites": top("site", 10),
            "devices": top("device"),
            "errors": top("error"),
        }


class StatsMiddleware:
    """ASGI middleware counting finished ``/api/`` requests into ``Stats``."""

    def __init__(self, app: ASGIApp, stats: Stats) -> None:
        """Wrap ``app``."""
        self.app = app
        self.stats = stats

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the request on and count it once its status is known."""
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return
        status = 500

        async def capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            headers = dict(scope.get("headers") or [])
            agent = headers.get(b"user-agent", b"").decode("latin-1")
            client = scope.get("client")
            self.stats.record_request(
                scope.get("method", "GET"), path, status, client[0] if client else "", agent
            )
