"""Presence theater configuration — bond-tier auras and celebration metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BondPresenceTier:
    id: str
    label: str
    min_bond: int
    aura_color: str
    glow_intensity: float


BOND_PRESENCE_TIERS: tuple[BondPresenceTier, ...] = (
    BondPresenceTier(
        id="spark",
        label="Spark",
        min_bond=0,
        aura_color="#6c8cff",
        glow_intensity=0.35,
    ),
    BondPresenceTier(
        id="warmth",
        label="Warmth",
        min_bond=25,
        aura_color="#ff8fa3",
        glow_intensity=0.5,
    ),
    BondPresenceTier(
        id="trust",
        label="Trusted",
        min_bond=50,
        aura_color="#ffd878",
        glow_intensity=0.62,
    ),
    BondPresenceTier(
        id="depth",
        label="Deep Bond",
        min_bond=75,
        aura_color="#c77dff",
        glow_intensity=0.78,
    ),
    BondPresenceTier(
        id="inseparable",
        label="Inseparable",
        min_bond=100,
        aura_color="#ffe566",
        glow_intensity=1.0,
    ),
)


def resolve_bond_tier(bond_score: int) -> BondPresenceTier:
    """Return the highest presence tier unlocked by bond_score."""
    score = max(0, min(100, bond_score))
    tier = BOND_PRESENCE_TIERS[0]
    for candidate in BOND_PRESENCE_TIERS:
        if score >= candidate.min_bond:
            tier = candidate
    return tier


def get_presence_config() -> dict[str, object]:
    """Serialize presence theater settings for the client."""
    return {
        "celebration_enabled": True,
        "voice_input_enabled": True,
        "voice_input_hint": "Tap the mic to speak — uses browser speech recognition when available.",
        "bond_tiers": [
            {
                "id": tier.id,
                "label": tier.label,
                "min_bond": tier.min_bond,
                "aura_color": tier.aura_color,
                "glow_intensity": tier.glow_intensity,
            }
            for tier in BOND_PRESENCE_TIERS
        ],
    }