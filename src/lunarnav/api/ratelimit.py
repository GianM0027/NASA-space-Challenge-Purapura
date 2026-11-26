# ABOUTME: Per-client rate limiting of the REST API (decision D44): sliding window per IP and group
# ABOUTME: Owner: Gian. In memory, one process; LUNARNAV_RATE_LIMITS sets the limits or "off"

"""Per-client rate limiting for the public deployment.

Each request under ``/api/`` counts against the ``default`` group and, when its route is
expensive, against one more group (``heavy``: evaluations and analyses, ``ai``: LLM calls,
``write``: changes to saved sites, ``auth``: log in, register and delete account). A client
over any limit gets HTTP 429 with ``Retry-After``.

The client is ``request.client.host``: behind the proxies (Tailscale Funnel, then Caddy, then
uvicorn with ``--proxy-headers``) it is the visitor's address. State lives in this process only,
so limits reset on restart; that is enough for a small site.
"""

from __future__ import annotations

import math
import os
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send

WINDOW_S = 60.0
# Requests per client per minute, by group. Generous for a person clicking around the GUI
# (one evaluation per click, a few AI calls per question), tight for a script.
# "auth" (log in, register, delete account) slows down password guessing (decision D45).
DEFAULT_LIMITS: dict[str, int] = {"default": 300, "heavy": 40, "ai": 20, "write": 30, "auth": 10}
# Distinct clients remembered at once; the least recently seen is forgotten first.
MAX_CLIENTS = 10_000

_HEAVY_PREFIXES = ("/api/evaluate", "/api/compare", "/api/rank", "/api/mission-analysis")
_AI_PREFIXES = ("/api/ai/", "/api/tradeoff")


def route_group(method: str, path: str) -> str | None:
    """Return the extra limit group of a request, or None when only ``default`` applies.

    Args:
        method: HTTP method.
        path: URL path.
    """
    if path.startswith("/api/auth/") and method == "POST" and path != "/api/auth/logout":
        return "auth"
    if path.startswith(_AI_PREFIXES) and method == "POST":
        return "ai"
    if path.startswith(_HEAVY_PREFIXES) and method == "POST":
        return "heavy"
    if path.startswith("/api/sites") and method in {"POST", "PATCH", "DELETE"}:
        return "write"
    return None


def parse_limits(text: str | None) -> dict[str, int] | None:
    """Parse ``LUNARNAV_RATE_LIMITS``: "off", or "group=n,..." overriding the defaults.

    Returns:
        The limits per group, or None when limiting is off.

    Raises:
        ValueError: On an unknown group or a limit that is not a positive integer.
    """
    if text is None or not text.strip():
        return dict(DEFAULT_LIMITS)
    if text.strip().lower() == "off":
        return None
    limits = dict(DEFAULT_LIMITS)
    for item in text.split(","):
        group, _, value = item.partition("=")
        group = group.strip()
        if group not in DEFAULT_LIMITS:
            raise ValueError(f"unknown rate limit group {group!r} in LUNARNAV_RATE_LIMITS")
        if not value.strip().isdigit() or int(value) < 1:
            raise ValueError(f"rate limit for {group!r} must be a positive integer")
        limits[group] = int(value)
    return limits


@dataclass
class RateLimiter:
    """Sliding-window counters per (client, group).

    Attributes:
        limits: Requests allowed per ``window_s`` for each group.
        window_s: Window length, seconds.
        clock: Monotonic time source, seconds (replaceable in tests).
        max_clients: Clients remembered at once.
    """

    limits: dict[str, int]
    window_s: float = WINDOW_S
    clock: Callable[[], float] = time.monotonic
    max_clients: int = MAX_CLIENTS

    def __post_init__(self) -> None:
        """Create the empty counters."""
        self._hits: OrderedDict[str, dict[str, deque[float]]] = OrderedDict()

    def check(self, client: str, groups: list[str]) -> float:
        """Record one request of ``client`` in ``groups`` if every group has room.

        Returns:
            0 when the request is allowed (and recorded); otherwise the seconds until the
            fullest group has room again (nothing is recorded).
        """
        now = self.clock()
        per_group = self._hits.get(client)
        if per_group is None:
            per_group = {}
            self._hits[client] = per_group
            if len(self._hits) > self.max_clients:
                self._hits.popitem(last=False)
        else:
            self._hits.move_to_end(client)
        wait = 0.0
        for group in groups:
            hits = per_group.setdefault(group, deque())
            while hits and hits[0] <= now - self.window_s:
                hits.popleft()
            if len(hits) >= self.limits[group]:
                wait = max(wait, hits[0] + self.window_s - now)
        if wait > 0:
            return wait
        for group in groups:
            per_group[group].append(now)
        return 0.0


class RateLimitMiddleware:
    """ASGI middleware answering 429 to clients over their limit on ``/api/`` routes."""

    def __init__(self, app: ASGIApp, limiter: RateLimiter) -> None:
        """Wrap ``app``.

        Args:
            app: The ASGI application.
            limiter: The shared counters.
        """
        self.app = app
        self.limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Count the request and pass it on, or answer 429."""
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith("/api/") or path == "/api/health":
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        host = client[0] if client else "unknown"
        groups = ["default"]
        extra = route_group(scope.get("method", "GET"), path)
        if extra is not None:
            groups.append(extra)
        wait = self.limiter.check(host, groups)
        if wait <= 0:
            await self.app(scope, receive, send)
            return
        body = b'{"detail":"Too many requests: wait a moment and try again."}'
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"retry-after", str(max(1, math.ceil(wait))).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def limiter_from_env() -> RateLimiter | None:
    """Build the limiter configured by ``LUNARNAV_RATE_LIMITS`` (None when "off")."""
    limits = parse_limits(os.environ.get("LUNARNAV_RATE_LIMITS"))
    return None if limits is None else RateLimiter(limits)
