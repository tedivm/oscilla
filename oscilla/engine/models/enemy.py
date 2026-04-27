"""Enemy manifest model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Literal

from pydantic import BaseModel, Field

from oscilla.engine.models.base import BaseSpec, ManifestEnvelope
from oscilla.engine.models.loot_table import LootGroup  # noqa: F401 — re-exported for callers

if TYPE_CHECKING:
    from oscilla.engine.models.adventure import Effect


class EnemySkillEntry(BaseModel):
    """Declares a skill the enemy knows and when to auto-use it."""

    skill_ref: str = Field(description="Skill manifest name.")
    # 0 means the skill is never triggered automatically — only by future AI logic.
    use_every_n_turns: int = Field(
        default=0,
        ge=0,
        description="Trigger the skill every N turns (starting turn 1). 0 = AI-only.",
    )


class EnemySpec(BaseSpec):
    """Enemy combat stats and behavior.

    Stats are declared as a free-form dict keyed by stat name. The stat names
    that must be present are determined by the resolved CombatSystem manifest.
    Defeat conditions and damage formulas in the CombatSystem reference these
    keys by name.

    on_defeat_effects fires when the enemy is defeated, before loot and the
    on_win branch execute. Use it for XP grants, milestone grants, or any
    other reward effects.
    """

    displayName: str
    description: str = ""
    # Free-form dict of stat name → initial integer value. Must include every
    # stat key referenced by target_stat in the resolved CombatSystem's
    # player_damage_formulas and enemy_damage_formulas.
    stats: Dict[str, int] = Field(
        default_factory=dict,
        description="Combat stat values. Keys must match the CombatSystem's formula target_stat references.",
    )
    # Effects fired when this enemy is defeated (before loot/on_win branch).
    on_defeat_effects: List["Effect"] = []
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


# Resolve forward reference: Effect is defined in adventure.py.
from oscilla.engine.models.adventure import Effect as _Effect  # noqa: E402

EnemySpec.model_rebuild(_types_namespace={"Effect": _Effect})
