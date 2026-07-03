from fastapi import APIRouter

from app.api.routes import chat, companion, health, llm, metrics, providers, tts, video, webrtc

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(metrics.router)
api_router.include_router(providers.router)
api_router.include_router(llm.router)
api_router.include_router(tts.router)
api_router.include_router(video.router)
api_router.include_router(chat.router)
api_router.include_router(companion.router)
api_router.include_router(webrtc.router)