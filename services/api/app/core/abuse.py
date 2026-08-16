"""Lightweight abuse protection for a single-instance deployment.

Two pieces, both dependency-free:

- `RateLimiter`: in-process sliding-window limiter keyed by (route, client IP).
  Right-sized for Render's single API instance; if the API ever scales to
  multiple replicas, swap this for a Redis-backed limiter (Redis is already
  in the stack) without changing call sites.
- `SecurityHeadersMiddleware`: sets the baseline OWASP-recommended response
  headers that uvicorn/FastAPI don't set by default.
"""

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class RateLimiter:
    """Sliding-window rate limit: `limit` requests per `window_seconds`.

    Raises RateLimitExceeded when the caller exceeds the budget. The window
    is a deque of arrival timestamps -- O(1) per request, no background
    cleanup needed (windows expire lazily as requests come in). In-memory
    only: fine for one instance, documented above for horizontal scaling.
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        window = self._hits[key]
        cutoff = now - self.window_seconds
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= self.limit:
            raise RateLimitExceeded()
        window.append(now)

    def _reset(self) -> None:
        self._hits.clear()


class RateLimitExceeded(Exception):
    pass


# Public (unauthenticated) endpoints get tight limits -- a scripted attacker
# costs real money on every render/ASR/LLM call, so the first line of defense
# is stopping brute-force signups and login spam at the door.
AUTH_LIMITER = RateLimiter(limit=10, window_seconds=60)
UPLOAD_START_LIMITER = RateLimiter(limit=20, window_seconds=60)
GENERAL_LIMITER = RateLimiter(limit=600, window_seconds=60)


def client_ip(request: Request) -> str:
    """Best-effort client IP. Render terminates TLS and sets X-Forwarded-For
    with the real client address first; behind any proxy, trust the first
    entry only (never the raw socket peer, which would be the proxy)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def raise_rate_limited() -> None:
    """Raise a standard 429. Kept as a function so the limit config + copy
    live in one place; endpoints just call `check()` and let this fire."""
    from fastapi import HTTPException

    raise HTTPException(
        status_code=429,
        detail="Too many requests. Please slow down and try again in a minute.",
        headers={"Retry-After": "60"},
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """OWASP-recommended baseline response headers. CSP is deliberately NOT
    set here: this app is a Next.js client-rendered app whose exact
    inline-script needs change with every build, so a hand-maintained CSP is
    worse than none. Revisit when adding a strict-CSP pipeline."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for name, value in self._headers.items():
            response.headers.setdefault(name, value)
        return response
