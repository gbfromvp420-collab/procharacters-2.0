import logging
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings
from app.models.llm import StreamDoneEvent, StreamErrorEvent, StreamTokenEvent
from app.models.tts import AudioChunkEvent, TTSDoneEvent, TTSErrorEvent
from app.services.llm.pipeline import StreamEvent
from app.services.tts.audio import encode_pcm_b64
from app.services.tts.chunker import TextChunker
from app.services.tts.client import TTSClient, create_tts_client

logger = logging.getLogger(__name__)

TTSStreamEvent = AudioChunkEvent | TTSDoneEvent | TTSErrorEvent
SpeakStreamEvent = StreamEvent | TTSStreamEvent


class TTSStreamPipeline:
    """Converts streamed LLM tokens into chunked PCM audio for WebRTC playback."""

    def __init__(self, settings: Settings | None = None) -> None:
        from app.core.config import get_settings

        self._settings = settings or get_settings()
        self._client: TTSClient = create_tts_client(self._settings)

    @property
    def provider(self) -> str:
        return self._settings.tts_provider

    @property
    def voice(self) -> str:
        return self._settings.tts_voice

    async def stream_from_text(
        self,
        text: str,
        *,
        session_id: str | None = None,
        voice: str | None = None,
    ) -> AsyncIterator[TTSStreamEvent]:
        chunk_index = 0
        total_duration_ms = 0

        try:
            audio = await self._client.synthesize(text, voice=voice)
            yield AudioChunkEvent(
                chunk_index=chunk_index,
                text=text,
                audio_b64=encode_pcm_b64(audio.pcm_bytes),
                sample_rate=audio.sample_rate,
                channels=audio.channels,
                duration_ms=audio.duration_ms,
                session_id=session_id,
            )
            total_duration_ms += audio.duration_ms
            chunk_index += 1
        except httpx.HTTPStatusError as exc:
            logger.exception("TTS backend returned an error")
            yield TTSErrorEvent(
                message=f"TTS backend error: {exc.response.status_code}",
            )
            return
        except Exception as exc:
            logger.exception("TTS synthesis failed")
            yield TTSErrorEvent(message=str(exc))
            return

        yield TTSDoneEvent(
            session_id=session_id,
            chunk_count=chunk_index,
            total_duration_ms=total_duration_ms,
        )

    async def stream_from_llm_events(
        self,
        events: AsyncIterator[StreamEvent],
        *,
        session_id: str | None = None,
        voice: str | None = None,
    ) -> AsyncIterator[SpeakStreamEvent]:
        chunker = TextChunker(
            min_chars=self._settings.tts_chunk_min_chars,
            max_chars=self._settings.tts_chunk_max_chars,
        )
        chunk_index = 0
        total_duration_ms = 0

        async for event in events:
            if isinstance(event, StreamTokenEvent):
                yield event

                for text_chunk in chunker.push(event.content):
                    try:
                        audio_chunk = await self._emit_audio_chunk(
                            text_chunk,
                            chunk_index=chunk_index,
                            session_id=session_id,
                            voice=voice,
                        )
                    except httpx.HTTPStatusError as exc:
                        logger.exception("TTS backend returned an error")
                        yield TTSErrorEvent(
                            message=f"TTS backend error: {exc.response.status_code}",
                        )
                        return
                    except Exception as exc:
                        logger.exception("TTS chunk synthesis failed")
                        yield TTSErrorEvent(message=str(exc))
                        return

                    yield audio_chunk
                    total_duration_ms += audio_chunk.duration_ms
                    chunk_index += 1
                continue

            if isinstance(event, StreamErrorEvent):
                yield event
                return

            if isinstance(event, StreamDoneEvent):
                remaining = chunker.flush()
                if remaining:
                    try:
                        audio_chunk = await self._emit_audio_chunk(
                            remaining,
                            chunk_index=chunk_index,
                            session_id=session_id,
                            voice=voice,
                        )
                    except httpx.HTTPStatusError as exc:
                        logger.exception("TTS backend returned an error")
                        yield TTSErrorEvent(
                            message=f"TTS backend error: {exc.response.status_code}",
                        )
                        return
                    except Exception as exc:
                        logger.exception("TTS flush synthesis failed")
                        yield TTSErrorEvent(message=str(exc))
                        return

                    yield audio_chunk
                    total_duration_ms += audio_chunk.duration_ms
                    chunk_index += 1

                yield TTSDoneEvent(
                    session_id=session_id or event.session_id,
                    chunk_count=chunk_index,
                    total_duration_ms=total_duration_ms,
                )
                yield event
                return

        yield TTSErrorEvent(message="LLM stream ended without a completion event.")

    async def _emit_audio_chunk(
        self,
        text: str,
        *,
        chunk_index: int,
        session_id: str | None,
        voice: str | None,
    ) -> AudioChunkEvent:
        audio = await self._client.synthesize(text, voice=voice)
        return AudioChunkEvent(
            chunk_index=chunk_index,
            text=text,
            audio_b64=encode_pcm_b64(audio.pcm_bytes),
            sample_rate=audio.sample_rate,
            channels=audio.channels,
            duration_ms=audio.duration_ms,
            session_id=session_id,
        )

    async def aclose(self) -> None:
        await self._client.aclose()