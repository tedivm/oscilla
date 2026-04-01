"""Skill manifest model — learnable, activatable character abilities."""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field

from oscilla.engine.models.adventure import Effect
from oscilla.engine.models.base import Condition, ManifestEnvelope


class SkillCost(BaseModel):
    """Resource cost paid when the skill is activated."""

    stat: str = Field(description="Stat name representing the resource pool (e.g. 'mana', 'psi').")
    amount: int = Field(ge=1, description="Amount deducted from the resource stat.")


class SkillCooldown(BaseModel):
    """Prevents a skill from being used too frequently."""

    scope: Literal["turn", "adventure"] = Field(
        description="'turn' resets each combat; 'adventure' persists across adventures."
    )
    count: int = Field(ge=1, description="Turns or adventures required between uses.")


class SkillSpec(BaseModel):
    displayName: str
    description: str = ""
    # Display/organisation category — purely informational unless skill_category_rules
    # in CharacterConfig introduce engine-side enforcement.
    category: str = ""
    # Contexts in which the skill may be activated.
    contexts: List[Literal["combat", "overworld"]] = Field(
        min_length=1,
        description="At least one context must be declared.",
    )
    # Condition gate checked before allowing activation (not just grant).
    requires: Condition | None = None
    # Resource consumed on each use.
    cost: SkillCost | None = None
    # Activation frequency limiter.
    cooldown: SkillCooldown | None = None
    # Effects applied once on activation. Use `apply_buff` here to grant timed combat buffs.
    use_effects: List[Effect] = []


class SkillManifest(ManifestEnvelope):
    kind: Literal["Skill"]
    spec: SkillSpec
