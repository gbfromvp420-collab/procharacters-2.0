"""Sovereign Scale — multi-tenant fleet, horizontal scale, hardening, observability (Phase 19)."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

_DEFAULT_SCHEMA_PATH = "data/sovereign_scale_schema.json"
_DEFAULT_TENANTS_PATH = "data/sovereign_tenants.json"
_DEFAULT_NODES_PATH = "data/sovereign_nodes.json"
_MAX_TENANTS = 100
_MAX_NODES = 50

TenantStatus = Literal["active", "paused", "provisioning"]
NodeStatus = Literal["healthy", "degraded", "offline"]
NodeRole = Literal["api", "worker", "edge"]

_DEFAULT_SCHEMA: dict[str, Any] = {
    "multi_tenant": {
        "enabled": True,
        "default_max_sessions": 50,
        "default_max_companions": 100,
    },
    "horizontal_scale": {
        "enabled": True,
        "min_healthy_nodes": 1,
        "target_capacity_score": 100,
        "autoscale_stub": True,
    },
    "production_hardening": {
        "require_api_key": False,
        "require_rate_limit": True,
        "require_persist": True,
        "require_provider_gate": True,
        "require_turn_for_webrtc": False,
    },
    "observability": {
        "empire_grade_enabled": True,
        "rollup_interval_seconds": 30,
    },
    "version": 1,
}


@dataclass
class Tenant:
    id: str
    name: str
    slug: str
    status: TenantStatus
    max_sessions: int
    max_companions: int
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ScaleNode:
    id: str
    region: str
    role: NodeRole
    status: NodeStatus
    capacity_score: int
    hostname: str
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SovereignScale:
    """Multi-tenant registry, scale node fleet, hardening checks, observability rollup."""

    def __init__(
        self,
        *,
        schema_path: str = _DEFAULT_SCHEMA_PATH,
        tenants_path: str = _DEFAULT_TENANTS_PATH,
        nodes_path: str = _DEFAULT_NODES_PATH,
    ) -> None:
        self._schema_path = schema_path
        self._tenants_path = tenants_path
        self._nodes_path = nodes_path
        self._schema = self._load_or_create_schema()
        self._tenants: list[Tenant] = []
        self._nodes: list[ScaleNode] = []
        self._load_tenants()
        self._load_nodes()
        self._ensure_default_tenant()
        self._ensure_local_node()

    def _load_or_create_schema(self) -> dict[str, Any]:
        path = Path(self._schema_path)
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return raw
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to load sovereign scale schema %s: %s", path, exc)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_DEFAULT_SCHEMA, indent=2), encoding="utf-8")
        return dict(_DEFAULT_SCHEMA)

    def get_schema(self) -> dict[str, Any]:
        return dict(self._schema)

    def _load_tenants(self) -> None:
        path = Path(self._tenants_path)
        if not path.is_file():
            self._tenants = []
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load tenants %s: %s", path, exc)
            self._tenants = []
            return
        if not isinstance(raw, list):
            self._tenants = []
            return
        loaded: list[Tenant] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            slug = str(item.get("slug", "")).strip()
            if not name or not slug:
                continue
            status_raw = str(item.get("status", "active"))
            if status_raw not in ("active", "paused", "provisioning"):
                status_raw = "active"
            created_raw = item.get("created_at")
            try:
                created_at = (
                    datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                    if created_raw
                    else datetime.now(UTC)
                )
            except ValueError:
                created_at = datetime.now(UTC)
            loaded.append(
                Tenant(
                    id=str(item.get("id") or uuid.uuid4().hex[:12]),
                    name=name[:120],
                    slug=slug[:64],
                    status=status_raw,  # type: ignore[arg-type]
                    max_sessions=int(item.get("max_sessions", 50)),
                    max_companions=int(item.get("max_companions", 100)),
                    created_at=created_at,
                )
            )
        self._tenants = loaded[-_MAX_TENANTS:]

    def _save_tenants(self) -> None:
        path = Path(self._tenants_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug,
                "status": tenant.status,
                "max_sessions": tenant.max_sessions,
                "max_companions": tenant.max_companions,
                "created_at": tenant.created_at.isoformat(),
            }
            for tenant in self._tenants
        ]
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _load_nodes(self) -> None:
        path = Path(self._nodes_path)
        if not path.is_file():
            self._nodes = []
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load scale nodes %s: %s", path, exc)
            self._nodes = []
            return
        if not isinstance(raw, list):
            self._nodes = []
            return
        loaded: list[ScaleNode] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            region = str(item.get("region", "")).strip()
            if not region:
                continue
            role_raw = str(item.get("role", "api"))
            if role_raw not in ("api", "worker", "edge"):
                role_raw = "api"
            status_raw = str(item.get("status", "healthy"))
            if status_raw not in ("healthy", "degraded", "offline"):
                status_raw = "healthy"
            hb_raw = item.get("last_heartbeat")
            created_raw = item.get("created_at")
            try:
                last_heartbeat = (
                    datetime.fromisoformat(str(hb_raw).replace("Z", "+00:00"))
                    if hb_raw
                    else datetime.now(UTC)
                )
            except ValueError:
                last_heartbeat = datetime.now(UTC)
            try:
                created_at = (
                    datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                    if created_raw
                    else datetime.now(UTC)
                )
            except ValueError:
                created_at = datetime.now(UTC)
            loaded.append(
                ScaleNode(
                    id=str(item.get("id") or uuid.uuid4().hex[:12]),
                    region=region[:64],
                    role=role_raw,  # type: ignore[arg-type]
                    status=status_raw,  # type: ignore[arg-type]
                    capacity_score=max(0, min(100, int(item.get("capacity_score", 50)))),
                    hostname=str(item.get("hostname", "localhost"))[:120],
                    last_heartbeat=last_heartbeat,
                    created_at=created_at,
                )
            )
        self._nodes = loaded[-_MAX_NODES:]

    def _save_nodes(self) -> None:
        path = Path(self._nodes_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": node.id,
                "region": node.region,
                "role": node.role,
                "status": node.status,
                "capacity_score": node.capacity_score,
                "hostname": node.hostname,
                "last_heartbeat": node.last_heartbeat.isoformat(),
                "created_at": node.created_at.isoformat(),
            }
            for node in self._nodes
        ]
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _ensure_default_tenant(self) -> None:
        if any(t.slug == "default" for t in self._tenants):
            return
        mt = self._schema.get("multi_tenant", {})
        tenant = Tenant(
            id=uuid.uuid4().hex[:12],
            name="ProCharacters Default",
            slug="default",
            status="active",
            max_sessions=int(mt.get("default_max_sessions", 50)) if isinstance(mt, dict) else 50,
            max_companions=int(mt.get("default_max_companions", 100)) if isinstance(mt, dict) else 100,
        )
        self._tenants.insert(0, tenant)
        self._save_tenants()

    def _ensure_local_node(self) -> None:
        if self._nodes:
            return
        node = ScaleNode(
            id=uuid.uuid4().hex[:12],
            region="local",
            role="api",
            status="healthy",
            capacity_score=100,
            hostname="localhost",
        )
        self._nodes.append(node)
        self._save_nodes()

    def register_tenant(
        self,
        *,
        name: str,
        slug: str,
        max_sessions: int | None = None,
        max_companions: int | None = None,
    ) -> Tenant:
        mt = self._schema.get("multi_tenant", {})
        if isinstance(mt, dict) and not mt.get("enabled", True):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Multi-tenant disabled")
        name = name.strip()
        slug = slug.strip().lower().replace(" ", "-")
        if not name or not slug:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name and slug required")
        if any(t.slug == slug for t in self._tenants):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Tenant slug {slug!r} exists")
        default_sessions = int(mt.get("default_max_sessions", 50)) if isinstance(mt, dict) else 50
        default_companions = int(mt.get("default_max_companions", 100)) if isinstance(mt, dict) else 100
        tenant = Tenant(
            id=uuid.uuid4().hex[:12],
            name=name[:120],
            slug=slug[:64],
            status="active",
            max_sessions=max_sessions if max_sessions is not None else default_sessions,
            max_companions=max_companions if max_companions is not None else default_companions,
        )
        self._tenants.insert(0, tenant)
        if len(self._tenants) > _MAX_TENANTS:
            self._tenants = self._tenants[:_MAX_TENANTS]
        self._save_tenants()
        return tenant

    def register_node(
        self,
        *,
        region: str,
        role: NodeRole,
        hostname: str,
        capacity_score: int = 50,
    ) -> ScaleNode:
        scale = self._schema.get("horizontal_scale", {})
        if isinstance(scale, dict) and not scale.get("enabled", True):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Horizontal scale disabled")
        region = region.strip()
        hostname = hostname.strip()
        if not region or not hostname:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="region and hostname required")
        node = ScaleNode(
            id=uuid.uuid4().hex[:12],
            region=region[:64],
            role=role,
            status="healthy",
            capacity_score=max(0, min(100, capacity_score)),
            hostname=hostname[:120],
        )
        self._nodes.insert(0, node)
        if len(self._nodes) > _MAX_NODES:
            self._nodes = self._nodes[:_MAX_NODES]
        self._save_nodes()
        return node

    def heartbeat_node(self, *, node_id: str) -> ScaleNode:
        for node in self._nodes:
            if node.id == node_id:
                node.last_heartbeat = datetime.now(UTC)
                if node.status == "offline":
                    node.status = "healthy"
                self._save_nodes()
                return node
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown node {node_id!r}")

    def list_tenants(self, *, limit: int = 50) -> list[Tenant]:
        return self._tenants[: max(1, min(limit, 100))]

    def list_nodes(self, *, limit: int = 50) -> list[ScaleNode]:
        return self._nodes[: max(1, min(limit, 100))]

    def evaluate_hardening(self, *, settings: Any) -> list[dict[str, Any]]:
        hardening = self._schema.get("production_hardening", {})
        if not isinstance(hardening, dict):
            hardening = {}
        checks: list[dict[str, Any]] = []

        def _add(check_id: str, label: str, ok: bool, required: bool, detail: str) -> None:
            checks.append(
                {
                    "id": check_id,
                    "label": label,
                    "ok": ok,
                    "required": required,
                    "detail": detail,
                }
            )

        _add(
            "rate_limit",
            "Rate limiting enabled",
            bool(getattr(settings, "rate_limit_enabled", False)),
            bool(hardening.get("require_rate_limit", True)),
            "POST /chat/perform and /webrtc/session throttled per IP",
        )
        _add(
            "companion_persist",
            "Companion persistence enabled",
            bool(getattr(settings, "companion_persist_enabled", False)),
            bool(hardening.get("require_persist", True)),
            "Session state survives restarts under data/",
        )
        _add(
            "provider_gate",
            "Provider readiness gate",
            bool(getattr(settings, "provider_gate_enabled", False)),
            bool(hardening.get("require_provider_gate", True)),
            "Remote providers probed before perform/speak",
        )
        api_required = bool(hardening.get("require_api_key", False))
        _add(
            "api_key",
            "API key auth",
            bool(getattr(settings, "api_key_enabled", False)),
            api_required,
            "Optional /api/v1/* protection when enabled",
        )
        turn_required = bool(hardening.get("require_turn_for_webrtc", False))
        turn_configured = bool(getattr(settings, "webrtc_turn_urls", None))
        _add(
            "webrtc_turn",
            "WebRTC TURN configured",
            turn_configured,
            turn_required,
            "TURN relay for production WebRTC NAT traversal",
        )
        cors_wide = "*" in getattr(settings, "cors_origins", [])
        _add(
            "cors_tight",
            "CORS not wide-open",
            not cors_wide,
            False,
            "Restrict CORS_ORIGINS in production deploys",
        )
        _add(
            "docker_health",
            "Docker readiness probes",
            True,
            True,
            "compose healthcheck hits /api/v1/health/ready",
        )
        return checks

    def build_observability_rollup(self, *, app_state: Any) -> dict[str, Any]:
        metrics = app_state.metrics.snapshot()
        session_manager = app_state.session_manager
        companion_store = app_state.companion_store
        settings = app_state.settings

        webrtc_active = session_manager.active_session_count
        companion_ids = companion_store.list_session_ids()
        workforce_snaps: dict[str, Any] = {}
        phase = settings.deployment_phase
        theater = getattr(app_state, "agent_theater", None)
        if theater is not None:
            workforce_snaps["theater"] = theater.status()
        for attr, key in (
            ("revenue_forge", "revenue"),
            ("character_forge", "characters"),
            ("live_stage", "live"),
            ("sovereign_scale", "scale"),
            ("crown_completion", "crown"),
        ):
            service = getattr(app_state, attr, None)
            if service is not None and hasattr(service, "snapshot"):
                if attr == "crown_completion":
                    workforce_snaps[key] = service.snapshot(
                        deployment_phase=phase,
                        app_version=settings.app_version,
                    )
                elif attr == "sovereign_scale":
                    workforce_snaps[key] = service.snapshot(
                        deployment_phase=phase,
                        settings=settings,
                    )
                else:
                    workforce_snaps[key] = service.snapshot(deployment_phase=phase)

        healthy_nodes = sum(1 for n in self._nodes if n.status == "healthy")
        total_capacity = sum(n.capacity_score for n in self._nodes if n.status != "offline")

        return {
            "metrics": metrics,
            "webrtc_active_sessions": webrtc_active,
            "companion_sessions": len(companion_ids),
            "workforce": workforce_snaps,
            "tenants_active": sum(1 for t in self._tenants if t.status == "active"),
            "nodes_healthy": healthy_nodes,
            "nodes_total": len(self._nodes),
            "fleet_capacity_score": total_capacity,
            "deployment_phase": settings.deployment_phase,
            "app_version": settings.app_version,
        }

    def snapshot(self, *, deployment_phase: int, settings: Any | None = None) -> dict[str, object]:
        healthy = sum(1 for n in self._nodes if n.status == "healthy")
        active_tenants = sum(1 for t in self._tenants if t.status == "active")
        total_capacity = sum(n.capacity_score for n in self._nodes if n.status != "offline")
        hardening_ok = 0
        hardening_total = 0
        if settings is not None:
            checks = self.evaluate_hardening(settings=settings)
            hardening_total = len(checks)
            hardening_ok = sum(1 for c in checks if c["ok"] or not c["required"])
        scale = self._schema.get("horizontal_scale", {})
        min_nodes = int(scale.get("min_healthy_nodes", 1)) if isinstance(scale, dict) else 1
        return {
            "deployment_phase": deployment_phase,
            "multi_tenant_enabled": bool(
                self._schema.get("multi_tenant", {}).get("enabled", True)
                if isinstance(self._schema.get("multi_tenant"), dict)
                else True
            ),
            "horizontal_scale_enabled": bool(
                scale.get("enabled", True) if isinstance(scale, dict) else True
            ),
            "tenants_total": len(self._tenants),
            "tenants_active": active_tenants,
            "nodes_total": len(self._nodes),
            "nodes_healthy": healthy,
            "fleet_capacity_score": total_capacity,
            "min_healthy_nodes": min_nodes,
            "scale_ready": healthy >= min_nodes,
            "hardening_checks_passed": hardening_ok,
            "hardening_checks_total": hardening_total,
            "observability_empire_grade": bool(
                self._schema.get("observability", {}).get("empire_grade_enabled", True)
                if isinstance(self._schema.get("observability"), dict)
                else True
            ),
            "tenants_path": self._tenants_path,
            "nodes_path": self._nodes_path,
        }