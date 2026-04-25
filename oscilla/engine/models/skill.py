"""Skill manifest model — learnable, activatable character abilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Literal

from pydantic import BaseModel, Field

from oscilla.engine.models.adventure import Cooldown, Effect
from oscilla.engine.models.base import Condition, ManifestEnvelope

if TYPE_CHECKING:
    from oscilla.engine.models.combat_system import DamageFormulaEntry


class SkillCost(BaseModel):
    """Resource cost paid when the skill is activated."""

    stat: str = Field(description="Stat name representing the resource pool (e.g. 'mana', 'psi').")
    amount: int = Field(ge=1, description="Amount deducted from the resource stat.")


class SkillSpec(BaseModel):
    displayName: str
    description: str = ""
    # Display/organisation category — purely informational unless skill_category_rules
    # in CharacterConfig introduce engine-side enforcement.
    category: str = ""
    # Contexts in which the skill may be activated.
    # "overworld" is a built-in context for the overworld phase.
    # Combat context strings are game-defined — a skill is available in a combat
    # system when at least one of its contexts appears in that system's skill_contexts.
    contexts: List[str] = Field(
        min_length=1,
        description="At least one context must be declared. 'overworld' is built-in; combat context strings are game-defined via CombatSystem.skill_contexts.",
    )
    # Condition gate checked before allowing activation (not just grant).
    requires: Condition | None = None
    # Resource consumed on each use.
    cost: SkillCost | None = None
    # Activation frequency limiter. Use scope: "turn" for combat resets; omit scope for adventure-scope.
    cooldown: Cooldown | None = None
    # Effects applied once on activation. Use `apply_buff` here to grant timed combat buffs.
    use_effects: List[Effect] = []
    # Per-skill damage formulas applied when this skill is used as a combat action in
    # 'choice' mode. Rendered in CombatFormulaContext; can target multiple stat namespaces.
    combat_damage_formulas: List["DamageFormulaEntry"] = []


class SkillManifest(ManifestEnvelope):
    kind: Literal["Skill"]
    spec: SkillSpec


# Resolve forward reference: DamageFormulaEntry is defined in combat_system.py.
from oscilla.engine.models.combat_system import DamageFormulaEntry as _DamageFormulaEntry  # noqa: E402

SkillSpec.model_rebuild(_types_namespace={"DamageFormulaEntry": _DamageFormulaEntry})
