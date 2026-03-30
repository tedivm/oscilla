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
class ItemInstance:
    """An individual, non-stackable item owned by the character.

    Each instance has a unique UUID so the service layer can persist it
    separately from the item manifest reference.  Per-instance modifiers
    support future enchanting / crafting systems.
    """

    instance_id: UUID
    item_ref: str
    # Per-instance stat delta applied on top of the item's equip stat_modifiers
    modifiers: Dict[str, int | float] = field(default_factory=dict)


@dataclass
class CharacterState:
    """Complete in-memory state for a single character.

    Collection fields use default_factory to prevent shared mutable defaults.
    The `stats` dict is populated from CharacterConfig at character creation —
    its values are typed narrowly (not Any) so Phase 3 JSON serialization is
    unambiguous.

    Inventory model:
    - ``stacks``: quantity-counted map for stackable items (potions, currency, etc.)
    - ``instances``: list of individual non-stackable item instances (weapons, armour, etc.)
    - ``equipment``: slot_name → instance_id for currently equipped non-stackable items
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
    # Stackable items: item_ref → quantity
    stacks: Dict[str, int] = field(default_factory=dict)
    # Non-stackable item instances
    instances: List[ItemInstance] = field(default_factory=list)
    # slot_name → instance_id (UUID) of the currently equipped item
    equipment: Dict[str, UUID] = field(default_factory=dict)
    # quest_ref → current stage name
    active_quests: Dict[str, str] = field(default_factory=dict)
    completed_quests: Set[str] = field(default_factory=set)
    active_adventure: AdventurePosition | None = None
    # Dynamic stats from CharacterConfig; int | float | bool | None (not Any).
    stats: Dict[str, int | float | bool | None] = field(default_factory=dict)

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
        initial_stats: Dict[str, int | float | bool | None] = {s.name: s.default for s in all_stats}
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

    def add_item(self, ref: str, quantity: int = 1, registry: "ContentRegistry | None" = None) -> None:
        """Add items to the character's inventory.

        If a registry is provided and the item is non-stackable, creates
        individual ItemInstance objects (one per call; quantity must be 1).
        Without a registry, or when the item is stackable, increments stacks.
        """
        item = registry.items.get(ref) if registry is not None else None
        if item is not None and not item.spec.stackable:
            if quantity != 1:
                raise ValueError(f"Cannot add {quantity}x non-stackable item {ref!r}; add one at a time")
            self.instances.append(ItemInstance(instance_id=uuid4(), item_ref=ref))
        else:
            self.stacks[ref] = self.stacks.get(ref, 0) + quantity

    def remove_item(self, ref: str, quantity: int = 1) -> None:
        """Remove stackable items from stacks. Raises ValueError if insufficient quantity."""
        current = self.stacks.get(ref, 0)
        if current < quantity:
            raise ValueError(f"Cannot remove {quantity}x {ref!r}: only {current} in stacks")
        new_qty = current - quantity
        if new_qty == 0:
            del self.stacks[ref]
        else:
            self.stacks[ref] = new_qty

    def remove_instance(self, instance_id: UUID) -> ItemInstance:
        """Remove and return a non-stackable item instance by its UUID.

        Also unequips the instance from any slots that reference it.
        Raises ValueError if the instance is not found.
        """
        for i, inst in enumerate(self.instances):
            if inst.instance_id == instance_id:
                self.instances.pop(i)
                # Unequip from any slots referencing this instance
                for slot in [s for s, iid in self.equipment.items() if iid == instance_id]:
                    del self.equipment[slot]
                return inst
        raise ValueError(f"Instance {instance_id} not found in instances list")

    # --- Equipment ---

    def check_displacement(self, instance_id: UUID, slots: List[str]) -> List[UUID]:
        """Return instance_ids that would be displaced by equipping to the given slots."""
        displaced: List[UUID] = []
        for slot in slots:
            current = self.equipment.get(slot)
            if current is not None and current != instance_id and current not in displaced:
                displaced.append(current)
        return displaced

    def equip_instance(self, instance_id: UUID, slots: List[str]) -> List[ItemInstance]:
        """Equip a non-stackable item instance into the given slot(s).

        Any instance already occupying a slot is unequipped from all its slots
        (an item can occupy multiple slots, e.g. two-handed weapons).

        Returns the list of displaced instances that were unequipped.
        Raises ValueError if the instance_id is not found in self.instances.
        """
        if not any(inst.instance_id == instance_id for inst in self.instances):
            raise ValueError(f"Instance {instance_id} not found in instances list")

        displaced_ids = self.check_displacement(instance_id=instance_id, slots=slots)
        displaced: List[ItemInstance] = []
        for displaced_id in displaced_ids:
            # Remove displaced instance from all slots
            for slot in [s for s, iid in self.equipment.items() if iid == displaced_id]:
                del self.equipment[slot]
            displaced_inst = next((inst for inst in self.instances if inst.instance_id == displaced_id), None)
            if displaced_inst is not None:
                displaced.append(displaced_inst)

        for slot in slots:
            self.equipment[slot] = instance_id
        return displaced

    def unequip_slot(self, slot: str) -> ItemInstance | None:
        """Remove the equipped item from slot. Returns the instance, or None if empty."""
        instance_id = self.equipment.pop(slot, None)
        if instance_id is None:
            return None
        # Also remove this instance_id from any other slots (multi-slot items)
        for s in [s for s, iid in self.equipment.items() if iid == instance_id]:
            del self.equipment[s]
        return next((inst for inst in self.instances if inst.instance_id == instance_id), None)

    # --- Stat computation ---

    def effective_stats(self, registry: "ContentRegistry | None" = None) -> Dict[str, int | float | bool | None]:
        """Return base stats augmented by equipped item stat_modifiers.

        Iterates over unique equipped instance_ids, looks up each item's equip
        spec, and accumulates stat_modifiers.  Per-instance modifiers from
        ItemInstance.modifiers are also applied.  Non-numeric stats are not
        modified by equipment.
        """
        result: Dict[str, int | float | bool | None] = dict(self.stats)
        if registry is None:
            return result

        applied: Set[UUID] = set()
        for instance_id in self.equipment.values():
            if instance_id in applied:
                continue
            applied.add(instance_id)

            instance = next((inst for inst in self.instances if inst.instance_id == instance_id), None)
            if instance is None:
                continue

            item = registry.items.get(instance.item_ref)
            if item is not None and item.spec.equip is not None:
                for modifier in item.spec.equip.stat_modifiers:
                    current = result.get(modifier.stat, 0)
                    if isinstance(current, (int, float)):
                        result[modifier.stat] = current + modifier.amount

            # Apply per-instance modifiers on top
            for stat, amount in instance.modifiers.items():
                current = result.get(stat, 0)
                if isinstance(current, (int, float)):
                    result[stat] = current + amount

        return result

    # --- Milestones ---

    def grant_milestone(self, name: str) -> None:
        """Add a milestone flag. No-op if already held."""
        self.milestones.add(name)

    def has_milestone(self, name: str) -> bool:
        return name in self.milestones

    # --- XP / levelling ---

    def add_xp(self, amount: int, xp_thresholds: List[int], hp_per_level: int) -> tuple[List[int], List[int]]:
        """Add or subtract XP and auto-level-up or level-down.

        xp_thresholds[i] is the cumulative XP required to reach level i+2
        (index 0 = XP to reach level 2). hp_per_level is added to max_hp
        for each level gained, or subtracted for each level lost.

        For negative XP, supports level-down to level 1 (minimum) and XP floor at 0.
        HP is capped at the new max_hp after level changes.

        Returns tuple of (levels_gained, levels_lost) as lists of actual level numbers.
        """
        self.xp += amount
        # Floor XP at 0
        if self.xp < 0:
            self.xp = 0

        levels_gained: List[int] = []
        levels_lost: List[int] = []

        # Handle level-up (positive XP)
        while self.level - 1 < len(xp_thresholds) and self.xp >= xp_thresholds[self.level - 1]:
            self.level += 1
            self.max_hp += hp_per_level
            levels_gained.append(self.level)

        # Handle level-down (negative XP or low remaining XP)
        while self.level > 1:
            # Check if current level is sustainable
            required_xp_for_current = xp_thresholds[self.level - 2] if self.level >= 2 else 0
            if self.xp >= required_xp_for_current:
                break  # Can sustain current level

            # Must de-level
            old_level = self.level
            self.level -= 1
            self.max_hp -= hp_per_level
            levels_lost.append(old_level)

        # Cap current HP at new max HP
        if self.hp > self.max_hp:
            self.hp = self.max_hp

        return (levels_gained, levels_lost)

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
            "stacks": dict(self.stacks),
            "instances": [
                {
                    "instance_id": str(inst.instance_id),
                    "item_ref": inst.item_ref,
                    "modifiers": dict(inst.modifiers),
                }
                for inst in self.instances
            ],
            "equipment": {slot: str(iid) for slot, iid in self.equipment.items()},
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
        _type_map = {"int": int, "float": float, "bool": bool}

        saved_stats: Dict[str, int | float | bool | None] = data.get("stats", {})
        reconciled_stats: Dict[str, int | float | bool | None] = {}

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

        # Deserialize instances
        raw_instances: List[Dict[str, Any]] = data.get("instances", [])
        instances: List[ItemInstance] = [
            ItemInstance(
                instance_id=UUID(inst["instance_id"]),
                item_ref=inst["item_ref"],
                modifiers=dict(inst.get("modifiers", {})),
            )
            for inst in raw_instances
        ]

        # Deserialize equipment: slot → UUID string in the dict
        raw_equipment: Dict[str, str] = data.get("equipment", {})
        equipment: Dict[str, UUID] = {slot: UUID(iid_str) for slot, iid_str in raw_equipment.items()}

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
            stacks=dict(data.get("stacks", {})),
            instances=instances,
            equipment=equipment,
            active_quests=dict(data.get("active_quests", {})),
            completed_quests=set(data.get("completed_quests", [])),
            stats=reconciled_stats,
            statistics=statistics,
            active_adventure=active_adventure,
        )
