"""Manifest model registry mapping kind strings to Pydantic model classes."""

from typing import Dict, Type

from oscilla.engine.models.adventure import AdventureManifest
from oscilla.engine.models.base import ManifestEnvelope
from oscilla.engine.models.buff import BuffManifest
from oscilla.engine.models.character_config import CharacterConfigManifest
from oscilla.engine.models.enemy import EnemyManifest
from oscilla.engine.models.game import GameManifest
from oscilla.engine.models.game_class import ClassManifest
from oscilla.engine.models.item import EquipSpec, ItemManifest, StatModifier
from oscilla.engine.models.location import LocationManifest
from oscilla.engine.models.loot_table import LootTableManifest
from oscilla.engine.models.quest import QuestManifest
from oscilla.engine.models.recipe import RecipeManifest
from oscilla.engine.models.region import RegionManifest
from oscilla.engine.models.skill import SkillManifest

MANIFEST_REGISTRY: Dict[str, Type[ManifestEnvelope]] = {
    "Region": RegionManifest,
    "Location": LocationManifest,
    "Adventure": AdventureManifest,
    "Enemy": EnemyManifest,
    "Item": ItemManifest,
    "Recipe": RecipeManifest,
    "Quest": QuestManifest,
    "Class": ClassManifest,
    "Game": GameManifest,
    "CharacterConfig": CharacterConfigManifest,
    "Skill": SkillManifest,
    "Buff": BuffManifest,
    "LootTable": LootTableManifest,
}

__all__ = [
    "MANIFEST_REGISTRY",
    "AdventureManifest",
    "BuffManifest",
    "CharacterConfigManifest",
    "ClassManifest",
    "EquipSpec",
    "EnemyManifest",
    "GameManifest",
    "ItemManifest",
    "LocationManifest",
    "ManifestEnvelope",
    "QuestManifest",
    "RecipeManifest",
    "RegionManifest",
    "SkillManifest",
    "StatModifier",
]
