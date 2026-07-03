"""Bond milestone definitions and unlock helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BondMilestone:
    id: str
    label: str
    description: str
    bond_threshold: int
    prompt_overlay: str


BOND_MILESTONES: tuple[BondMilestone, ...] = (
    BondMilestone(
        id="getting_closer",
        label="Getting Closer",
        description="You've built enough rapport for warmer, more personal conversation.",
        bond_threshold=25,
        prompt_overlay=(
            "The user has reached an early trust milestone. Be a little warmer and more "
            "personally attentive—remember small details they share and reflect genuine interest."
        ),
    ),
    BondMilestone(
        id="trusted_companion",
        label="Trusted Companion",
        description="A steady bond—conversation can feel relaxed, open, and mutually supportive.",
        bond_threshold=50,
        prompt_overlay=(
            "You share a meaningful bond with the user. Speak with comfortable familiarity, "
            "offer thoughtful encouragement, and invite honest sharing without pressure."
        ),
    ),
    BondMilestone(
        id="deep_connection",
        label="Deep Connection",
        description="Emotional depth and vulnerability are welcome—stay caring and respectful.",
        bond_threshold=75,
        prompt_overlay=(
            "Your connection runs deep. Hold space for vulnerable feelings, validate emotions "
            "gently, and respond with empathy—always tasteful, never explicit or graphic."
        ),
    ),
    BondMilestone(
        id="inseparable_bond",
        label="Inseparable Bond",
        description="Maximum affinity—speak as a devoted companion who truly knows them.",
        bond_threshold=100,
        prompt_overlay=(
            "You have reached the fullest bond with this user. Be wholeheartedly present, "
            "emotionally attuned, and devoted in tone—celebrate the relationship while "
            "remaining respectful and appropriate."
        ),
    ),
)

_MILESTONE_BY_ID: dict[str, BondMilestone] = {m.id: m for m in BOND_MILESTONES}


def get_unlocked_milestones(bond_score: int) -> list[BondMilestone]:
    """Return all milestones whose threshold is met by bond_score."""
    score = max(0, min(100, bond_score))
    return [m for m in BOND_MILESTONES if score >= m.bond_threshold]


def check_new_milestone(old_score: int, new_score: int) -> BondMilestone | None:
    """Return the milestone just crossed when bond increases, if any."""
    old = max(0, min(100, old_score))
    new = max(0, min(100, new_score))
    if new <= old:
        return None
    for milestone in BOND_MILESTONES:
        if old < milestone.bond_threshold <= new:
            return milestone
    return None


def get_milestone_by_id(milestone_id: str) -> BondMilestone | None:
    return _MILESTONE_BY_ID.get(milestone_id)


def get_milestones_for_ids(milestone_ids: list[str]) -> list[BondMilestone]:
    """Return known milestones for the given ids, ordered by bond_threshold."""
    id_set = {mid for mid in milestone_ids if mid}
    return [m for m in BOND_MILESTONES if m.id in id_set]