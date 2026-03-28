"""In-memory player state representation.

PlayerState and its nested types are plain dataclasses — no ORM and no Pydantic.
Pydantic validates manifests at the content boundary; once data is in the engine
it is trusted internal state and plain dataclasses keep mutation straightforward.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Set
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from oscilla.engine.models.character_config import CharacterConfigManifest
    from oscilla.engine.models.game import GameManifest


@dataclass
class AdventurePosition:
    """Tracks which step of an in-progress adventure the player is currently on."""

    adventure_ref: str
    step_index: int
    # mid-step scratch space — e.g. enemy HP persisted between combat rounds
    step_state: Dict[str, int | float | str | bool | None] = field(default_factory=dict)


@dataclass
class PlayerStatistics:
    """Per-entity event counters that record how many times a player has
    interacted with a specific named entity. Missing keys are implicitly 0.
    """

    enemies_defeated: Dict[str, int] = field(default_factory=dict)
    locations_visited: Dict[str, int] = field(default_factory=dict)
    adventures_completed: Dict[str, int] = field(default_factory=dict)

    def _increment(self, mapping: Dict[str, int], key: str) -> None:
        mapping[key] = mapping.get(key, 0) + 1

    def record_enemy_defeated(self, enemy_ref: str) -> None:
        self._increment(self.enemies_defeated, enemy_ref)

    def record_location_visited(self, location_ref: str) -> None:
        self._increment(self.locations_visited, location_ref)

    def record_adventure_completed(self, adventure_ref: str) -> None:
        self._increment(self.adventures_completed, adventure_ref)


@dataclass
class PlayerState:
    """Complete in-memory state for a single player character.

    Collection fields use default_factory to prevent shared mutable defaults.
    The `stats` dict is populated from CharacterConfig at character creation —
    its values are typed narrowly (not Any) so Phase 3 JSON serialization is
    unambiguous.
    """

    player_id: UUID
    name: str
    character_class: str | None
    level: int
    xp: int
    hp: int
    max_hp: int
    prestige_count: int
    current_location: str | None
    milestones: Set[str] = field(default_factory=set)
    statistics: PlayerStatistics = field(default_factory=PlayerStatistics)
    inventory: Dict[str, int] = field(default_factory=dict)
    # slot_name → item_ref
    equipment: Dict[str, str] = field(default_factory=dict)
    # quest_ref → current stage name
    active_quests: Dict[str, str] = field(default_factory=dict)
    completed_quests: Set[str] = field(default_factory=set)
    active_adventure: AdventurePosition | None = None
    # Dynamic stats from CharacterConfig; int | float | str | bool | None (not Any).
    stats: Dict[str, int | float | str | bool | None] = field(default_factory=dict)

    # --- Factory ---

    @classmethod
    def new_player(
        cls,
        name: str,
        game_manifest: "GameManifest",
        character_config: "CharacterConfigManifest",
    ) -> "PlayerState":
        """Create a fresh level-1 player with defaults from game + character config.

        Stats are populated from all public and hidden stats in CharacterConfig.
        HP and max_hp are set from the game manifest's hp_formula.base_hp.
        All collection fields start empty.
        """
        all_stats = character_config.spec.public_stats + character_config.spec.hidden_stats
        initial_stats: Dict[str, int | float | str | bool | None] = {s.name: s.default for s in all_stats}
        base_hp = game_manifest.spec.hp_formula.base_hp
        return cls(
            player_id=uuid4(),
            name=name,
            character_class=None,
            level=1,
            xp=0,
            hp=base_hp,
            max_hp=base_hp,
            prestige_count=0,
            current_location=None,
            stats=initial_stats,
        )

    # --- Inventory ---

    def add_item(self, ref: str, quantity: int = 1) -> None:
        self.inventory[ref] = self.inventory.get(ref, 0) + quantity

    def remove_item(self, ref: str, quantity: int = 1) -> None:
        current = self.inventory.get(ref, 0)
        if current < quantity:
            raise ValueError(f"Cannot remove {quantity}x {ref!r}: only {current} in inventory")
        new_qty = current - quantity
        if new_qty == 0:
            del self.inventory[ref]
        else:
            self.inventory[ref] = new_qty

    # --- Milestones ---

    def grant_milestone(self, name: str) -> None:
        """Add a milestone flag. No-op if already held."""
        self.milestones.add(name)

    def has_milestone(self, name: str) -> bool:
        return name in self.milestones

    # --- XP / levelling ---

    def add_xp(self, amount: int, xp_thresholds: List[int], hp_per_level: int) -> List[int]:
        """Add XP and auto-level-up.

        xp_thresholds[i] is the cumulative XP required to reach level i+2
        (index 0 = XP to reach level 2). hp_per_level is added to max_hp
        for each level gained.

        Returns the list of new level numbers reached (empty if none).
        """
        self.xp += amount
        levels_gained: List[int] = []
        while self.level - 1 < len(xp_thresholds) and self.xp >= xp_thresholds[self.level - 1]:
            self.level += 1
            self.max_hp += hp_per_level
            levels_gained.append(self.level)
        return levels_gained

    # --- Equipment ---

    def equip(self, item_ref: str, slot: str) -> None:
        """Move item_ref from inventory into the given equipment slot.

        Any item already in the slot is returned to inventory. Raises
        ValueError if item_ref is not in inventory.
        """
        if self.inventory.get(item_ref, 0) == 0:
            raise ValueError(f"Cannot equip {item_ref!r}: not in inventory")
        displaced = self.equipment.get(slot)
        if displaced:
            self.add_item(displaced)
        self.remove_item(item_ref)
        self.equipment[slot] = item_ref
