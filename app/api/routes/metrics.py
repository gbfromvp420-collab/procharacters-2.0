import time

from fastapi import APIRouter, Request

from app.services.observability.metrics import MetricsCollector

router = APIRouter(tags=["metrics"])


@router.get(
    "/metrics",
    summary="In-memory counters and process uptime",
)
async def get_metrics(request: Request) -> dict:
    metrics: MetricsCollector = request.app.state.metrics
    started_at: float = request.app.state.started_at_monotonic
    return {
        **metrics.snapshot(),
        "uptime_seconds": round(time.monotonic() - started_at, 3),
    }