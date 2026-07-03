"""Bond score (0–100) derived from conversation depth and relationship mode."""

from __future__ import annotations

_RELATIONSHIP_BOND_BOOST: dict[str, int] = {
    "friendly": 0,
    "flirtatious": 4,
    "romantic": 8,
    "deep": 12,
}


def compute_bond_score(turn_count: int, relationship_mode: str = "") -> int:
    """Compute affinity bond score capped at 100."""
    turns = max(0, turn_count)
    base = min(turns * 7, 88)
    boost = _RELATIONSHIP_BOND_BOOST.get((relationship_mode or "").strip().lower(), 0)
    return min(100, base + boost)