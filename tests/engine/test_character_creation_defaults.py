"""Tests for CharacterCreationDefaults integration in new_character()."""

from __future__ import annotations

import logging

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.models.base import Metadata
from oscilla.engine.models.character_config import CharacterConfigManifest, CharacterConfigSpec, StatDefinition
from oscilla.engine.models.game import CharacterCreationDefaults, GameManifest, GameSpec, HpFormula
from oscilla.engine.templates import DEFAULT_PRONOUN_SET, PRONOUN_SETS


def _make_game(character_creation: CharacterCreationDefaults | None = None) -> GameManifest:
    return GameManifest(
        apiVersion="game/v1",
        kind="Game",
        metadata=Metadata(name="cc-test-game"),
        spec=GameSpec(
            displayName="CC Test",
            xp_thresholds=[100],
            hp_formula=HpFormula(base_hp=20, hp_per_level=5),
            character_creation=character_creation,
        ),
    )


def _make_char_config() -> CharacterConfigManifest:
    return CharacterConfigManifest(
        apiVersion="game/v1",
        kind="CharacterConfig",
        metadata=Metadata(name="cc-test-char-config"),
        spec=CharacterConfigSpec(
            public_stats=[StatDefinition(name="strength", type="int", default=10)],
            hidden_stats=[],
        ),
    )


def test_new_character_uses_default_pronouns_from_game_spec() -> None:
    """When character_creation.default_pronouns is set, new_character() applies it."""
    game = _make_game(character_creation=CharacterCreationDefaults(default_pronouns="she_her"))
    player = CharacterState.new_character(
        name="Hero",
        game_manifest=game,
        character_config=_make_char_config(),
    )
    expected = PRONOUN_SETS["she_her"]
    assert player.pronouns == expected


def test_new_character_uses_default_pronoun_set_when_no_config() -> None:
    """When character_creation is absent, new_character() falls back to DEFAULT_PRONOUN_SET."""
    game = _make_game()
    player = CharacterState.new_character(
        name="Hero",
        game_manifest=game,
        character_config=_make_char_config(),
    )
    assert player.pronouns == DEFAULT_PRONOUN_SET


def test_new_character_warns_and_falls_back_on_unknown_pronoun_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When default_pronouns is an unknown key, new_character() warns and uses DEFAULT_PRONOUN_SET."""
    game = _make_game(character_creation=CharacterCreationDefaults(default_pronouns="elf_elvish"))
    with caplog.at_level(logging.WARNING):
        player = CharacterState.new_character(
            name="Hero",
            game_manifest=game,
            character_config=_make_char_config(),
        )
    assert player.pronouns == DEFAULT_PRONOUN_SET
    assert any("elf_elvish" in r.message for r in caplog.records)


def test_character_creation_defaults_default_name_overrides_engine_default() -> None:
    """CharacterCreationDefaults.default_name overrides the engine DEFAULT_CHARACTER_NAME at session start."""
    # This tests the model validation only — the session wires it at runtime.
    defaults = CharacterCreationDefaults(default_name="Protagonist")
    assert defaults.default_name == "Protagonist"
