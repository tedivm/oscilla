"""CombatContext — ephemeral state for one in-progress combat encounter.

Never serialized. Constructed at run_combat() entry from step_state and
the enemy spec; destroyed when combat ends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Literal

if TYPE_CHECKING:
    from oscilla.engine.models.adventure import Effect
    from oscilla.engine.models.buff import CombatModifier


@dataclass
class ActiveCombatEffect:
    """A timed buff/debuff currently active on a combat participant."""

    # Display name for TUI messages — set from buff_manifest.metadata.name.
    source_skill: str
    target: Literal["player", "enemy"]
    remaining_turns: int
    # Each entry is dispatched through run_effect() at the top of each round.
    per_turn_effects: List["Effect"]
    # Stable identifier copied from the buff manifest name; used by DispelEffect.
    # Empty string means this effect cannot be targeted by dispel.
    label: str = ""
    # Passive modifiers consulted by the combat loop during damage arithmetic.
    # Not dispatched as discrete effects — simply read each round.
    modifiers: List["CombatModifier"] = field(default_factory=list)


@dataclass
class CombatContext:
    """Live state for a single combat encounter.

    enemy_hp mirrors active_adventure.step_state["enemy_hp"] — the combat loop
    writes back to step_state each round for persistence, but reads from here
    for performance and clarity.
    """

    enemy_hp: int
    enemy_ref: str
    # active_effects tick down each round; entries removed when remaining_turns hits 0.
    active_effects: List[ActiveCombatEffect] = field(default_factory=list)
    # skill_ref \u2192 turn number of last use; used for turn-scope cooldown enforcement.
    skill_uses_this_combat: Dict[str, int] = field(default_factory=dict)
    # Current turn number starting at 1.
    turn_number: int = 1
    # Enemy resource pool: resource_name \u2192 current value; initialized from EnemySpec.
    enemy_resources: Dict[str, int] = field(default_factory=dict)
