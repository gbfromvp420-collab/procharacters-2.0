"""Prometheus text exposition format for in-memory metrics."""

from __future__ import annotations

from app.services.observability.metrics import MetricsCollector

_COUNTER_FIELDS = (
    "perform_requests",
    "speak_requests",
    "tokens_streamed",
    "sessions_created",
    "sessions_closed",
    "companion_turns_saved",
    "bond_increments",
    "sessions_cloned",
    "sessions_imported",
)


def format_prometheus_metrics(metrics: MetricsCollector, uptime_seconds: float) -> str:
    snapshot = metrics.snapshot()
    lines: list[str] = []

    for name in _COUNTER_FIELDS:
        value = snapshot.get(name, 0)
        lines.append(f"# HELP procharacters_{name} Total {name.replace('_', ' ')}")
        lines.append(f"# TYPE procharacters_{name} counter")
        lines.append(f"procharacters_{name} {value}")

    lines.append("# HELP procharacters_uptime_seconds Process uptime in seconds")
    lines.append("# TYPE procharacters_uptime_seconds gauge")
    lines.append(f"procharacters_uptime_seconds {uptime_seconds}")

    return "\n".join(lines) + "\n"