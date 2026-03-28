"""Tests for CharacterConfig models and validation."""

import pytest
from pydantic import ValidationError

from oscilla.engine.models.character_config import CharacterConfigManifest, CharacterConfigSpec, StatDefinition


def test_stat_definition_basic() -> None:
    """Test basic StatDefinition creation."""
    stat = StatDefinition(name="strength", type="int", default=10)
    assert stat.name == "strength"
    assert stat.type == "int"
    assert stat.default == 10


def test_character_config_spec_valid() -> None:
    """Test valid CharacterConfigSpec creation."""
    spec = CharacterConfigSpec(
        public_stats=[
            StatDefinition(name="strength", type="int", default=10),
            StatDefinition(name="dexterity", type="int", default=8),
        ],
        hidden_stats=[
            StatDefinition(name="luck", type="int", default=5),
        ],
    )
    assert len(spec.public_stats) == 2
    assert len(spec.hidden_stats) == 1


def test_character_config_duplicate_stat_names_error() -> None:
    """Test that duplicate stat names between public and hidden stats raise ValidationError."""
    with pytest.raises(ValidationError, match="Duplicate stat names"):
        CharacterConfigSpec(
            public_stats=[
                StatDefinition(name="strength", type="int", default=10),
            ],
            hidden_stats=[
                StatDefinition(name="strength", type="int", default=5),  # Duplicate!
            ],
        )


def test_character_config_duplicate_within_public_stats() -> None:
    """Test that duplicate stat names within public_stats raise ValidationError."""
    with pytest.raises(ValidationError, match="Duplicate stat names"):
        CharacterConfigSpec(
            public_stats=[
                StatDefinition(name="strength", type="int", default=10),
                StatDefinition(name="strength", type="int", default=8),  # Duplicate!
            ],
            hidden_stats=[],
        )


def test_character_config_duplicate_within_hidden_stats() -> None:
    """Test that duplicate stat names within hidden_stats raise ValidationError."""
    with pytest.raises(ValidationError, match="Duplicate stat names"):
        CharacterConfigSpec(
            public_stats=[],
            hidden_stats=[
                StatDefinition(name="luck", type="int", default=5),
                StatDefinition(name="luck", type="int", default=3),  # Duplicate!
            ],
        )


def test_character_config_manifest_complete() -> None:
    """Test complete CharacterConfigManifest creation."""
    manifest = CharacterConfigManifest(
        apiVersion="game/v1",
        kind="CharacterConfig",
        metadata={"name": "test-config"},
        spec=CharacterConfigSpec(
            public_stats=[
                StatDefinition(name="strength", type="int", default=10),
            ],
            hidden_stats=[
                StatDefinition(name="luck", type="int", default=5),
            ],
        ),
    )
    assert manifest.kind == "CharacterConfig"
    assert manifest.spec.public_stats[0].name == "strength"
