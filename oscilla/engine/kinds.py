"""Central registry of all Oscilla manifest kinds with metadata.

This module is the single source of truth for all manifest kinds. Every
subsystem that iterates over kinds (CLI, schema export, graph renderers)
imports from here rather than defining its own mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List


@dataclass(frozen=True)
class ManifestKind:
    """Metadata about one manifest kind."""

    slug: str  # CLI kind slug, e.g. "adventure"
    plural_slug: str  # Plural CLI slug, e.g. "adventures"
    registry_attr: str  # ContentRegistry attribute name, e.g. "adventures"
    display_label: str  # Singular display label, e.g. "Adventure"
    model_class: Any  # Pydantic model class, e.g. AdventureManifest
    creatable: bool = True  # Whether `content create` supports this kind


def _load_kinds() -> List[ManifestKind]:
    """Import and register all manifest kinds.

    Deferred import keeps the module importable without loading all models.
    """
    from oscilla.engine.models.adventure import AdventureManifest
    from oscilla.engine.models.buff import BuffManifest
    from oscilla.engine.models.character_config import CharacterConfigManifest
    from oscilla.engine.models.enemy import EnemyManifest
    from oscilla.engine.models.game import GameManifest
    from oscilla.engine.models.game_class import ClassManifest
    from oscilla.engine.models.item import ItemManifest
    from oscilla.engine.models.location import LocationManifest
    from oscilla.engine.models.loot_table import LootTableManifest
    from oscilla.engine.models.quest import QuestManifest
    from oscilla.engine.models.recipe import RecipeManifest
    from oscilla.engine.models.region import RegionManifest
    from oscilla.engine.models.skill import SkillManifest

    return [
        ManifestKind("adventure", "adventures", "adventures", "Adventure", AdventureManifest, creatable=True),
        ManifestKind("buff", "buffs", "buffs", "Buff", BuffManifest, creatable=False),
        ManifestKind(
            "character-config",
            "character-configs",
            "character_config",
            "CharacterConfig",
            CharacterConfigManifest,
            creatable=False,
        ),
        ManifestKind("class", "classes", "classes", "Class", ClassManifest, creatable=False),
        ManifestKind("enemy", "enemies", "enemies", "Enemy", EnemyManifest, creatable=True),
        ManifestKind("game", "games", "game", "Game", GameManifest, creatable=False),
        ManifestKind("item", "items", "items", "Item", ItemManifest, creatable=True),
        ManifestKind("location", "locations", "locations", "Location", LocationManifest, creatable=True),
        ManifestKind("loot-table", "loot-tables", "loot_tables", "LootTable", LootTableManifest, creatable=False),
        ManifestKind("quest", "quests", "quests", "Quest", QuestManifest, creatable=True),
        ManifestKind("recipe", "recipes", "recipes", "Recipe", RecipeManifest, creatable=False),
        ManifestKind("region", "regions", "regions", "Region", RegionManifest, creatable=True),
        ManifestKind("skill", "skills", "skills", "Skill", SkillManifest, creatable=False),
    ]


# Module-level list. Import this in consuming modules.
ALL_KINDS: List[ManifestKind] = _load_kinds()

# Convenience lookup dicts.
KINDS_BY_SLUG: dict[str, ManifestKind] = {k.slug: k for k in ALL_KINDS}
KINDS_BY_PLURAL: dict[str, ManifestKind] = {k.plural_slug: k for k in ALL_KINDS}
KINDS_BY_REGISTRY_ATTR: dict[str, ManifestKind] = {k.registry_attr: k for k in ALL_KINDS}
