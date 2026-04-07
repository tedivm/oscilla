"""Tests for the SetNameEffect handler and the name_equals condition."""

from __future__ import annotations

from oscilla.engine.character import CharacterState, DEFAULT_CHARACTER_NAME
from oscilla.engine.conditions import evaluate
from oscilla.engine.models.adventure import SetNameEffect
from oscilla.engine.models.base import NameEqualsCondition
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.steps.effects import run_effect
from tests.engine.conftest import MockTUI


async def test_set_name_always_updates_character_name(base_player: CharacterState) -> None:
    """SetNameEffect always prompts and replaces the player name, regardless of the current name."""
    base_player.name = DEFAULT_CHARACTER_NAME
    tui = MockTUI(text_responses=["Aria"])
    effect = SetNameEffect(type="set_name")
    await run_effect(effect=effect, player=base_player, registry=ContentRegistry(), tui=tui)
    assert base_player.name == "Aria"


async def test_set_name_overwrites_existing_name(base_player: CharacterState) -> None:
    """SetNameEffect replaces a non-default name — callers must gate with requires if needed."""
    base_player.name = "OldName"
    tui = MockTUI(text_responses=["NewName"])
    effect = SetNameEffect(type="set_name")
    await run_effect(effect=effect, player=base_player, registry=ContentRegistry(), tui=tui)
    assert base_player.name == "NewName"


async def test_set_name_strips_whitespace(base_player: CharacterState) -> None:
    """SetNameEffect strips leading and trailing whitespace from user input."""
    base_player.name = DEFAULT_CHARACTER_NAME
    tui = MockTUI(text_responses=["  Aria  "])
    effect = SetNameEffect(type="set_name")
    await run_effect(effect=effect, player=base_player, registry=ContentRegistry(), tui=tui)
    assert base_player.name == "Aria"


def test_name_equals_condition_matches_current_name(base_player: CharacterState) -> None:
    """name_equals returns True when the player name exactly matches the value."""
    base_player.name = DEFAULT_CHARACTER_NAME
    cond = NameEqualsCondition(type="name_equals", value=DEFAULT_CHARACTER_NAME)
    assert evaluate(cond, base_player) is True


def test_name_equals_condition_does_not_match_different_name(base_player: CharacterState) -> None:
    """name_equals returns False when the player name differs from the value."""
    base_player.name = "Elara"
    cond = NameEqualsCondition(type="name_equals", value=DEFAULT_CHARACTER_NAME)
    assert evaluate(cond, base_player) is False


def test_name_equals_condition_is_case_sensitive(base_player: CharacterState) -> None:
    """name_equals comparison is case-sensitive."""
    base_player.name = "adventurer"
    cond = NameEqualsCondition(type="name_equals", value="Adventurer")
    assert evaluate(cond, base_player) is False
