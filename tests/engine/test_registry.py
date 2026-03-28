"""Tests for ContentRegistry and KindRegistry."""

import pytest

from oscilla.engine.models.adventure import AdventureManifest, AdventureSpec
from oscilla.engine.models.base import ManifestEnvelope, Metadata
from oscilla.engine.models.character_config import CharacterConfigManifest, CharacterConfigSpec
from oscilla.engine.models.enemy import EnemyManifest, EnemySpec
from oscilla.engine.models.game import GameManifest, GameSpec, HpFormula
from oscilla.engine.models.item import ItemManifest, ItemSpec
from oscilla.engine.models.location import LocationManifest, LocationSpec
from oscilla.engine.models.quest import QuestManifest, QuestSpec, QuestStage
from oscilla.engine.models.recipe import RecipeManifest, RecipeSpec, RecipeIngredient, RecipeOutput
from oscilla.engine.models.region import RegionManifest, RegionSpec
from oscilla.engine.registry import ContentRegistry, KindRegistry


def test_kind_registry_basic_operations() -> None:
    """Test basic KindRegistry operations."""
    registry: KindRegistry[ItemManifest] = KindRegistry()

    # Create a test item
    item = ItemManifest(
        apiVersion="game/v1",
        kind="Item",
        metadata=Metadata(name="test-item"),
        spec=ItemSpec(displayName="Test Item", kind="consumable"),
    )

    # Test empty registry
    assert len(registry) == 0
    assert registry.get("test-item") is None
    assert "test-item" not in registry
    assert list(registry.all()) == []
    assert registry.names() == []

    # Register item
    registry.register(item)

    # Test populated registry
    assert len(registry) == 1
    assert registry.get("test-item") == item
    assert "test-item" in registry
    assert list(registry.all()) == [item]
    assert registry.names() == ["test-item"]


def test_kind_registry_require_success() -> None:
    """Test KindRegistry.require() when item exists."""
    registry: KindRegistry[ItemManifest] = KindRegistry()

    item = ItemManifest(
        apiVersion="game/v1",
        kind="Item",
        metadata=Metadata(name="test-item"),
        spec=ItemSpec(displayName="Test Item", kind="consumable"),
    )
    registry.register(item)

    result = registry.require("test-item", "Item")
    assert result == item


def test_kind_registry_require_missing_raises_error() -> None:
    """Test KindRegistry.require() when item is missing."""
    registry: KindRegistry[ItemManifest] = KindRegistry()

    with pytest.raises(KeyError, match="No Item named 'missing-item' in registry"):
        registry.require("missing-item", "Item")


def test_content_registry_initialization() -> None:
    """Test ContentRegistry initialization."""
    registry = ContentRegistry()

    assert isinstance(registry.regions, KindRegistry)
    assert isinstance(registry.locations, KindRegistry)
    assert isinstance(registry.adventures, KindRegistry)
    assert isinstance(registry.enemies, KindRegistry)
    assert isinstance(registry.items, KindRegistry)
    assert isinstance(registry.recipes, KindRegistry)
    assert isinstance(registry.quests, KindRegistry)
    assert isinstance(registry.classes, KindRegistry)
    assert registry.game is None
    assert registry.character_config is None


def test_content_registry_build_with_all_kinds() -> None:
    """Test ContentRegistry.build() processes all manifest kinds."""
    manifests: list[ManifestEnvelope] = [
        RegionManifest(
            apiVersion="game/v1",
            kind="Region",
            metadata=Metadata(name="test-region"),
            spec=RegionSpec(displayName="Test Region"),
        ),
        LocationManifest(
            apiVersion="game/v1",
            kind="Location",
            metadata=Metadata(name="test-location"),
            spec=LocationSpec(displayName="Test Location", region="test-region", adventures=[]),
        ),
        AdventureManifest(
            apiVersion="game/v1",
            kind="Adventure",
            metadata=Metadata(name="test-adventure"),
            spec=AdventureSpec(displayName="Test Adventure", steps=[]),
        ),
        EnemyManifest(
            apiVersion="game/v1",
            kind="Enemy",
            metadata=Metadata(name="test-enemy"),
            spec=EnemySpec(displayName="Test Enemy", hp=10, attack=5, defense=2, xp_reward=10),
        ),
        ItemManifest(
            apiVersion="game/v1",
            kind="Item",
            metadata=Metadata(name="test-item"),
            spec=ItemSpec(displayName="Test Item", kind="consumable"),
        ),
        RecipeManifest(
            apiVersion="game/v1",
            kind="Recipe",
            metadata=Metadata(name="test-recipe"),
            spec=RecipeSpec(
                displayName="Test Recipe",
                inputs=[RecipeIngredient(item="test-input", quantity=1)],
                output=RecipeOutput(item="test-item", quantity=1),
            ),
        ),
        QuestManifest(
            apiVersion="game/v1",
            kind="Quest",
            metadata=Metadata(name="test-quest"),
            spec=QuestSpec(
                displayName="Test Quest", entry_stage="start", stages=[QuestStage(name="start", terminal=True)]
            ),
        ),
        GameManifest(
            apiVersion="game/v1",
            kind="Game",
            metadata=Metadata(name="test-game"),
            spec=GameSpec(
                displayName="Test Game", xp_thresholds=[0, 100], hp_formula=HpFormula(base_hp=20, hp_per_level=5)
            ),
        ),
        CharacterConfigManifest(
            apiVersion="game/v1",
            kind="CharacterConfig",
            metadata=Metadata(name="test-character-config"),
            spec=CharacterConfigSpec(public_stats=[], hidden_stats=[]),
        ),
    ]

    registry = ContentRegistry.build(manifests)

    # Check that all registries are populated
    assert len(registry.regions) == 1
    assert len(registry.locations) == 1
    assert len(registry.adventures) == 1
    assert len(registry.enemies) == 1
    assert len(registry.items) == 1
    assert len(registry.recipes) == 1
    assert len(registry.quests) == 1
    assert len(registry.classes) == 0  # No Class manifest added

    # Check that singleton manifests are set
    assert registry.game is not None
    assert registry.game.metadata.name == "test-game"
    assert registry.character_config is not None
    assert registry.character_config.metadata.name == "test-character-config"
