"""In-memory character state representation.

CharacterState and its nested types are plain dataclasses — no ORM and no Pydantic.
Pydantic validates manifests at the content boundary; once data is in the engine
it is trusted internal state and plain dataclasses keep mutation straightforward.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from logging import getLogger
from typing import TYPE_CHECKING, Any, Dict, List, Set
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from oscilla.engine.models.character_config import CharacterConfigManifest
    from oscilla.engine.models.game import GameManifest
    from oscilla.engine.registry import ContentRegistry

logger = getLogger(__name__)


@dataclass
class AdventurePosition:
    """Tracks which step of an in-progress adventure the player is currently on."""

    adventure_ref: str
    step_index: int
    # mid-step scratch space — e.g. enemy HP persisted between combat rounds
    step_state: Dict[str, int | float | str | bool | None] = field(default_factory=dict)


@dataclass
class CharacterStatistics:
    """Per-entity event counters that record how many times a character has
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
class CharacterState:
    """Complete in-memory state for a single character.

    Collection fields use default_factory to prevent shared mutable defaults.
    The `stats` dict is populated from CharacterConfig at character creation —
    its values are typed narrowly (not Any) so Phase 3 JSON serialization is
    unambiguous.
    """

    character_id: UUID
    name: str
    character_class: str | None
    level: int
    xp: int
    hp: int
    max_hp: int
    # 0-based prestige run number; maps to character_iterations.iteration
    iteration: int
    current_location: str | None
    milestones: Set[str] = field(default_factory=set)
    statistics: CharacterStatistics = field(default_factory=CharacterStatistics)
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
    def new_character(
        cls,
        name: str,
        game_manifest: "GameManifest",
        character_config: "CharacterConfigManifest",
    ) -> "CharacterState":
        """Create a fresh level-1 character with defaults from game + character config.

        Stats are populated from all public and hidden stats in CharacterConfig.
        HP and max_hp are set from the game manifest's hp_formula.base_hp.
        All collection fields start empty.
        """
        all_stats = character_config.spec.public_stats + character_config.spec.hidden_stats
        initial_stats: Dict[str, int | float | str | bool | None] = {s.name: s.default for s in all_stats}
        base_hp = game_manifest.spec.hp_formula.base_hp
        return cls(
            character_id=uuid4(),
            name=name,
            character_class=None,
            level=1,
            xp=0,
            hp=base_hp,
            max_hp=base_hp,
            iteration=0,
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

    # --- Serialization ---

    def to_dict(self) -> Dict[str, Any]:
        """Serialize CharacterState to a JSON-native dict.

        UUIDs are converted to strings, sets to sorted lists, and nested
        dataclasses to dicts. The result is passable to json.dumps() without
        further transformation.
        """
        active_adventure: Dict[str, Any] | None = None
        if self.active_adventure is not None:
            active_adventure = {
                "adventure_ref": self.active_adventure.adventure_ref,
                "step_index": self.active_adventure.step_index,
                "step_state": dict(self.active_adventure.step_state),
            }
        return {
            "character_id": str(self.character_id),
            "iteration": self.iteration,
            "name": self.name,
            "character_class": self.character_class,
            "level": self.level,
            "xp": self.xp,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "current_location": self.current_location,
            "milestones": sorted(self.milestones),
            "inventory": dict(self.inventory),
            "equipment": dict(self.equipment),
            "active_quests": dict(self.active_quests),
            "completed_quests": sorted(self.completed_quests),
            "stats": dict(self.stats),
            "statistics": {
                "enemies_defeated": dict(self.statistics.enemies_defeated),
                "locations_visited": dict(self.statistics.locations_visited),
                "adventures_completed": dict(self.statistics.adventures_completed),
            },
            "active_adventure": active_adventure,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        character_config: "CharacterConfigManifest",
        registry: "ContentRegistry | None" = None,
    ) -> "CharacterState":
        """Reconstruct CharacterState from a serialized dict with content-drift resilience.

        Stat reconciliation against the current CharacterConfig:
        - Stats present in config but absent in data → added with their default value from config.
        - Stats present in data but absent from config → dropped; WARNING logged per removed key.

        Adventure ref validation (only when registry is provided):
        - If active_adventure.adventure_ref is not in the registry →
          active_adventure is set to None and WARNING is logged.

        Numeric type fidelity: each stat value is cast to the type declared in
        CharacterConfig (e.g. int(v) for type="int" stats) so equality checks
        remain correct after a DB round-trip (SQLite returns float for REAL columns).
        """
        all_stats = character_config.spec.public_stats + character_config.spec.hidden_stats
        stat_defs = {s.name: s for s in all_stats}
        _type_map = {"int": int, "float": float, "str": str, "bool": bool}

        saved_stats: Dict[str, int | float | str | bool | None] = data.get("stats", {})
        reconciled_stats: Dict[str, int | float | str | bool | None] = {}

        # Inject defaults for stats in config but missing from save
        for stat_name, stat_def in stat_defs.items():
            if stat_name not in saved_stats:
                reconciled_stats[stat_name] = stat_def.default
            else:
                raw_value = saved_stats[stat_name]
                if raw_value is not None:
                    cast_fn = _type_map.get(stat_def.type)
                    reconciled_stats[stat_name] = cast_fn(raw_value) if cast_fn else raw_value
                else:
                    reconciled_stats[stat_name] = None

        # Log and drop stats in save but not in current config
        for stat_name in saved_stats:
            if stat_name not in stat_defs:
                logger.warning(
                    "Dropping unknown stat %r from loaded CharacterState — "
                    "stat may have been removed from the content package.",
                    stat_name,
                )

        # Deserialize active_adventure
        raw_adventure = data.get("active_adventure")
        active_adventure: AdventurePosition | None = None
        if raw_adventure is not None:
            adventure_ref: str = raw_adventure["adventure_ref"]
            if registry is not None and adventure_ref not in registry.adventures:
                logger.warning(
                    "Clearing active_adventure %r from loaded CharacterState — "
                    "adventure ref not found in the current content registry.",
                    adventure_ref,
                )
            else:
                active_adventure = AdventurePosition(
                    adventure_ref=adventure_ref,
                    step_index=raw_adventure["step_index"],
                    step_state=raw_adventure.get("step_state", {}),
                )

        raw_stats = data.get("statistics", {})
        statistics = CharacterStatistics(
            enemies_defeated=dict(raw_stats.get("enemies_defeated", {})),
            locations_visited=dict(raw_stats.get("locations_visited", {})),
            adventures_completed=dict(raw_stats.get("adventures_completed", {})),
        )

        return cls(
            character_id=UUID(data["character_id"]),
            iteration=data["iteration"],
            name=data["name"],
            character_class=data.get("character_class"),
            level=data["level"],
            xp=data["xp"],
            hp=data["hp"],
            max_hp=data["max_hp"],
            current_location=data.get("current_location"),
            milestones=set(data.get("milestones", [])),
            inventory=dict(data.get("inventory", {})),
            equipment=dict(data.get("equipment", {})),
            active_quests=dict(data.get("active_quests", {})),
            completed_quests=set(data.get("completed_quests", [])),
            stats=reconciled_stats,
            statistics=statistics,
            active_adventure=active_adventure,
        )
