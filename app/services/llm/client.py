import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings
from app.models.llm import ChatMessage

logger = logging.getLogger(__name__)

# =============================================================================
# LLM PROVIDER CONTRACT (openai_compatible)
# =============================================================================
# Endpoint: POST {llm_base_url}/chat/completions
#   (base_url typically ends with /v1 or includes it, e.g. "https://.../v1" or "http://host:port")
#
# Request:
#   Headers: Content-Type: application/json, (optional) Authorization: Bearer <llm_api_key>
#   JSON body:
#     {
#       "model": "<llm_model>",
#       "messages": [{"role": "user|system|assistant", "content": "..."}, ...],
#       "max_tokens": <int>,
#       "temperature": <float>,
#       "stream": true
#     }
#
# Response (SSE, text/event-stream):
#   data: {"id": "...", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": "token text"}, "finish_reason": null}], ...}
#   data: {"choices": [{"delta": {}, "finish_reason": "stop"}]}
#   data: [DONE]
#
# Client behavior: yields each non-empty delta.content as a separate token str.
# Errors: raise_for_status() on non-2xx; caller (pipeline) maps to StreamErrorEvent.
#
# RunPod / vLLM / OpenAI-compatible must support the above streaming chat format.
# =============================================================================


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
    """Streams tokens from a vLLM / RunPod OpenAI-compatible endpoint.

    Resilient features:
    - Granular timeouts (connect short, read long for streaming)
    - Per-chunk validation and skip of malformed data
    - Simple retry (up to 1 reconnect attempt) on transient connect/read timeouts
    - Explicit handling of httpx stream errors -> exceptions surfaced to pipeline
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.llm_base_url.rstrip("/"),
            headers=self._build_headers(),
            timeout=httpx.Timeout(
                connect=10.0,
                read=settings.llm_timeout_seconds,
                write=30.0,
                pool=5.0,
            ),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        self._max_retries = 1  # for transient stream start failures

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

        attempt = 0
        last_exc: Exception | None = None
        while attempt <= self._max_retries:
            try:
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
                            return  # end of stream

                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            logger.warning("Skipping malformed LLM stream chunk: %s", data[:120])
                            continue

                        # Validate shape more strictly
                        choices = chunk.get("choices") or []
                        if not isinstance(choices, list) or not choices:
                            # Some backends send usage-only or empty chunks; ignore
                            continue

                        choice = choices[0]
                        if not isinstance(choice, dict):
                            continue

                        delta = choice.get("delta") or {}
                        if not isinstance(delta, dict):
                            continue

                        content = delta.get("content")
                        if isinstance(content, str) and content:
                            yield content
                return  # successful completion
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError) as exc:
                last_exc = exc
                attempt += 1
                logger.warning("LLM stream transient error (attempt %s/%s): %s", attempt, self._max_retries + 1, exc)
                if attempt <= self._max_retries:
                    await asyncio.sleep(0.2 * attempt)
                    continue
                raise
            except httpx.HTTPStatusError:
                raise  # let caller/pipeline turn into error event
            except Exception:
                raise
        if last_exc:
            raise last_exc

    async def aclose(self) -> None:
        await self._client.aclose()


class MockLLMClient(LLMClient):
    """Deterministic local stream for development without a GPU backend.

    Improved realism:
    - Punctuation-aware tokenization (treats punctuation as separate "tokens" for chunker)
    - Variable per-token delay: base + length factor; longer pauses at sentence boundaries
    - Slightly longer, multi-sentence canned responses to exercise TTS chunking + video sync
    - Ignores max_tokens/temperature for determinism but truncates to reasonable size
    """

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
            "Hello",
        )
        # More realistic multi-sentence response to drive downstream chunking
        model_name = self._settings.llm_model.split("/")[-1][:24]
        if self._settings.mock_realistic:
            base = (
                f"Hi there. I'm {model_name} in local mock mode. "
                f"I heard you say: {latest_user}. "
                "This is a simulated response with multiple sentences. "
                "It helps test realistic TTS chunking, variable audio durations, and frame sync. "
                "Thanks for chatting!"
            )
        else:
            base = f"Hi — I'm {model_name} running in mock mode. You said: {latest_user}"
        # Simple deterministic "tokenization"
        tokens: list[str] = []
        if not self._settings.mock_realistic:
            tokens = base.split()
        else:
            for word in base.split():
                clean = word.strip()
                if not clean:
                    continue
                # Split trailing punctuation for better chunker boundary testing
                punct = ""
                while clean and clean[-1] in ".,!?;:\"'":
                    punct = clean[-1] + punct
                    clean = clean[:-1]
                if clean:
                    tokens.append(clean)
                if punct:
                    tokens.append(punct)

        base_delay = self._settings.llm_mock_token_delay_ms / 1000.0
        for idx, tok in enumerate(tokens):
            if idx > 0:
                # natural spacing (no extra space before punct)
                if not tok[0] in ".,!?;:":
                    yield " "
            yield tok

            # Variable delay: longer for longer tokens and sentence enders
            delay = base_delay
            delay += (len(tok) - 3) * 0.005  # slight length effect
            if tok in {".", "!", "?", ":"}:
                delay += 0.12  # pause at sentence end
            await asyncio.sleep(max(0.005, delay))


def create_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleLLMClient(settings)
    return MockLLMClient(settings)