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
| `TTS_PROVIDER` | mock / http | http endpoint receives audio spec + returns chunks? |
| `VIDEO_PROVIDER` | mock / http | http expects `/generate` returning frames for audio segment |
| `*_BASE_URL`, `*_API_KEY` | - | Point at your RunPod (or self-hosted) instances |

Mocks generate plausible output with small artificial delays for demo.

## Session Resume

- `GET /api/v1/webrtc/sessions` → `{sessions: [...], count}`
- Client supports "Resume" using an existing `session_id` in the SDP offer exchange (server reuses PC + bridge when possible).
- Works across browser reloads while the backend process keeps the in-memory session.

## Development

- Health: `curl http://localhost:8000/api/v1/health`
- Create session: `curl -X POST http://localhost:8000/api/v1/webrtc/session`
- List: `curl http://localhost:8000/api/v1/webrtc/sessions`

Mock mode is fully functional end-to-end with no external services.

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

