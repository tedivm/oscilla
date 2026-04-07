"""Tests for CharacterConfig models and validation."""

import pytest
from pydantic import ValidationError

from oscilla.engine.models.character_config import (
    CharacterConfigManifest,
    CharacterConfigSpec,
    StatBounds,
    StatDefinition,
)


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
        apiVersion="oscilla/v1",
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


# ---------------------------------------------------------------------------
# StatBounds tests
# ---------------------------------------------------------------------------


def test_stat_bounds_min_gt_max_raises() -> None:
    """StatBounds with min > max should raise ValidationError."""
    with pytest.raises(ValidationError, match="min"):
        StatBounds(min=100, max=10)


def test_stat_bounds_on_bool_stat_raises() -> None:
    """StatDefinition with type=bool and bounds set should raise ValidationError."""
    with pytest.raises(ValidationError, match="bool"):
        StatDefinition(name="flag", type="bool", bounds=StatBounds(min=0, max=1))


def test_stat_bounds_absent_is_valid() -> None:
    """StatDefinition with no bounds field should parse without error."""
    stat = StatDefinition(name="gold", type="int", default=0)
    assert stat.bounds is None


def test_stat_bounds_min_only_is_valid() -> None:
    """StatBounds with only min set (no max) should be valid."""
    stat = StatDefinition(name="reputation", type="int", default=0, bounds=StatBounds(min=0))
    assert stat.bounds is not None
    assert stat.bounds.min == 0
    assert stat.bounds.max is None


def test_stat_bounds_max_only_is_valid() -> None:
    """StatBounds with only max set (no min) should be valid."""
    stat = StatDefinition(name="stress", type="int", default=0, bounds=StatBounds(max=100))
    assert stat.bounds is not None
    assert stat.bounds.min is None
    assert stat.bounds.max == 100


def test_float_stat_type_rejected() -> None:
    """StatDefinition with type='float' should raise ValidationError."""
    with pytest.raises(ValidationError):
        StatDefinition.model_validate({"name": "speed", "type": "float", "default": 1.0})


def test_stat_bounds_min_eq_max_is_valid() -> None:
    """StatBounds with min == max (a fixed value) should be valid."""
    bounds = StatBounds(min=50, max=50)
    assert bounds.min == 50
    assert bounds.max == 50
