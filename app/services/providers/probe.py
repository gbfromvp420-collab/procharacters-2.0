"""Lightweight health probes for configured LLM, TTS, and video providers."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.models.providers import ProviderHealthStatus, ProviderStatus

logger = logging.getLogger(__name__)

PROBE_TIMEOUT_SECONDS = 3.0
CACHE_TTL_SECONDS = 30.0


class ProviderProbeService:
    """Probe external provider endpoints with short timeouts and optional caching."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(PROBE_TIMEOUT_SECONDS),
            follow_redirects=True,
        )
        self._cache: dict[str, ProviderStatus] | None = None
        self._cache_at: float = 0.0
        self._probe_lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._client.aclose()

    def _mock_status(self, provider: str, mode: str, endpoint: str) -> ProviderStatus:
        return ProviderStatus(
            provider=provider,  # type: ignore[arg-type]
            mode=mode,
            status="ok",
            latency_ms=0,
            endpoint=endpoint,
            message="mock",
        )

    def _build_headers(self, api_key: str) -> dict[str, str]:
        if api_key:
            return {"Authorization": f"Bearer {api_key}"}
        return {}

    async def _request_probe(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> tuple[ProviderHealthStatus, str]:
        try:
            response = await self._client.request(method, url, headers=headers or {})
            if response.status_code < 400:
                return "ok", f"{method} {url} -> {response.status_code}"
            if response.status_code < 500:
                return "degraded", f"{method} {url} -> {response.status_code}"
            return "degraded", f"{method} {url} -> {response.status_code}"
        except httpx.TimeoutException:
            return "unreachable", "timeout"
        except httpx.ConnectError:
            return "unreachable", "connection refused"
        except httpx.HTTPError as exc:
            return "unreachable", str(exc)

    async def _probe_http_base(
        self,
        base_url: str,
        *,
        api_key: str = "",
        extra_get_paths: list[str] | None = None,
    ) -> tuple[ProviderHealthStatus, int, str]:
        base = base_url.rstrip("/")
        headers = self._build_headers(api_key)
        candidates: list[tuple[str, str]] = [("GET", f"{base}/health")]
        for path in extra_get_paths or []:
            candidates.append(("GET", f"{base}{path}"))
        candidates.append(("HEAD", base))

        start = time.perf_counter()
        last_message = "no response"
        best_status: ProviderHealthStatus = "unreachable"

        for method, url in candidates:
            status, message = await self._request_probe(method, url, headers=headers)
            last_message = message
            if status == "ok":
                latency_ms = int((time.perf_counter() - start) * 1000)
                return "ok", latency_ms, message
            if status == "degraded" and best_status == "unreachable":
                best_status = "degraded"

        latency_ms = int((time.perf_counter() - start) * 1000)
        return best_status, latency_ms, last_message

    async def probe_llm(self) -> ProviderStatus:
        settings = self._settings
        mode = settings.llm_provider
        endpoint = settings.llm_base_url

        if mode == "mock":
            return self._mock_status("llm", mode, endpoint)

        status, latency_ms, message = await self._probe_http_base(
            endpoint,
            api_key=settings.llm_api_key,
            extra_get_paths=["/models"],
        )
        return ProviderStatus(
            provider="llm",
            mode=mode,
            status=status,
            latency_ms=latency_ms,
            endpoint=endpoint,
            message=message,
        )

    async def probe_tts(self) -> ProviderStatus:
        settings = self._settings
        mode = settings.tts_provider
        endpoint = settings.tts_base_url

        if mode == "mock":
            return self._mock_status("tts", mode, endpoint)

        status, latency_ms, message = await self._probe_http_base(
            endpoint,
            api_key=settings.tts_api_key,
        )
        return ProviderStatus(
            provider="tts",
            mode=mode,
            status=status,
            latency_ms=latency_ms,
            endpoint=endpoint,
            message=message,
        )

    async def probe_video(self) -> ProviderStatus:
        settings = self._settings
        mode = settings.video_provider
        endpoint = settings.video_base_url

        if mode == "mock":
            return self._mock_status("video", mode, endpoint)

        status, latency_ms, message = await self._probe_http_base(
            endpoint,
            api_key=settings.video_api_key,
        )
        return ProviderStatus(
            provider="video",
            mode=mode,
            status=status,
            latency_ms=latency_ms,
            endpoint=endpoint,
            message=message,
        )

    async def probe_all(self) -> dict[str, ProviderStatus]:
        llm, tts, video = await asyncio.gather(
            self.probe_llm(),
            self.probe_tts(),
            self.probe_video(),
        )
        result = {"llm": llm, "tts": tts, "video": video}
        self._cache = result
        self._cache_at = time.monotonic()
        return result

    def get_cached_all(self) -> dict[str, ProviderStatus] | None:
        if self._cache is None:
            return None
        if time.monotonic() - self._cache_at > CACHE_TTL_SECONDS:
            return None
        return self._cache

    async def probe_all_cached(self, *, max_age_seconds: float = CACHE_TTL_SECONDS) -> dict[str, ProviderStatus]:
        cached = self.get_cached_all()
        if cached is not None and time.monotonic() - self._cache_at <= max_age_seconds:
            return cached
        async with self._probe_lock:
            cached = self.get_cached_all()
            if cached is not None and time.monotonic() - self._cache_at <= max_age_seconds:
                return cached
            return await self.probe_all()

    def providers_summary_from(self, statuses: dict[str, ProviderStatus]) -> dict[str, Any]:
        return {
            provider: {
                "status": statuses[provider].status,
                "mode": statuses[provider].mode,
                "latency_ms": statuses[provider].latency_ms,
            }
            for provider in ("llm", "tts", "video")
        }

    async def get_providers_summary(self, *, timeout_seconds: float = 2.0) -> dict[str, Any]:
        cached = self.get_cached_all()
        if cached is not None:
            return self.providers_summary_from(cached)

        try:
            statuses = await asyncio.wait_for(self.probe_all_cached(), timeout=timeout_seconds)
            return self.providers_summary_from(statuses)
        except asyncio.TimeoutError:
            if cached is not None:
                summary = self.providers_summary_from(cached)
                summary["stale"] = True
                return summary
            return {
                "llm": {"status": "unknown", "mode": self._settings.llm_provider},
                "tts": {"status": "unknown", "mode": self._settings.tts_provider},
                "video": {"status": "unknown", "mode": self._settings.video_provider},
                "stale": True,
            }