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

from oscilla.engine.templates import DEFAULT_PRONOUN_SET, PRONOUN_SETS, PronounSet

if TYPE_CHECKING:
    from oscilla.engine.models.character_config import CharacterConfigManifest
    from oscilla.engine.models.game import GameManifest
    from oscilla.engine.registry import ContentRegistry

logger = getLogger(__name__)

# Hard INT64 floor/ceiling used as an absolute backstop in set_stat().
# Bounds from StatDefinition are enforced in the effect handlers before this point.
_INT64_MIN: int = -(2**63)
_INT64_MAX: int = (2**63) - 1


def _deserialize_pronoun_set(key: str) -> PronounSet:
    """Return the PronounSet for key, falling back to they_them for unknown keys."""
    ps = PRONOUN_SETS.get(key)
    if ps is None:
        logger.warning(
            "Unknown pronoun_set key %r in saved CharacterState — defaulting to 'they_them'.",
            key,
        )
        return DEFAULT_PRONOUN_SET
    return ps


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
    # Remaining uses before auto-removal; None means unlimited (or consumed_on_use controls removal).
    charges_remaining: int | None = None


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
    # Player's chosen pronoun set. Defaults to they/them until explicitly set.
    pronouns: PronounSet = field(default_factory=lambda: DEFAULT_PRONOUN_SET)
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
    # Dynamic stats from CharacterConfig; int | bool | None (not Any).
    stats: Dict[str, int | bool | None] = field(default_factory=dict)
    # Skill refs permanently learned by the player.
    known_skills: Set[str] = field(default_factory=set)
    # Adventure-scope cooldowns: skill_ref → adventures remaining before reuse.
    # Decremented at adventure start; removed when value reaches 0.
    skill_cooldowns: Dict[str, int] = field(default_factory=dict)

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
        initial_stats: Dict[str, int | bool | None] = {s.name: s.default for s in all_stats}
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

    # --- Stat mutation ---

    def set_stat(self, name: str, value: int) -> None:
        """Set an integer stat, clamping to INT64 range as an absolute backstop.

        Effect handlers should clamp to StatBounds before calling this method.
        This backstop prevents silent integer overflow from reaching the DB.
        """
        clamped = max(_INT64_MIN, min(_INT64_MAX, value))
        if clamped != value:
            logger.warning(
                "set_stat(%r): value %d clamped to INT64 range %d.",
                name,
                value,
                clamped,
            )
        self.stats[name] = clamped

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
            charges_remaining = item.spec.charges
            self.instances.append(ItemInstance(instance_id=uuid4(), item_ref=ref, charges_remaining=charges_remaining))
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

    def effective_stats(
        self,
        registry: "ContentRegistry | None" = None,
        exclude_item: str | None = None,
    ) -> Dict[str, int | bool | None]:
        """Return base stats augmented by equipped item stat_modifiers and passive effects.

        Iterates over unique equipped instance_ids, looks up each item's equip
        spec, and accumulates stat_modifiers.  Per-instance modifiers from
        ItemInstance.modifiers are also applied.  Non-numeric stats are not
        modified by equipment.

        When exclude_item is set, the named item's stat contributions are skipped.
        This prevents an item from satisfying its own equip requirements
        (the self-justification guard).
        """
        result: Dict[str, int | bool | None] = dict(self.stats)
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

            # Skip the excluded item's stat contributions (self-justification guard).
            if instance.item_ref == exclude_item:
                continue

            item = registry.items.get(instance.item_ref)
            if item is not None and item.spec.equip is not None:
                for modifier in item.spec.equip.stat_modifiers:
                    current = result.get(modifier.stat, 0)
                    if isinstance(current, int) and not isinstance(current, bool):
                        result[modifier.stat] = int(current + modifier.amount)

            # Apply per-instance modifiers on top
            for stat, amount in instance.modifiers.items():
                current = result.get(stat, 0)
                if isinstance(current, int) and not isinstance(current, bool):
                    result[stat] = int(current + amount)

        # Apply passive effects from the game manifest.
        if registry.game is not None:
            from oscilla.engine.conditions import evaluate

            for passive in registry.game.spec.passive_effects:
                # Passive effects are evaluated without registry to avoid recursion.
                if evaluate(condition=passive.condition, player=self, registry=None):
                    for modifier in passive.stat_modifiers:
                        current = result.get(modifier.stat, 0)
                        if isinstance(current, int) and not isinstance(current, bool):
                            result[modifier.stat] = int(current + modifier.amount)

        return result

    # --- Milestones ---

    def grant_milestone(self, name: str) -> None:
        """Add a milestone flag. No-op if already held."""
        self.milestones.add(name)

    def has_milestone(self, name: str) -> bool:
        return name in self.milestones

    # --- Skills ---

    def available_skills(self, registry: "ContentRegistry | None" = None) -> Set[str]:
        """Return the full set of skill refs the player can currently activate.

        Combines:
        1. Permanently learned skills (known_skills).
        2. Skills granted by currently equipped item instances (grants_skills_equipped).
        3. Skills granted by any held item — stacks or instances (grants_skills_held).

        Requires registry to resolve item specs. Without a registry only known_skills
        is returned, which is correct for context where items cannot be looked up.
        """
        result: Set[str] = set(self.known_skills)
        if registry is None:
            return result

        # Equipped-item skills: only items actually in an equipment slot.
        equipped_refs: Set[str] = {
            inst.item_ref for inst in self.instances if inst.instance_id in self.equipment.values()
        }
        for item_ref in equipped_refs:
            item = registry.items.get(item_ref)
            if item is not None:
                result.update(item.spec.grants_skills_equipped)

        # Held-item skills: any item in stacks or instances (equipped or not).
        for item_ref in self.stacks:
            item = registry.items.get(item_ref)
            if item is not None:
                result.update(item.spec.grants_skills_held)
        for inst in self.instances:
            item = registry.items.get(inst.item_ref)
            if item is not None:
                result.update(item.spec.grants_skills_held)

        # Passive effect skill grants from the game manifest.
        if registry.game is not None:
            from oscilla.engine.conditions import evaluate

            for passive in registry.game.spec.passive_effects:
                # Passive conditions evaluated without registry to avoid recursion.
                if evaluate(condition=passive.condition, player=self, registry=None):
                    result.update(passive.skill_grants)

        return result

    def grant_skill(self, skill_ref: str, registry: "ContentRegistry | None" = None) -> bool:
        """Attempt to grant the player a skill. Returns True if the skill was newly learned.

        Enforces SkillCategoryRule restrictions (max_known, exclusive_with) when
        a registry with CharacterConfig is provided. If a rule blocks the grant,
        logs a warning and returns False without mutating state.

        Already-known skills are a no-op (returns False).
        """
        if skill_ref in self.known_skills:
            return False

        if registry is not None and registry.character_config is not None:
            skill = registry.skills.get(skill_ref)
            if skill is not None:
                category = skill.spec.category
                rules = {r.category: r for r in registry.character_config.spec.skill_category_rules}
                rule = rules.get(category)
                if rule is not None:
                    # Check exclusive_with: if the player already knows any skill from
                    # an exclusive category, block the grant.
                    for excl_cat in rule.exclusive_with:
                        for known in self.known_skills:
                            known_skill = registry.skills.get(known)
                            if known_skill is not None and known_skill.spec.category == excl_cat:
                                logger.warning(
                                    "grant_skill(%r) blocked: category %r is exclusive with %r "
                                    "and player already knows a %r skill.",
                                    skill_ref,
                                    category,
                                    excl_cat,
                                    excl_cat,
                                )
                                return False
                    # Check max_known: count existing skills in this category.
                    if rule.max_known is not None:
                        count = sum(
                            1
                            for known in self.known_skills
                            if (s := registry.skills.get(known)) is not None and s.spec.category == category
                        )
                        if count >= rule.max_known:
                            logger.warning(
                                "grant_skill(%r) blocked: category %r already has %d/%d skills.",
                                skill_ref,
                                category,
                                count,
                                rule.max_known,
                            )
                            return False

        self.known_skills.add(skill_ref)
        return True

    def tick_skill_cooldowns(self) -> None:
        """Decrement adventure-scoped cooldowns by one. Called at the start of each adventure.

        Removes entries that reach 0 so that skill_cooldowns only contains active cooldowns.
        """
        spent: List[str] = []
        for skill_ref, remaining in self.skill_cooldowns.items():
            new_val = remaining - 1
            if new_val <= 0:
                spent.append(skill_ref)
            else:
                self.skill_cooldowns[skill_ref] = new_val
        for skill_ref in spent:
            del self.skill_cooldowns[skill_ref]

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
            "pronoun_set": next(
                (k for k, v in PRONOUN_SETS.items() if v == self.pronouns),
                "they_them",  # fallback if using a custom set not in the built-in registry
            ),
            "milestones": sorted(self.milestones),
            "stacks": dict(self.stacks),
            "instances": [
                {
                    "instance_id": str(inst.instance_id),
                    "item_ref": inst.item_ref,
                    "modifiers": dict(inst.modifiers),
                    "charges_remaining": inst.charges_remaining,
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
            "known_skills": sorted(self.known_skills),
            "skill_cooldowns": dict(self.skill_cooldowns),
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
        _type_map = {"int": int, "bool": bool}

        saved_stats: Dict[str, int | bool | None] = data.get("stats", {})
        reconciled_stats: Dict[str, int | bool | None] = {}

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
                charges_remaining=inst.get("charges_remaining"),
            )
            for inst in raw_instances
        ]

        # Deserialize equipment: slot → UUID string in the dict
        raw_equipment: Dict[str, str] = data.get("equipment", {})
        equipment: Dict[str, UUID] = {slot: UUID(iid_str) for slot, iid_str in raw_equipment.items()}

        result = cls(
            character_id=UUID(data["character_id"]),
            iteration=data["iteration"],
            name=data["name"],
            character_class=data.get("character_class"),
            level=data["level"],
            xp=data["xp"],
            hp=data["hp"],
            max_hp=data["max_hp"],
            current_location=data.get("current_location"),
            pronouns=_deserialize_pronoun_set(data.get("pronoun_set", "they_them")),
            milestones=set(data.get("milestones", [])),
            stacks=dict(data.get("stacks", {})),
            instances=instances,
            equipment=equipment,
            active_quests=dict(data.get("active_quests", {})),
            completed_quests=set(data.get("completed_quests", [])),
            stats=reconciled_stats,
            statistics=statistics,
            active_adventure=active_adventure,
            known_skills=set(data.get("known_skills", [])),
            skill_cooldowns=dict(data.get("skill_cooldowns", {})),
        )

        # Warn about equipped items whose requires condition is no longer satisfied.
        # The items remain equipped — do not cascade at load time.
        if registry is not None:
            from oscilla.engine.conditions import evaluate

            equipped_ids = set(result.equipment.values())
            for inst in result.instances:
                if inst.instance_id not in equipped_ids:
                    continue
                item_mf = registry.items.get(inst.item_ref)
                if item_mf is None or item_mf.spec.equip is None:
                    continue
                req = item_mf.spec.equip.requires
                if req is None:
                    continue
                if not evaluate(condition=req, player=result, registry=registry, exclude_item=inst.item_ref):
                    logger.warning(
                        "Equipped item %r no longer meets its requires condition at session load — "
                        "item remains equipped (manual unequip required).",
                        inst.item_ref,
                    )

        return result


def validate_equipped_requires(
    player: "CharacterState",
    registry: "ContentRegistry",
) -> List[str]:
    """Return item_ref strings for equipped items whose `requires` is no longer satisfied.

    Each item's `requires` is evaluated with `exclude_item=item_ref` to strip its
    own stat bonuses from the check (self-justification guard).
    """
    from oscilla.engine.conditions import evaluate

    failing: List[str] = []
    equipped_ids = set(player.equipment.values())
    for inst in player.instances:
        if inst.instance_id not in equipped_ids:
            continue
        item_mf = registry.items.get(inst.item_ref)
        if item_mf is None or item_mf.spec.equip is None:
            continue
        req = item_mf.spec.equip.requires
        if req is None:
            continue
        if not evaluate(condition=req, player=player, registry=registry, exclude_item=inst.item_ref):
            failing.append(inst.item_ref)
    return failing


def cascade_unequip_invalid(
    player: "CharacterState",
    registry: "ContentRegistry",
) -> List[str]:
    """Unequip all items whose `requires` is no longer satisfied, repeating until stable.

    Runs in a fixed-point loop so that unequipping one item that enabled another
    item's requirement will also unequip the dependent item.

    Returns the display names of all unequipped items for TUI notification.
    """
    unequipped_names: List[str] = []
    while True:
        failing_refs = validate_equipped_requires(player=player, registry=registry)
        if not failing_refs:
            break
        for item_ref in failing_refs:
            # Find the instance and unequip it from all its slots.
            for slot in [s for s, iid in player.equipment.items()]:
                inst = player.instances
                equipped_inst = next(
                    (i for i in inst if i.instance_id == player.equipment.get(slot) and i.item_ref == item_ref),
                    None,
                )
                if equipped_inst is not None:
                    player.unequip_slot(slot)
                    item_mf = registry.items.get(item_ref)
                    name = item_mf.spec.displayName if item_mf is not None else item_ref
                    if name not in unequipped_names:
                        unequipped_names.append(name)
    return unequipped_names
