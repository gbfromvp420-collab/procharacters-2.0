"""Local HTTP contract backend for LLM / TTS / MuseTalk shapes.

This is not a GPU provider. It implements the exact request/response contracts
the http clients send so mock → http can be proven without RunPod keys.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.services.tts.audio import encode_pcm_b64, generate_mock_pcm
from app.services.video.frames import mock_frame_b64

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8010


def create_contract_app() -> FastAPI:
    """FastAPI app exposing /v1/chat/completions, /synthesize, and /generate."""
    app = FastAPI(title="ProCharacters Contract Backend", version="1.0.0")

    @app.get("/health")
    @app.get("/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "role": "contract_backend"}

    @app.get("/models")
    @app.get("/v1/models")
    async def models() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [
                {
                    "id": "contract-mock",
                    "object": "model",
                    "owned_by": "procharacters-contract",
                }
            ],
        }

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "service": "procharacters-contract-backend",
            "llm": "POST /v1/chat/completions",
            "tts": "POST /synthesize",
            "video": "POST /generate",
        }

    @app.post("/chat/completions")
    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Response:
        payload = await request.json()
        stream = bool(payload.get("stream", False))
        force_json = (request.headers.get("x-contract-mode") or "").lower() == "json"
        text = _completion_text(payload)
        if stream and not force_json:
            return StreamingResponse(
                _sse_chat_chunks(text),
                media_type="text/event-stream",
            )
        return JSONResponse(_non_stream_completion(payload, text))

    @app.post("/synthesize")
    async def synthesize(request: Request) -> Response:
        payload = await request.json()
        text = str(payload.get("text") or "")
        sample_rate = int(payload.get("sample_rate") or 24000)
        channels = int(payload.get("channels") or 1)
        pcm = generate_mock_pcm(text or "ok", sample_rate=sample_rate)
        mode = (request.headers.get("x-contract-mode") or "").lower()
        if mode == "raw":
            return Response(content=pcm, media_type="application/octet-stream")
        body = {
            "audio_b64": encode_pcm_b64(pcm),
            "sample_rate": sample_rate,
            "channels": channels,
        }
        if mode == "json-no-ctype":
            return Response(content=json.dumps(body), media_type="")
        return JSONResponse(body)

    @app.post("/generate")
    async def generate(request: Request) -> JSONResponse:
        payload = await request.json()
        duration_ms = int(payload.get("duration_ms") or 200)
        fps = max(1, int(payload.get("fps") or 25))
        start_pts = int(payload.get("start_pts_ms") or 0)
        start_index = int(payload.get("start_frame_index") or 0)
        frame_b64 = mock_frame_b64()
        count = max(1, round((duration_ms / 1000.0) * fps))
        frames = []
        for offset in range(count):
            frames.append(
                {
                    "frame_index": start_index + offset,
                    "pts_ms": start_pts + int(round(offset * (1000.0 / fps))),
                    "frame_b64": frame_b64,
                }
            )
        return JSONResponse(
            {
                "frames": frames,
                "width": 512,
                "height": 512,
            }
        )

    return app


def _completion_text(payload: dict[str, Any]) -> str:
    messages = payload.get("messages") or []
    last_user = "hello"
    if isinstance(messages, list):
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "user":
                last_user = str(message.get("content") or last_user)
                break
    return f"Contract backend heard: {last_user}"


def _non_stream_completion(payload: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        "id": "contract-chat",
        "object": "chat.completion",
        "model": str(payload.get("model") or "contract-mock"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }


def _sse_chat_chunks(text: str):
    words = text.split()
    for index, word in enumerate(words):
        piece = word if index == 0 else f" {word}"
        chunk = {
            "id": "contract-chat",
            "object": "chat.completion.chunk",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": piece},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk)}\n\n"
    done = {
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(done)}\n\n"
    yield "data: [DONE]\n\n"


@dataclass
class ContractBackendServer:
    host: str
    port: int
    thread: threading.Thread
    server: uvicorn.Server

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def llm_base_url(self) -> str:
        return f"{self.base_url}/v1"

    @property
    def tts_base_url(self) -> str:
        return self.base_url

    @property
    def video_base_url(self) -> str:
        return self.base_url

    def http_env(self) -> dict[str, str]:
        return {
            "LLM_PROVIDER": "openai_compatible",
            "LLM_BASE_URL": self.llm_base_url,
            "TTS_PROVIDER": "http",
            "TTS_BASE_URL": self.tts_base_url,
            "VIDEO_PROVIDER": "http",
            "VIDEO_BASE_URL": self.video_base_url,
            "PROVIDER_GATE_ENABLED": "true",
            "PROVIDER_GATE_ALLOW_DEGRADED": "true",
        }

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=8)


def pick_free_port(host: str = DEFAULT_HOST) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def start_contract_backend(
    *,
    host: str = DEFAULT_HOST,
    port: int = 0,
) -> ContractBackendServer:
    """Start the contract backend in a background thread (real TCP)."""
    bound_port = port or pick_free_port(host)
    app = create_contract_app()
    config = uvicorn.Config(app, host=host, port=bound_port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="contract-backend")
    thread.start()
    deadline = time.time() + 6
    while time.time() < deadline:
        if server.started:
            return ContractBackendServer(host, bound_port, thread, server)
        if not thread.is_alive():
            break
        time.sleep(0.05)
    raise RuntimeError(f"Contract backend failed to start on {host}:{bound_port}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run local LLM/TTS/Video contract backend")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    app = create_contract_app()
    print(f"Contract backend on http://{args.host}:{args.port}")
    print(f"  LLM   {args.host}:{args.port}/v1  POST /chat/completions")
    print(f"  TTS   {args.host}:{args.port}     POST /synthesize")
    print(f"  Video {args.host}:{args.port}     POST /generate")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
