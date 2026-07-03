"""Optional API key authentication middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings, get_settings

_API_PREFIX = "/api/v1"
_EXEMPT_API_ROUTES = {
    ("GET", f"{_API_PREFIX}/health"),
    ("GET", f"{_API_PREFIX}/metrics"),
    ("GET", f"{_API_PREFIX}/metrics/prometheus"),
}
_DOCS_PATHS = {"/docs", "/openapi.json", "/redoc"}


def _extract_api_key(request: Request) -> str | None:
    header_key = request.headers.get("X-API-Key")
    if header_key:
        return header_key.strip()

    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _resolve_settings(request: Request) -> Settings:
    state_settings = getattr(request.app.state, "settings", None)
    if state_settings is not None:
        return state_settings
    return get_settings()


def _is_exempt(path: str, method: str) -> bool:
    if method == "GET" and path in _DOCS_PATHS:
        return True
    return (method.upper(), path) in _EXEMPT_API_ROUTES


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key or Authorization: Bearer on /api/v1/* when enabled."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = _resolve_settings(request)

        if not settings.api_key_enabled or not settings.api_key:
            return await call_next(request)

        path = request.url.path
        method = request.method.upper()

        if _is_exempt(path, method):
            return await call_next(request)

        if not path.startswith(_API_PREFIX):
            return await call_next(request)

        provided = _extract_api_key(request)
        if provided != settings.api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)