"""Simple in-memory per-IP sliding-window rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings, get_settings

_RATE_LIMITED_ROUTES = {
    ("POST", "/api/v1/chat/perform"),
    ("POST", "/api/v1/webrtc/session"),
}
_WINDOW_SECONDS = 60.0


class SlidingWindowRateLimiter:
    """Tracks request timestamps per bucket key within a sliding time window."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, bucket_key: str, limit: int, *, window_seconds: float = _WINDOW_SECONDS) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        recent = [ts for ts in self._hits[bucket_key] if ts > cutoff]
        if len(recent) >= limit:
            self._hits[bucket_key] = recent
            return False
        recent.append(now)
        self._hits[bucket_key] = recent
        return True

    def reset(self) -> None:
        self._hits.clear()


_rate_limiter = SlidingWindowRateLimiter()


def get_rate_limiter() -> SlidingWindowRateLimiter:
    return _rate_limiter


def reset_rate_limiter() -> None:
    _rate_limiter.reset()


def _resolve_settings(request: Request) -> Settings:
    state_settings = getattr(request.app.state, "settings", None)
    if state_settings is not None:
        return state_settings
    return get_settings()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limit POST /chat/perform and POST /webrtc/session per client IP."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = _resolve_settings(request)

        if not settings.rate_limit_enabled:
            return await call_next(request)

        route = (request.method.upper(), request.url.path)
        if route not in _RATE_LIMITED_ROUTES:
            return await call_next(request)

        bucket_key = f"{_client_ip(request)}:{route[1]}"
        limit = settings.rate_limit_perform_per_minute
        if not _rate_limiter.allow(bucket_key, limit):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": "60"},
            )

        return await call_next(request)