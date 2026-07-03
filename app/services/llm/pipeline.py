import logging
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings
from app.models.llm import (
    ChatMessage,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamTokenEvent,
)
from app.services.llm.client import LLMClient, create_llm_client

logger = logging.getLogger(__name__)

StreamEvent = StreamTokenEvent | StreamDoneEvent | StreamErrorEvent


class LLMStreamPipeline:
    """Token-by-token LLM pipeline for downstream TTS and video sync."""

    def __init__(self, settings: Settings | None = None) -> None:
        from app.core.config import get_settings

        self._settings = settings or get_settings()
        self._client: LLMClient = create_llm_client(self._settings)

    @property
    def provider(self) -> str:
        return self._settings.llm_provider

    @property
    def model(self) -> str:
        return self._settings.llm_model

    async def stream_completion(
        self,
        messages: list[ChatMessage],
        *,
        session_id: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[StreamEvent]:
        resolved_max_tokens = max_tokens or self._settings.llm_max_tokens
        resolved_temperature = (
            temperature if temperature is not None else self._settings.llm_temperature
        )

        token_index = 0
        finish_reason = "stop"

        try:
            async for token in self._client.stream_tokens(
                messages,
                max_tokens=resolved_max_tokens,
                temperature=resolved_temperature,
            ):
                yield StreamTokenEvent(content=token, index=token_index)
                token_index += 1
        except httpx.HTTPStatusError as exc:
            logger.exception("LLM backend returned an error")
            yield StreamErrorEvent(
                message=f"LLM backend error: {exc.response.status_code}",
            )
            return
        except Exception as exc:
            logger.exception("LLM stream failed")
            yield StreamErrorEvent(message=str(exc))
            return

        yield StreamDoneEvent(
            session_id=session_id,
            finish_reason=finish_reason,
            token_count=token_index,
        )

    async def aclose(self) -> None:
        await self._client.aclose()