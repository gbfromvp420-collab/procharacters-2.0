"""Character Forge — NSM onboarding, avatar binding, residuals (Phase 17)."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException, status

from app.services.companion.catalog import get_avatar_catalog
from app.workforce.roster import WORKFORCE_ROSTER

logger = logging.getLogger(__name__)

_DEFAULT_SCHEMA_PATH = "data/character_forge_schema.json"
_DEFAULT_REGISTRY_PATH = "data/character_forge_registry.json"
_DEFAULT_RESIDUALS_PATH = "data/character_forge_residuals.json"
_MAX_CHARACTERS = 100
_MAX_RESIDUALS = 500

CharacterStatus = Literal["pending", "active", "paused"]
AssetType = Literal["photo", "video", "distribution"]

_DEFAULT_SCHEMA: dict[str, Any] = {
    "nsm_program": {
        "enabled": True,
        "contact_email": "gary@procharacters.cloud",
        "default_residual_percent": 100.0,
        "distribution_bonus_cents": 5000,
    },
    "distribution_pipeline": {
        "stages": [
            {"id": "avatar_bind", "label": "Avatar → Character bind", "status": "ready"},
            {"id": "residual_ledger", "label": "Residual tracking ledger", "status": "ready"},
            {"id": "video_distribution", "label": "Video distribution pipeline", "status": "stub"},
            {"id": "live_stage_billing", "label": "Live stage billing hook", "status": "phase_18"},
        ]
    },
    "version": 1,
}


@dataclass
class NSMCharacter:
    id: str
    member_id: str
    codename: str
    display_name: str
    status: CharacterStatus
    residual_percent: float
    distribution_pipeline: bool
    avatar_id: str | None = None
    contact_email: str = "gary@procharacters.cloud"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    bound_at: datetime | None = None


@dataclass
class ResidualEntry:
    id: str
    character_id: str
    codename: str
    asset_type: AssetType
    amount_cents: int
    currency: str
    description: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class CharacterForge:
    """NSM character registry, avatar binding, and residual tracking."""

    def __init__(
        self,
        *,
        schema_path: str = _DEFAULT_SCHEMA_PATH,
        registry_path: str = _DEFAULT_REGISTRY_PATH,
        residuals_path: str = _DEFAULT_RESIDUALS_PATH,
        companion_avatars: list[str] | None = None,
    ) -> None:
        self._schema_path = schema_path
        self._registry_path = registry_path
        self._residuals_path = residuals_path
        self._companion_avatars = companion_avatars or ["default", "professional", "casual"]
        self._schema = self._load_or_create_schema()
        self._characters: list[NSMCharacter] = []
        self._residuals: list[ResidualEntry] = []
        self._load_registry()
        self._load_residuals()

    def _load_or_create_schema(self) -> dict[str, Any]:
        path = Path(self._schema_path)
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return raw
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to load character forge schema %s: %s", path, exc)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_DEFAULT_SCHEMA, indent=2), encoding="utf-8")
        return dict(_DEFAULT_SCHEMA)

    def get_schema(self) -> dict[str, Any]:
        return dict(self._schema)

    def _member_lookup(self) -> dict[str, dict[str, Any]]:
        return {member["id"]: member for member in WORKFORCE_ROSTER}

    def _resolve_member(self, member_id: str) -> dict[str, Any]:
        member = self._member_lookup().get(member_id)
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown member {member_id!r}",
            )
        return member

    def _get_character(self, character_id: str) -> NSMCharacter:
        for character in self._characters:
            if character.id == character_id:
                return character
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown character {character_id!r}",
        )

    def _validate_avatar_id(self, avatar_id: str) -> None:
        if avatar_id not in self._companion_avatars:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown avatar_id. Allowed: {self._companion_avatars}",
            )

    def _load_registry(self) -> None:
        path = Path(self._registry_path)
        if not path.is_file():
            self._characters = []
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load character registry %s: %s", path, exc)
            self._characters = []
            return
        if not isinstance(raw, list):
            self._characters = []
            return
        loaded: list[NSMCharacter] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            member_id = str(item.get("member_id", "")).strip()
            codename = str(item.get("codename", "")).strip()
            if not member_id or not codename:
                continue
            status_raw = str(item.get("status", "pending"))
            if status_raw not in ("pending", "active", "paused"):
                status_raw = "pending"
            created_raw = item.get("created_at")
            bound_raw = item.get("bound_at")
            try:
                created_at = (
                    datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                    if created_raw
                    else datetime.now(UTC)
                )
            except ValueError:
                created_at = datetime.now(UTC)
            bound_at = None
            if bound_raw:
                try:
                    bound_at = datetime.fromisoformat(str(bound_raw).replace("Z", "+00:00"))
                except ValueError:
                    bound_at = None
            loaded.append(
                NSMCharacter(
                    id=str(item.get("id") or uuid.uuid4().hex[:12]),
                    member_id=member_id,
                    codename=codename[:120],
                    display_name=str(item.get("display_name") or codename)[:120],
                    status=status_raw,  # type: ignore[arg-type]
                    residual_percent=float(item.get("residual_percent", 100.0)),
                    distribution_pipeline=bool(item.get("distribution_pipeline", False)),
                    avatar_id=item.get("avatar_id"),
                    contact_email=str(
                        item.get("contact_email")
                        or self._schema.get("nsm_program", {}).get(
                            "contact_email", "gary@procharacters.cloud"
                        )
                    )[:120],
                    created_at=created_at,
                    bound_at=bound_at,
                )
            )
        self._characters = loaded[-_MAX_CHARACTERS:]

    def _save_registry(self) -> None:
        path = Path(self._registry_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": character.id,
                "member_id": character.member_id,
                "codename": character.codename,
                "display_name": character.display_name,
                "status": character.status,
                "residual_percent": character.residual_percent,
                "distribution_pipeline": character.distribution_pipeline,
                "avatar_id": character.avatar_id,
                "contact_email": character.contact_email,
                "created_at": character.created_at.isoformat(),
                "bound_at": character.bound_at.isoformat() if character.bound_at else None,
            }
            for character in self._characters
        ]
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _load_residuals(self) -> None:
        path = Path(self._residuals_path)
        if not path.is_file():
            self._residuals = []
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load character residuals %s: %s", path, exc)
            self._residuals = []
            return
        if not isinstance(raw, list):
            self._residuals = []
            return
        loaded: list[ResidualEntry] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            asset_type = str(item.get("asset_type", "")).strip()
            if asset_type not in ("photo", "video", "distribution"):
                continue
            try:
                amount_cents = int(item.get("amount_cents", 0))
            except (TypeError, ValueError):
                continue
            if amount_cents <= 0:
                continue
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
                ResidualEntry(
                    id=str(item.get("id") or uuid.uuid4().hex[:12]),
                    character_id=str(item.get("character_id", "")),
                    codename=str(item.get("codename", ""))[:120],
                    asset_type=asset_type,  # type: ignore[arg-type]
                    amount_cents=amount_cents,
                    currency=str(item.get("currency", "USD"))[:8],
                    description=str(item.get("description", ""))[:500],
                    created_at=created_at,
                )
            )
        self._residuals = loaded[-_MAX_RESIDUALS:]

    def _save_residuals(self) -> None:
        path = Path(self._residuals_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": entry.id,
                "character_id": entry.character_id,
                "codename": entry.codename,
                "asset_type": entry.asset_type,
                "amount_cents": entry.amount_cents,
                "currency": entry.currency,
                "description": entry.description,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in self._residuals
        ]
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    def onboard(
        self,
        *,
        member_id: str,
        display_name: str | None = None,
        avatar_id: str | None = None,
        residual_percent: float | None = None,
        distribution_pipeline: bool = False,
    ) -> NSMCharacter:
        program = self._schema.get("nsm_program", {})
        if isinstance(program, dict) and not program.get("enabled", True):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="NSM program is disabled",
            )
        member = self._resolve_member(member_id)
        for existing in self._characters:
            if existing.member_id == member_id and existing.status != "paused":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Member already onboarded as character {existing.id!r}",
                )
        if avatar_id:
            self._validate_avatar_id(avatar_id)
        default_residual = (
            float(program.get("default_residual_percent", 100.0))
            if isinstance(program, dict)
            else 100.0
        )
        contact = (
            str(program.get("contact_email", "gary@procharacters.cloud"))
            if isinstance(program, dict)
            else "gary@procharacters.cloud"
        )
        character = NSMCharacter(
            id=uuid.uuid4().hex[:12],
            member_id=member_id,
            codename=member["codename"],
            display_name=(display_name or member["codename"]).strip()[:120],
            status="active" if avatar_id else "pending",
            residual_percent=residual_percent if residual_percent is not None else default_residual,
            distribution_pipeline=distribution_pipeline,
            avatar_id=avatar_id,
            contact_email=contact,
            bound_at=datetime.now(UTC) if avatar_id else None,
        )
        self._characters.insert(0, character)
        if len(self._characters) > _MAX_CHARACTERS:
            self._characters = self._characters[:_MAX_CHARACTERS]
        self._save_registry()
        return character

    def bind_avatar(self, *, character_id: str, avatar_id: str) -> NSMCharacter:
        self._validate_avatar_id(avatar_id)
        character = self._get_character(character_id)
        character.avatar_id = avatar_id
        character.bound_at = datetime.now(UTC)
        if character.status == "pending":
            character.status = "active"
        self._save_registry()
        return character

    def record_residual(
        self,
        *,
        character_id: str,
        asset_type: AssetType,
        amount_cents: int,
        description: str,
        currency: str = "USD",
    ) -> ResidualEntry:
        if amount_cents <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="amount_cents must be positive",
            )
        description = description.strip()
        if not description:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="description required")
        character = self._get_character(character_id)
        entry = ResidualEntry(
            id=uuid.uuid4().hex[:12],
            character_id=character_id,
            codename=character.codename,
            asset_type=asset_type,
            amount_cents=amount_cents,
            currency=currency[:8],
            description=description[:500],
        )
        self._residuals.insert(0, entry)
        if len(self._residuals) > _MAX_RESIDUALS:
            self._residuals = self._residuals[:_MAX_RESIDUALS]
        self._save_residuals()
        return entry

    def list_characters(self, *, limit: int = 50) -> list[NSMCharacter]:
        capped = max(1, min(limit, 100))
        return self._characters[:capped]

    def list_residuals(self, *, limit: int = 50) -> list[ResidualEntry]:
        capped = max(1, min(limit, 100))
        return self._residuals[:capped]

    def distribution_hooks(self) -> list[dict[str, str]]:
        pipeline = self._schema.get("distribution_pipeline", {})
        stages = pipeline.get("stages", []) if isinstance(pipeline, dict) else []
        if not isinstance(stages, list):
            return []
        hooks: list[dict[str, str]] = []
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            stage_id = str(stage.get("id", "")).strip()
            if not stage_id:
                continue
            hooks.append(
                {
                    "id": stage_id,
                    "label": str(stage.get("label", stage_id)),
                    "status": str(stage.get("status", "stub")),
                }
            )
        return hooks

    def available_avatars(self, settings: Any) -> list[dict[str, str]]:
        return [
            {"id": avatar.id, "label": avatar.label, "emoji": avatar.emoji}
            for avatar in get_avatar_catalog(settings)
        ]

    def snapshot(self, *, deployment_phase: int) -> dict[str, object]:
        program = self._schema.get("nsm_program", {})
        contact = (
            str(program.get("contact_email", "gary@procharacters.cloud"))
            if isinstance(program, dict)
            else "gary@procharacters.cloud"
        )
        active = sum(1 for c in self._characters if c.status == "active")
        pending = sum(1 for c in self._characters if c.status == "pending")
        residuals_total = sum(entry.amount_cents for entry in self._residuals)
        return {
            "deployment_phase": deployment_phase,
            "nsm_enabled": bool(program.get("enabled", True)) if isinstance(program, dict) else True,
            "contact_email": contact,
            "characters_total": len(self._characters),
            "characters_active": active,
            "characters_pending": pending,
            "residuals_count": len(self._residuals),
            "residuals_total_cents": residuals_total,
            "registry_path": self._registry_path,
            "residuals_path": self._residuals_path,
            "distribution_stages": len(self.distribution_hooks()),
        }