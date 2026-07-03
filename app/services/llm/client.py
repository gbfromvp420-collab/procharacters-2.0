import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings
from app.models.llm import ChatMessage

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    @abstractmethod
    async def stream_tokens(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


class OpenAICompatibleLLMClient(LLMClient):
    """Streams tokens from a vLLM / RunPod OpenAI-compatible endpoint."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.llm_base_url.rstrip("/"),
            headers=self._build_headers(),
            timeout=httpx.Timeout(settings.llm_timeout_seconds),
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self._settings.llm_api_key}"
        return headers

    async def stream_tokens(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self._settings.llm_model,
            "messages": [message.model_dump() for message in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        async with self._client.stream(
            "POST",
            "/chat/completions",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue

                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break

                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed LLM stream chunk")
                    continue

                choices = chunk.get("choices") or []
                if not choices:
                    continue

                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content

    async def aclose(self) -> None:
        await self._client.aclose()


class MockLLMClient(LLMClient):
    """Deterministic local stream for development without a GPU backend."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def stream_tokens(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        del max_tokens, temperature

        latest_user = next(
            (message.content for message in reversed(messages) if message.role == "user"),
            "",
        )
        response = (
            f"Hi — I'm {self._settings.llm_model} running in mock mode. "
            f"You said: {latest_user}"
        )

        for index, token in enumerate(response.split()):
            if index:
                yield " "
            yield token
            await asyncio.sleep(self._settings.llm_mock_token_delay_ms / 1000)


def create_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleLLMClient(settings)
    return MockLLMClient(settings)