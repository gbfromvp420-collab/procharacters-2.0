"""Live and static provider contract verification (Real Provider Forge)."""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

from app.models.llm import ChatMessage
from app.models.providers import ProviderForgeEntry, ProviderForgeResponse, ProviderContractSpec
from app.services.llm.client import create_llm_client
from app.services.providers.contracts import PROVIDER_CONTRACTS, is_placeholder_endpoint
from app.services.tts.client import create_tts_client
from app.services.video.client import create_musetalk_client
from app.services.video.sync import SyncTimeline

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.services.providers.probe import ProviderProbeService

logger = logging.getLogger(__name__)

_SMOKE_LLM_PROMPT = "Say hi."
_SMOKE_TTS_TEXT = "Ok."
_SMOKE_VIDEO_MS = 200


class ProviderContractForge:
    """Combines reachability probes with contract metadata and optional live smoke."""

    def __init__(
        self,
        settings: Settings,
        *,
        probe: ProviderProbeService,
    ) -> None:
        self._settings = settings
        self._probe = probe

    def contract_spec(self, provider: str) -> ProviderContractSpec:
        spec = PROVIDER_CONTRACTS[provider]
        return ProviderContractSpec(
            provider=provider,  # type: ignore[arg-type]
            endpoint_path=spec["endpoint_path"],
            method=spec["method"],
            request_fields=list(spec["request_fields"]),
            response_fields=list(spec["response_fields"]),
        )

    def _mode_for(self, provider: str) -> str:
        return getattr(self._settings, f"{provider}_provider")

    def _endpoint_for(self, provider: str) -> str:
        if provider == "llm":
            return self._settings.llm_base_url
        if provider == "tts":
            return self._settings.tts_base_url
        return self._settings.video_base_url

    def _is_remote_mode(self, provider: str) -> bool:
        mode = self._mode_for(provider)
        return mode in PROVIDER_CONTRACTS[provider]["remote_modes"]

    async def _live_smoke(self, provider: str) -> tuple[bool, str]:
        if not self._is_remote_mode(provider):
            return True, "mock contract satisfied"

        try:
            if provider == "llm":
                return await self._smoke_llm()
            if provider == "tts":
                return await self._smoke_tts()
            return await self._smoke_video()
        except Exception as exc:
            logger.warning("Live contract smoke failed for %s: %s", provider, exc)
            return False, str(exc)

    async def _smoke_llm(self) -> tuple[bool, str]:
        client = create_llm_client(self._settings)
        tokens: list[str] = []
        try:
            async for token in client.stream_tokens(
                [ChatMessage(role="user", content=_SMOKE_LLM_PROMPT)],
                max_tokens=8,
                temperature=0.0,
            ):
                tokens.append(token)
                if len(tokens) >= 4:
                    break
        finally:
            await client.aclose()

        if not tokens:
            return False, "LLM smoke returned zero tokens"
        preview = "".join(tokens)[:40]
        return True, f"stream ok ({len(tokens)} tokens): {preview!r}"

    async def _smoke_tts(self) -> tuple[bool, str]:
        client = create_tts_client(self._settings)
        try:
            audio = await client.synthesize(_SMOKE_TTS_TEXT)
        finally:
            await client.aclose()

        if not audio.pcm_bytes:
            return False, "TTS smoke returned empty PCM"
        return True, f"{len(audio.pcm_bytes)} bytes, {audio.duration_ms}ms"

    async def _smoke_video(self) -> tuple[bool, str]:
        client = create_musetalk_client(self._settings)
        fake_pcm = b"\x00\x00" * (self._settings.tts_sample_rate // 4)
        audio_b64 = base64.b64encode(fake_pcm).decode("ascii")
        timeline = SyncTimeline(fps=self._settings.video_fps)
        try:
            result = await client.generate_frames(
                audio_b64=audio_b64,
                sample_rate=self._settings.tts_sample_rate,
                channels=self._settings.tts_channels,
                duration_ms=_SMOKE_VIDEO_MS,
                timeline=timeline,
                avatar_id=self._settings.video_avatar_id,
            )
        finally:
            await client.aclose()

        if not result.frames:
            return False, "Video smoke returned zero frames"
        return True, f"{len(result.frames)} frames @ {result.width}x{result.height}"

    async def evaluate_provider(
        self,
        provider: str,
        *,
        live_smoke: bool = False,
    ) -> ProviderForgeEntry:
        probe_fn = getattr(self._probe, f"probe_{provider}")
        probe_result = await probe_fn()
        mode = self._mode_for(provider)
        endpoint = self._endpoint_for(provider)
        spec = self.contract_spec(provider)
        message = probe_result.message

        if not self._is_remote_mode(provider):
            smoke_ok = True if live_smoke else None
            smoke_message = "mock contract satisfied" if live_smoke else ""
            return ProviderForgeEntry(
                provider=provider,  # type: ignore[arg-type]
                mode=mode,
                endpoint=endpoint,
                probe_status=probe_result.status,
                contract_ok=True,
                smoke_ok=smoke_ok,
                message=smoke_message or message,
                spec=spec,
            )

        config_ok = not is_placeholder_endpoint(endpoint)
        reachability_ok = probe_result.status in ("ok", "degraded")
        contract_ok = config_ok and reachability_ok

        if not config_ok:
            message = "endpoint looks like a placeholder — set real RunPod URL in .env"
        elif not reachability_ok:
            message = probe_result.message

        smoke_ok: bool | None = None
        if live_smoke:
            smoke_ok, smoke_message = await self._live_smoke(provider)
            contract_ok = contract_ok and smoke_ok
            if smoke_message:
                message = smoke_message

        return ProviderForgeEntry(
            provider=provider,  # type: ignore[arg-type]
            mode=mode,
            endpoint=endpoint,
            probe_status=probe_result.status,
            contract_ok=contract_ok,
            smoke_ok=smoke_ok,
            message=message,
            spec=spec,
        )

    async def evaluate_all(self, *, live_smoke: bool = False) -> ProviderForgeResponse:
        llm = await self.evaluate_provider("llm", live_smoke=live_smoke)
        tts = await self.evaluate_provider("tts", live_smoke=live_smoke)
        video = await self.evaluate_provider("video", live_smoke=live_smoke)
        forge_ok = llm.contract_ok and tts.contract_ok and video.contract_ok
        return ProviderForgeResponse(
            forge_ok=forge_ok,
            live_smoke=live_smoke,
            llm=llm,
            tts=tts,
            video=video,
        )