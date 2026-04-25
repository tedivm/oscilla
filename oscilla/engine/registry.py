"""Content registry — typed in-memory store for all loaded manifests."""

from typing import TYPE_CHECKING, Dict, Generic, Iterator, List, Type, TypeVar, cast

from oscilla.engine.models.adventure import AdventureManifest
from oscilla.engine.models.archetype import ArchetypeManifest
from oscilla.engine.models.base import ManifestEnvelope
from oscilla.engine.models.buff import BuffManifest
from oscilla.engine.models.character_config import CharacterConfigManifest
from oscilla.engine.models.combat_system import CombatSystemManifest
from oscilla.engine.models.custom_condition import CustomConditionManifest
from oscilla.engine.models.enemy import EnemyManifest
from oscilla.engine.models.game import GameManifest
from oscilla.engine.models.item import ItemManifest
from oscilla.engine.models.location import LocationManifest
from oscilla.engine.models.loot_table import LootGroup, LootTableManifest
from oscilla.engine.models.quest import QuestManifest
from oscilla.engine.models.recipe import RecipeManifest
from oscilla.engine.models.region import RegionManifest
from oscilla.engine.models.skill import SkillManifest

if TYPE_CHECKING:
    from oscilla.engine.ingame_time import InGameTimeResolver
    from oscilla.engine.models.character_config import StatDefinition
    from oscilla.engine.templates import GameTemplateEngine

T = TypeVar("T", bound=ManifestEnvelope)


class KindRegistry(Generic[T]):
    """Typed in-memory store for one manifest kind."""

    def __init__(self) -> None:
        self._store: Dict[str, T] = {}

    def register(self, manifest: T) -> None:
        self._store[manifest.metadata.name] = manifest

    def get(self, name: str) -> T | None:
        return self._store.get(name)

    def require(self, name: str, kind: str) -> T:
        """Fetch by name, raising a clear error if missing."""
        obj = self._store.get(name)
        if obj is None:
            raise KeyError(f"No {kind} named {name!r} in registry")
        return obj

    def all(self) -> Iterator[T]:
        return iter(self._store.values())

    def names(self) -> List[str]:
        return list(self._store.keys())

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, name: object) -> bool:
        return name in self._store


class ContentRegistry:
    """Aggregated read-only store of all loaded manifests, one KindRegistry per kind."""

    def __init__(self) -> None:
        self.regions: KindRegistry[RegionManifest] = KindRegistry()
        self.locations: KindRegistry[LocationManifest] = KindRegistry()
        self.adventures: KindRegistry[AdventureManifest] = KindRegistry()
        self.archetypes: KindRegistry[ArchetypeManifest] = KindRegistry()
        self.enemies: KindRegistry[EnemyManifest] = KindRegistry()
        self.items: KindRegistry[ItemManifest] = KindRegistry()
        self.loot_tables: KindRegistry[LootTableManifest] = KindRegistry()
        self.recipes: KindRegistry[RecipeManifest] = KindRegistry()
        self.quests: KindRegistry[QuestManifest] = KindRegistry()
        self.buffs: KindRegistry[BuffManifest] = KindRegistry()
        self.skills: KindRegistry[SkillManifest] = KindRegistry()
        self.custom_conditions: KindRegistry[CustomConditionManifest] = KindRegistry()
        self.combat_systems: KindRegistry[CombatSystemManifest] = KindRegistry()
        self.game: GameManifest | None = None
        self.character_config: CharacterConfigManifest | None = None
        # Holds precompiled templates; populated by loader.py after validation.
        self.template_engine: "GameTemplateEngine | None" = None
        # InGameTimeResolver is built once after game manifest is registered.
        # None when time system is not configured.
        self._ingame_time_resolver: "InGameTimeResolver | None" = None
        # Built by loader.py after all manifests are registered.
        # trigger_name → ordered list of adventure refs from trigger_adventures.
        self.trigger_index: Dict[str, List[str]] = {}
        # stat_name → sorted list of (threshold_value, trigger_name) pairs.
        self.stat_threshold_index: Dict[str, List[tuple[int, str]]] = {}
        # Topological sort of derived stats (dependencies first). Populated by loader.py.
        # Used by _recompute_derived_stats() in effects.py to evaluate in safe order.
        self.derived_eval_order: "List[StatDefinition]" = []

    @property
    def ingame_time_resolver(self) -> "InGameTimeResolver | None":
        return self._ingame_time_resolver

    @classmethod
    def build(
        cls: Type["ContentRegistry"],
        manifests: List[ManifestEnvelope],
        template_engine: "GameTemplateEngine | None" = None,
    ) -> "ContentRegistry":
        registry = cls()
        registry.template_engine = template_engine
        for m in manifests:
            match m.kind:
                case "Region":
                    registry.regions.register(cast(RegionManifest, m))
                case "Location":
                    registry.locations.register(cast(LocationManifest, m))
                case "Adventure":
                    registry.adventures.register(cast(AdventureManifest, m))
                case "Archetype":
                    registry.archetypes.register(cast(ArchetypeManifest, m))
                case "Enemy":
                    registry.enemies.register(cast(EnemyManifest, m))
                case "Item":
                    registry.items.register(cast(ItemManifest, m))
                case "LootTable":
                    registry.loot_tables.register(cast(LootTableManifest, m))
                case "Recipe":
                    registry.recipes.register(cast(RecipeManifest, m))
                case "Quest":
                    registry.quests.register(cast(QuestManifest, m))
                case "Skill":
                    registry.skills.register(cast(SkillManifest, m))
                case "Buff":
                    registry.buffs.register(cast(BuffManifest, m))
                case "CustomCondition":
                    registry.custom_conditions.register(cast(CustomConditionManifest, m))
                case "CombatSystem":
                    registry.combat_systems.register(cast(CombatSystemManifest, m))
                case "Game":
                    registry.game = cast(GameManifest, m)
                    # Build the in-game time resolver once the game manifest is available.
                    # A malformed time spec (e.g. missing root cycle) may raise here; skip
                    # resolver construction so the semantic validator can report the error.
                    game_manifest = registry.game
                    if game_manifest.spec.time is not None:
                        from oscilla.engine.ingame_time import InGameTimeResolver
                        from oscilla.engine.loader import compute_epoch_offset

                        try:
                            epoch_offset = compute_epoch_offset(game_manifest.spec.time)
                            registry._ingame_time_resolver = InGameTimeResolver(
                                spec=game_manifest.spec.time,
                                epoch_offset=epoch_offset,
                            )
                        except Exception:
                            # Leave _ingame_time_resolver as None; the semantic validator
                            # will surface actionable errors about the malformed spec.
                            pass
                case "CharacterConfig":
                    registry.character_config = cast(CharacterConfigManifest, m)
        return registry

    def resolve_loot_groups(self, loot_ref: str) -> "List[LootGroup] | None":
        """Resolve a loot_ref to its loot groups.

        Resolves against loot_tables only. The historical enemy fallback is
        removed — loot_ref is exclusively a named LootTable manifest reference.

        Returns None if the ref is not found, or if the table has no groups.
        """
        loot_table = self.loot_tables.get(loot_ref)
        if loot_table is not None:
            return loot_table.spec.groups if loot_table.spec.groups else None

        return None

    def resolve_combat_system(self, name: str | None) -> "CombatSystemManifest | None":
        """Resolve a CombatSystem manifest by name with fallback logic.

        Resolution order:
        1. The explicit ``name`` argument (if provided).
        2. The game manifest's ``default_combat_system`` field.
        3. Auto-promote when exactly one CombatSystem is registered.
        """
        if name is not None:
            return self.combat_systems.get(name)

        if self.game is not None and self.game.spec.default_combat_system is not None:
            return self.combat_systems.get(self.game.spec.default_combat_system)

        all_systems = list(self.combat_systems.all())
        if len(all_systems) == 1:
            return all_systems[0]

        return None

    def get_default_combat_system(self) -> "CombatSystemManifest | None":
        """Return the default combat system for this content package."""
        return self.resolve_combat_system(name=None)
