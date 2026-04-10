"""Enemy manifest model."""

from typing import Dict, List, Literal

from pydantic import BaseModel, Field

from oscilla.engine.models.base import ManifestEnvelope
from oscilla.engine.models.loot_table import LootGroup  # noqa: F401 — re-exported for callers


class EnemySkillEntry(BaseModel):
    """Declares a skill the enemy knows and when to auto-use it."""

    skill_ref: str = Field(description="Skill manifest name.")
    # 0 means the skill is never triggered automatically — only by future AI logic.
    use_every_n_turns: int = Field(
        default=0,
        ge=0,
        description="Trigger the skill every N turns (starting turn 1). 0 = AI-only.",
    )


class EnemySpec(BaseModel):
    displayName: str
    description: str = ""
    hp: int = Field(ge=1)
    attack: int = Field(ge=0)
    defense: int = Field(ge=0)
    xp_reward: int = Field(ge=0)
    # Each element is an independent draw pool. Simple single-pool drops use a
    # single group with no requires and method: weighted (the defaults).
    loot: List[LootGroup] = []
    # Fixed skill list — enemies never acquire new skills.
    skills: List[EnemySkillEntry] = []
    # Initial resource values for skill costs (resource_name → starting value).
    # These are NOT persisted; reset at the start of each combat.
    skill_resources: Dict[str, int] = Field(default_factory=dict)


class EnemyManifest(ManifestEnvelope):
    kind: Literal["Enemy"]
    spec: EnemySpec
