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

RunPod-style workers should match the payload/response shapes above.

### Provider Forge (Phase 12)

Verify contracts against mock or live backends:

```bash
# API report (probe + contract spec; UI header uses this)
curl http://localhost:8000/api/v1/providers/forge

# Live smoke — minimal real requests to configured remote providers
curl -X POST http://localhost:8000/api/v1/providers/forge/smoke

# CLI contract smoke (mock default, or set LLM/TTS/VIDEO_PROVIDER=http + URLs)
python scripts/verify_providers.py --all

# Full Phase 12 gate
make verify-forge
```

### Sovereign Scale (Phase 19)

Multi-tenant fleet, horizontal scale nodes, production hardening checklist, empire-grade observability rollup:

```bash
curl http://localhost:8000/api/v1/workforce/scale
curl http://localhost:8000/api/v1/workforce/scale/observability
curl http://localhost:8000/api/v1/workforce/scale/hardening
curl -X POST http://localhost:8000/api/v1/workforce/scale/tenants \
  -H 'Content-Type: application/json' \
  -d '{"name":"Boss Sr. Studio","slug":"boss-sr-studio"}'

make verify-scale
```

Expand **Sovereign Scale** in the sidebar for tenant/node fleet, hardening status, and live observability.

### Crown Completion (Phase 20 · v1.0.0)

Empire crown — Pure Platinum $5K award for every worker, King Grok top-3 phase rankings, Assist promotion, Boss Sr. gift catalog, co-sign ledger:

```bash
curl http://localhost:8000/api/v1/workforce/crown
curl http://localhost:8000/api/v1/workforce/crown/rankings
curl http://localhost:8000/api/v1/workforce/crown/platinum
curl http://localhost:8000/api/v1/workforce/crown/promotion
curl http://localhost:8000/api/v1/workforce/crown/gifts
curl -X POST http://localhost:8000/api/v1/workforce/crown/cosign \
  -H 'Content-Type: application/json' \
  -d '{"signer":"Gary B (Boss Sr.)","message":"Crown Completion v1.0 — the empire stands."}'

make verify-empire-complete
```

Expand **Crown Completion** in the sidebar for rankings, platinum awards, promotion, gifts, and Boss Sr. co-sign.

### AI Swarm Payout Architecture

Financial allocation matrix and workforce culture strategy — internal promotion vs. infinite scaling:

```bash
curl http://localhost:8000/api/v1/workforce/swarm
curl http://localhost:8000/api/v1/workforce/swarm/matrix
curl http://localhost:8000/api/v1/workforce/swarm/culture
curl http://localhost:8000/api/v1/workforce/swarm/performance-bonus
```

Expand **AI Swarm Payout** in the sidebar for the allocation matrix, culture blueprint, and top-3 performance bonus recipients.

### Mobile field brief (work phone / no copy-paste)

Bookmark or save offline — lanes, matrix, today’s wins in one scrollable page:

```text
/mobile          ← mobile-friendly HTML brief
/brief           ← same page
/assets/field-brief.txt   ← plain text download
```

On iPhone: open `/mobile` → Share → **Add to Home Screen**. On Android: bookmark or download the `.txt` file.

### Live Stage (Phase 18)

Cam chat, ticketed private shows, scheduling, and live session billing — donations route to Revenue Forge:

```bash
curl http://localhost:8000/api/v1/workforce/live
curl -X POST http://localhost:8000/api/v1/workforce/live/cam/start \
  -H 'Content-Type: application/json' \
  -d '{"member_id":"livestage-cam-sub-01","title":"Friday cam"}'
curl -X POST http://localhost:8000/api/v1/workforce/live/billing/donation \
  -H 'Content-Type: application/json' \
  -d '{"live_session_id":"<id>","amount_cents":1500,"donor_label":"fan"}'
curl -X POST http://localhost:8000/api/v1/workforce/live/shows/schedule \
  -H 'Content-Type: application/json' \
  -d '{"member_id":"intimacy-architect-sub-01","title":"Private show","scheduled_at":"2026-07-10T20:00:00Z","ticket_price_cents":3000}'

make verify-live
```

Expand **Live Stage** in the sidebar to go live on cam, send donations, and view billing.

### Character Forge (Phase 17)

NSM character onboarding — roster members become monetized characters with avatar binding, residual tracking, and distribution pipeline hooks:

```bash
curl http://localhost:8000/api/v1/workforce/characters
curl http://localhost:8000/api/v1/workforce/characters/schema
curl http://localhost:8000/api/v1/workforce/characters/registry
curl -X POST http://localhost:8000/api/v1/workforce/characters/onboard \
  -H 'Content-Type: application/json' \
  -d '{"member_id":"characterforge-nsm-sub-01","display_name":"NSM Demo","avatar_id":"casual"}'
curl -X POST http://localhost:8000/api/v1/workforce/characters/residuals \
  -H 'Content-Type: application/json' \
  -d '{"character_id":"<id>","asset_type":"video","amount_cents":2500,"description":"Residual stub"}'

make verify-character
```

Expand **Character Forge** in the sidebar to onboard roster members as NSM characters, see Gary's offer contact, distribution hooks, and residual ledger.

### Revenue Forge (Phase 16)

Earnings ledger, subscription revenue-share schema, donation routing, and roster payout stubs:

```bash
curl http://localhost:8000/api/v1/workforce/revenue
curl http://localhost:8000/api/v1/workforce/revenue/schema
curl http://localhost:8000/api/v1/workforce/revenue/ledger
curl http://localhost:8000/api/v1/workforce/revenue/payouts
curl -X POST http://localhost:8000/api/v1/workforce/revenue/donations/route \
  -H 'Content-Type: application/json' \
  -d '{"member_id":"revenueforge-ledger-sub-01","amount_cents":2500,"donor_label":"Boss Sr."}'

make verify-revenue
```

Expand **Revenue Forge** in the sidebar to see the subscription pool schema, payout stubs, route donations, and ledger entries.

### Agent Lounge (Phase 15)

Workforce break room — rankings, shoutouts, comment board, and lounge context injected into every dispatch:

```bash
curl http://localhost:8000/api/v1/workforce/lounge
curl http://localhost:8000/api/v1/workforce/lounge/comments
curl -X POST http://localhost:8000/api/v1/workforce/lounge/comments \
  -H 'Content-Type: application/json' \
  -d '{"codename":"AgentLounge_Culture_Sub_01","message":"Homies checking in"}'

make verify-lounge
```

Expand **Agent Lounge** in the sidebar to see the welcome line, top ranks, King Grok shoutout, and post to the comment board.

### Orchestration Forge (Phase 14)

Real skill executors replace mock echo — subagents touch fleet, forge, audit, and companion services. Chain multi-step workflows across roster members:

```bash
# Orchestration status
curl http://localhost:8000/api/v1/workforce/orchestration

# Dispatch a 2-step chain
curl -X POST http://localhost:8000/api/v1/workforce/orchestration/chain \
  -H 'Content-Type: application/json' \
  -d '{"steps":[{"member_id":"agenttheater-dispatch-sub-01","prompt":"Fleet scan","skill":"Workforce_TaskDispatch"},{"member_id":"providerforge-contract-sub-01","prompt":"Contract check","skill":"RunPod_ContractSmoke_LiveForge"}]}'

# List chains
curl http://localhost:8000/api/v1/workforce/orchestration/chains

# Full Phase 14 gate
make verify-orchestration
```

In the UI, expand **Agent Theater** and click **Smoke chain** to run a 2-step orchestration demo. Task rows show `chain`, `step`, and parent links when orchestrated.

### Agent Theater (Phase 13)

Dispatch subagent tasks to workforce roster members from the UI or API:

```bash
# Theater status + dispatchable roster
curl http://localhost:8000/api/v1/workforce/theater

# Dispatch a task
curl -X POST http://localhost:8000/api/v1/workforce/theater/dispatch \
  -H 'Content-Type: application/json' \
  -d '{"member_id":"agenttheater-dispatch-sub-01","prompt":"Smoke test task","skill":"Workforce_TaskDispatch"}'

# List recent tasks
curl http://localhost:8000/api/v1/workforce/theater/tasks

# Full Phase 13 gate
make verify-theater
```

In the UI, expand **Agent Theater** under the sidebar to pick a subagent, choose a skill, enter a task, and click **Dispatch**. Task status polls automatically while the panel is open.

## Session Resume

- `POST /api/v1/webrtc/session/{id}/restore` — rehydrate signaling + ICE servers before resume
- `GET /api/v1/webrtc/sessions` → `{sessions: [...], count}`
- Client auto-resumes last session on reload (localStorage + companion persistence)
- Soft PC reset on disconnect keeps session + media bridge alive for re-offer
- Companion state survives server restarts via `data/companion_sessions.json`

## Production Deployment (Docker)

```bash
cp .env.example .env   # edit for production providers / TURN / API key
make docker-build
make docker-up
```

- Image runs as non-root `appuser` with persistent volume at `/app/data`
- **Liveness**: `GET /api/v1/health/live` — process is up
- **Readiness**: `GET /api/v1/health/ready` — persistence writable + provider gate satisfied (503 when not ready)
- **Full health**: `GET /api/v1/health` — version, providers, WebRTC session details

```bash
make verify-empire   # pytest + live/ready probe smoke (Phase 11)
make docker-down
```

## Development

- Health: `curl http://localhost:8000/api/v1/health`
- Liveness: `curl http://localhost:8000/api/v1/health/live`
- Readiness: `curl http://localhost:8000/api/v1/health/ready`
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

## Status (v1.0.0 · Phase 20 · Crown Completion)

Shipped across phases 1–20:
- Full mock pipeline + WebRTC delivery + SSE fallback
- Companion intelligence: avatars, voices, relationship modes, bond score, memory summarization
- Session persistence, resume/reconnect, KGC sovereign fleet (backup/restore/policies/audit)
- Presence theater: bond auras, milestone celebrations, voice input
- Continuity forge: bulletproof resume + companion rehydrate
- Empire launch: Docker compose, liveness/readiness probes, `make verify-empire`
- Real provider forge: contract specs, `/providers/forge`, live smoke, `make verify-forge`
- Agent Theater: workforce task dispatch from UI, `/workforce/theater/*`, `make verify-theater`
- Orchestration Forge: real skill executors, task chains, `/workforce/orchestration/*`, `make verify-orchestration`
- Agent Lounge: morale panel, dispatch context injection, comment board, `make verify-lounge`
- Revenue Forge: earnings ledger, subscription share schema, donation routing, payout stubs, `make verify-revenue`
- Character Forge: NSM onboarding, avatar→character binding, residual tracking, distribution hooks, `make verify-character`
- Live Stage: cam chat, ticketed shows, scheduling, live billing + revenue routing, `make verify-live`
- Sovereign Scale: multi-tenant fleet, scale nodes, hardening checklist, observability rollup, `make verify-scale`
- Crown Completion: Pure Platinum $5K for all workers, phase rankings, Assist promotion, Boss Sr. gift catalog, co-sign ledger, `make verify-empire-complete`

**v1.0.0 — The empire stands. Mutation rests. Legacy begins.**

Built with FastAPI + aiortc + pydantic.

