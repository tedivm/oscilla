"""Content registry — typed in-memory store for all loaded manifests."""

from typing import TYPE_CHECKING, Dict, Generic, Iterator, List, Type, TypeVar, cast

from oscilla.engine.models.adventure import AdventureManifest
from oscilla.engine.models.base import ManifestEnvelope
from oscilla.engine.models.buff import BuffManifest
from oscilla.engine.models.character_config import CharacterConfigManifest
from oscilla.engine.models.enemy import EnemyManifest
from oscilla.engine.models.game import GameManifest
from oscilla.engine.models.game_class import ClassManifest
from oscilla.engine.models.item import ItemManifest
from oscilla.engine.models.location import LocationManifest
from oscilla.engine.models.quest import QuestManifest
from oscilla.engine.models.recipe import RecipeManifest
from oscilla.engine.models.region import RegionManifest
from oscilla.engine.models.skill import SkillManifest

if TYPE_CHECKING:
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
        self.enemies: KindRegistry[EnemyManifest] = KindRegistry()
        self.items: KindRegistry[ItemManifest] = KindRegistry()
        self.recipes: KindRegistry[RecipeManifest] = KindRegistry()
        self.quests: KindRegistry[QuestManifest] = KindRegistry()
        self.classes: KindRegistry[ClassManifest] = KindRegistry()
        self.buffs: KindRegistry[BuffManifest] = KindRegistry()
        self.skills: KindRegistry[SkillManifest] = KindRegistry()
        self.game: GameManifest | None = None
        self.character_config: CharacterConfigManifest | None = None
        # Holds precompiled templates; populated by loader.py after validation.
        self.template_engine: "GameTemplateEngine | None" = None

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
                case "Enemy":
                    registry.enemies.register(cast(EnemyManifest, m))
                case "Item":
                    registry.items.register(cast(ItemManifest, m))
                case "Recipe":
                    registry.recipes.register(cast(RecipeManifest, m))
                case "Quest":
                    registry.quests.register(cast(QuestManifest, m))
                case "Class":
                    registry.classes.register(cast(ClassManifest, m))
                case "Skill":
                    registry.skills.register(cast(SkillManifest, m))
                case "Buff":
                    registry.buffs.register(cast(BuffManifest, m))
                case "Game":
                    registry.game = cast(GameManifest, m)
                case "CharacterConfig":
                    registry.character_config = cast(CharacterConfigManifest, m)
        return registry
