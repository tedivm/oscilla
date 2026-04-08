"""Tests for the Cooldown model — validation constraints."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from oscilla.engine.models.adventure import Cooldown


def test_cooldown_ticks_only_is_valid() -> None:
    """A cooldown with only ticks is valid."""
    cooldown = Cooldown(ticks=5)
    assert cooldown.ticks == 5
    assert cooldown.scope is None


def test_cooldown_seconds_only_is_valid() -> None:
    """A cooldown with only seconds is valid."""
    cooldown = Cooldown(seconds=3600)
    assert cooldown.seconds == 3600


def test_cooldown_game_ticks_only_is_valid() -> None:
    """A cooldown with only game_ticks is valid."""
    cooldown = Cooldown(game_ticks=10)
    assert cooldown.game_ticks == 10


def test_cooldown_turn_scope_with_turns_is_valid() -> None:
    """scope=turn combined with turns field is valid."""
    cooldown = Cooldown(scope="turn", turns=3)
    assert cooldown.scope == "turn"
    assert cooldown.turns == 3


def test_cooldown_empty_raises_validation_error() -> None:
    """An empty Cooldown with no constraint fields is rejected."""
    with pytest.raises(ValidationError, match="at least one constraint"):
        Cooldown()


def test_cooldown_turn_scope_rejects_ticks_field() -> None:
    """scope=turn with ticks field is rejected — turn scope only accepts turns."""
    with pytest.raises(ValidationError, match="turn.*scope.*only|scope.*turn.*only|only.*turns"):
        Cooldown(scope="turn", ticks=5)


def test_cooldown_turn_scope_rejects_seconds_field() -> None:
    """scope=turn with seconds field is rejected."""
    with pytest.raises(ValidationError, match="turn.*scope.*only|scope.*turn.*only|only.*turns"):
        Cooldown(scope="turn", seconds=3600)


def test_cooldown_no_scope_rejects_turns_field() -> None:
    """turns field without scope=turn is rejected."""
    with pytest.raises(ValidationError, match="turns.*scope|scope.*turns"):
        Cooldown(turns=3)


def test_cooldown_template_string_is_accepted() -> None:
    """Template expressions are valid for cooldown fields (resolved at runtime)."""
    cooldown = Cooldown(seconds="{{ SECONDS_PER_DAY }}")
    assert cooldown.seconds == "{{ SECONDS_PER_DAY }}"


def test_cooldown_multiple_non_turn_fields_are_valid() -> None:
    """Multiple constraint fields (ticks + seconds) can be combined."""
    cooldown = Cooldown(ticks=3, seconds=3600)
    assert cooldown.ticks == 3
    assert cooldown.seconds == 3600
