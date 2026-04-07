"""Tests for the iteration → prestige_count rename."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from oscilla.engine.character import CharacterState
from oscilla.engine.models.base import PrestigeCountCondition
from oscilla.engine.registry import ContentRegistry


def test_prestige_count_condition_yaml_key() -> None:
    """type: prestige_count parses as PrestigeCountCondition."""
    data = {"type": "prestige_count", "gte": 1}
    cond = PrestigeCountCondition(**data)
    assert cond.type == "prestige_count"
    assert cond.gte == 1


def test_iteration_yaml_key_rejected() -> None:
    """type: iteration is no longer valid and must raise ValidationError."""
    with pytest.raises(ValidationError):
        PrestigeCountCondition(type="iteration", gte=1)  # type: ignore[call-overload]


def test_character_state_prestige_count_field(base_player: CharacterState) -> None:
    """new_character() sets prestige_count=0 and the field 'iteration' does not exist."""
    assert base_player.prestige_count == 0
    assert not hasattr(base_player, "iteration")


def test_to_dict_uses_prestige_count_key(base_player: CharacterState) -> None:
    """to_dict() output contains 'prestige_count' and not 'iteration'."""
    d = base_player.to_dict()
    assert "prestige_count" in d
    assert "iteration" not in d


def test_from_dict_backward_compat_iteration_key(
    base_player: CharacterState, minimal_registry: ContentRegistry
) -> None:
    """from_dict() with the old 'iteration' key still works (backward compat)."""
    assert minimal_registry.character_config is not None
    raw = base_player.to_dict()
    # Simulate an old serialized state using the old key name.
    raw["iteration"] = 3
    del raw["prestige_count"]
    restored = CharacterState.from_dict(raw, character_config=minimal_registry.character_config)
    assert restored.prestige_count == 3
