# ProCharacters Cloud

Live AI companion: WebRTC real-time avatar (video + audio) driven by LLM → TTS → MuseTalk video sync pipeline.

- **Streaming pipeline**: LLM tokens → chunked TTS audio → synchronized avatar video frames.
- **Transport**: WebRTC for low-latency delivery to browser + SSE fallback.
- **Modes**: `mock` (instant local dev) or `http` (RunPod / vLLM / custom endpoints).

## Quick Start

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. (Optional) configure real backends
cp .env.example .env
# edit .env → set LLM_PROVIDER=http etc + URLs

# 3. Run
uvicorn app.main:app --reload --port 8000
# open http://localhost:8000
```

In the UI:
- Click **Connect** (creates a new WebRTC session)
- Type in the chat box and Send → full LLM+TTS+Video pipeline runs and streams to avatar
- The 8-char session ID is shown in the video overlay badge
- To **resume** a session (e.g. after page reload while server is up): paste the ID into the Resume field and click Resume (or use the ↻ button to list active ones)

Disconnect leaves the server-side session alive for resume. Use server restart or explicit DELETE to fully end.

## Architecture

```
browser (WebRTC + SSE)
   ↕
FastAPI
├── /api/v1/webrtc/*     (signaling: /session, /offer, /ice-candidate, /sessions)
├── /api/v1/chat/perform (LLM + TTS + Video full pipeline, feeds bridge)
├── /api/v1/chat/speak   (LLM + TTS only)
└── pipelines
    ├── LLMStreamPipeline (mock | openai_compatible)
    ├── TTSStreamPipeline (mock | http)
    └── VideoSyncPipeline (mock | http MuseTalk)
            ↓
    AvatarMediaBridge → aiortc tracks → WebRTC
```

Key files:
- `app/main.py`, `app/core/config.py`
- `app/services/{llm,tts,video}/`
- `app/services/webrtc/{session_manager,media_bridge,tracks}.py`
- `client/{index.html,app.js,styles.css}` (served at `/`)

## Configuration (.env)

See `.env.example`. Important toggles:

| Key | Values | Notes |
|-----|--------|-------|
| `LLM_PROVIDER` | mock / openai_compatible | openai_compatible expects OpenAI chat/completions stream |
| `TTS_PROVIDER` | mock / http | http -> POST /synthesize (see contracts) |
| `VIDEO_PROVIDER` | mock / http | http -> POST /generate (see contracts) |
| `*_BASE_URL`, `*_API_KEY` | - | Point at your RunPod (or self-hosted) instances |
| `MOCK_REALISTIC` | true / false | realistic variable chunking + delays in mocks (demo mode) |

Mocks generate plausible output with small artificial delays for demo.
When `MOCK_REALISTIC=true` (default), mocks produce variable length chunks, jittered timings, punctuation-aware token streaming, and spread "compute" to better mimic real providers.

## Provider Contracts (exact shapes for real backends)

See detailed docstrings in:
- `app/services/llm/client.py` (OpenAICompatibleLLMClient)
- `app/services/tts/client.py` (HttpTTSClient)
- `app/services/video/client.py` (HttpMuseTalkClient)

### LLM (openai_compatible)
- `POST {LLM_BASE_URL}/chat/completions` (with `stream: true`)
- Request: standard OpenAI chat messages + max_tokens, temperature
- Streaming response: SSE `data: {... "choices":[{"delta":{"content":"..."}}] ...}` followed by `data: [DONE]`
- RunPod/vLLM/OpenAI compatible endpoints must implement this exactly for token streaming.

### TTS (http)
- `POST {TTS_BASE_URL}/synthesize`
- Request JSON: `{ "text": "...", "voice": "...", "format": "pcm_s16le", "sample_rate": 24000, "channels": 1 }`
- Response: JSON `{ "audio_b64": "..." }` OR raw PCM bytes
- Returns complete audio for the *chunk*. The app chunks text upstream.

### Video (http)
- `POST {VIDEO_BASE_URL}/generate`
- Request JSON includes: `audio_b64`, `duration_ms`, `avatar_id`, `fps`, `start_pts_ms`, `start_frame_index`
- Response: `{ "frames": [{"frame_index":0, "pts_ms":40, "frame_b64":"..."}, ...], "width"?, "height"? }`
- One POST per TTS audio chunk; frames are batched back.

RunPod-style workers should match the payload/response shapes above. Use the verification script for quick checks.

## Session Resume

- `GET /api/v1/webrtc/sessions` → `{sessions: [...], count}`
- Client supports "Resume" using an existing `session_id` in the SDP offer exchange (server reuses PC + bridge when possible).
- Works across browser reloads while the backend process keeps the in-memory session.

## Development

- Health: `curl http://localhost:8000/api/v1/health`
- Create session: `curl -X POST http://localhost:8000/api/v1/webrtc/session`
- List: `curl http://localhost:8000/api/v1/webrtc/sessions`
- Cleanup test sessions (dev helper): `curl -X DELETE http://localhost:8000/api/v1/webrtc/sessions`

Mock mode is fully functional end-to-end with no external services.

## Verification: Full "Mock Demo" from Terminal

A self-contained runnable script that exercises the **full pipeline + resume flow**:

```bash
# 1. Install (once)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Run the full verification demo (auto-starts server, creates session,
#    does WebRTC signaling with aiortc if available, calls /chat/perform,
#    parses SSE and counts token/audio/video_frame/done/error events,
#    re-uses the session_id to demonstrate resume, then cleans up)
python scripts/demo.py --start-server

# Or start server yourself in one terminal:
uvicorn app.main:app --reload
# Then in another:
python scripts/demo.py

# Fast variant (skips aiortc signaling, pure HTTP + SSE pipeline):
python scripts/demo.py --start-server --no-signaling

# Using make (after pip install):
make demo
make test
```

The demo:
- Uses `DELETE /webrtc/sessions` to avoid accumulation of test sessions.
- Calls `/webrtc/session` + (optional) `/webrtc/offer` (aiortc).
- Streams `/chat/perform` (LLM tokens → TextChunker → TTS audio chunks → SyncTimeline + video frames).
- Reports counts of each SSE event type.
- Performs two `/chat/perform` calls against the **same session_id** to show resume works.
- Prints ✅ SUCCESS when pipeline events and resume are observed.

Also works via `./scripts/run.sh --demo`

## Tests

Lightweight pytest-style tests exist for core pieces (no external services needed):

```bash
python -m pytest -q --tb=line
# or
make test
```

Covered:
- `SyncTimeline` (frame allocation, monotonic time)
- `TextChunker` (min/max chunking + boundary logic)
- Mock generation (MockLLMClient, MockTTSClient, MockMuseTalkClient)
- `WebRTCSessionManager` (create / list / close)

`python -m pytest` works after `pip install -r requirements.txt` (pytest + pytest-asyncio are included lightly).

To run a subset: `python -m pytest tests/test_sync_and_chunker.py -q`

## Status

Skeletal but runnable:
- Complete mock pipeline + WebRTC delivery
- Basic but working browser client
- HTTP adapters exist for production providers

Next areas (contributions welcome):
- Real provider implementations / contract tests
- Persistent session metadata
- Better renegotiation + reconnection UX
- Avatar selection, prompts, multi-turn memory
- Docker / deployment

Built with FastAPI + aiortc + pydantic.

