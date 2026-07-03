import time

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from app.services.observability.metrics import MetricsCollector
from app.services.observability.prometheus import format_prometheus_metrics

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


@router.get(
    "/metrics/prometheus",
    summary="Prometheus text exposition of in-memory counters and uptime",
    response_class=PlainTextResponse,
)
async def get_prometheus_metrics(request: Request) -> PlainTextResponse:
    metrics: MetricsCollector = request.app.state.metrics
    started_at: float = request.app.state.started_at_monotonic
    uptime = round(time.monotonic() - started_at, 3)
    body = format_prometheus_metrics(metrics, uptime)
    return PlainTextResponse(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")