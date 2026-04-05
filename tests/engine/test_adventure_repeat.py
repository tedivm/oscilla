"""Tests for adventure repeat controls (is_adventure_eligible)."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.models.adventure import AdventureSpec


def _make_player() -> CharacterState:
    return CharacterState(
        character_id=uuid4(),
        name="Tester",
        character_class=None,
        level=1,
        xp=0,
        hp=20,
        max_hp=20,
        iteration=0,
        current_location=None,
        stats={},
    )


def _spec(**kwargs: object) -> AdventureSpec:
    """Build a minimal AdventureSpec with overrides."""
    base = {
        "displayName": "Test Adventure",
        "type": "adventure",
        "start": "s1",
        "steps": [
            {
                "type": "narrative",
                "name": "s1",
                "text": "Hello",
                "choices": [{"label": "OK", "effects": [{"type": "end_adventure", "outcome": "completed"}]}],
            }
        ],
    }
    base.update(kwargs)
    return AdventureSpec.model_validate(base)


# --- no constraints ---


def test_eligible_no_constraints_never_played() -> None:
    """No constraints + never played → always eligible."""
    player = _make_player()
    spec = _spec()
    assert player.is_adventure_eligible("cave", spec, date.today()) is True


def test_eligible_no_constraints_played_many_times() -> None:
    """No constraints → eligible regardless of previous completions."""
    player = _make_player()
    player.statistics.adventures_completed["cave"] = 99
    spec = _spec()
    assert player.is_adventure_eligible("cave", spec, date.today()) is True


# --- repeatable: false ---


def test_repeatable_false_not_yet_completed() -> None:
    """repeatable: false → eligible before first completion."""
    player = _make_player()
    spec = _spec(repeatable=False)
    assert player.is_adventure_eligible("cave", spec, date.today()) is True


def test_repeatable_false_hides_after_completion() -> None:
    """repeatable: false → ineligible after first completion."""
    player = _make_player()
    player.statistics.adventures_completed["cave"] = 1
    spec = _spec(repeatable=False)
    assert player.is_adventure_eligible("cave", spec, date.today()) is False


# --- max_completions ---


def test_max_completions_below_cap() -> None:
    """max_completions=2 → eligible when completions < 2."""
    player = _make_player()
    player.statistics.adventures_completed["cave"] = 1
    spec = _spec(max_completions=2)
    assert player.is_adventure_eligible("cave", spec, date.today()) is True


def test_max_completions_at_cap() -> None:
    """max_completions=2 → ineligible at exactly 2 completions."""
    player = _make_player()
    player.statistics.adventures_completed["cave"] = 2
    spec = _spec(max_completions=2)
    assert player.is_adventure_eligible("cave", spec, date.today()) is False


def test_max_completions_above_cap() -> None:
    """max_completions=2 → ineligible above cap."""
    player = _make_player()
    player.statistics.adventures_completed["cave"] = 5
    spec = _spec(max_completions=2)
    assert player.is_adventure_eligible("cave", spec, date.today()) is False


# --- cooldown_days ---


def test_cooldown_days_same_day_hidden() -> None:
    """cooldown_days=1 → ineligible when completed today."""
    player = _make_player()
    today = date.today()
    player.adventure_last_completed_on["cave"] = today.isoformat()
    spec = _spec(cooldown_days=1)
    assert player.is_adventure_eligible("cave", spec, today) is False


def test_cooldown_days_next_day_visible() -> None:
    """cooldown_days=1 → eligible when cooldown has passed."""
    player = _make_player()
    yesterday = date.today() - timedelta(days=1)
    player.adventure_last_completed_on["cave"] = yesterday.isoformat()
    spec = _spec(cooldown_days=1)
    assert player.is_adventure_eligible("cave", spec, date.today()) is True


def test_cooldown_days_never_completed_no_cooldown() -> None:
    """cooldown_days set but never completed → eligible."""
    player = _make_player()
    spec = _spec(cooldown_days=7)
    assert player.is_adventure_eligible("cave", spec, date.today()) is True


# --- cooldown_adventures ---


def test_cooldown_adventures_below_threshold() -> None:
    """cooldown_adventures=3 maps to cooldown_ticks=3; ineligible when < 3 ticks elapsed."""
    player = _make_player()
    # Last completed at tick 10; only 2 ticks have elapsed (internal_ticks=12) → ineligible
    player.adventure_last_completed_at_ticks["cave"] = 10
    player.internal_ticks = 12
    spec = _spec(cooldown_adventures=3)
    assert player.is_adventure_eligible("cave", spec, date.today()) is False


def test_cooldown_adventures_at_threshold() -> None:
    """cooldown_adventures=3 maps to cooldown_ticks=3; eligible at exactly 3 ticks elapsed."""
    player = _make_player()
    # Last completed at tick 10; 3 ticks have elapsed (internal_ticks=13) → eligible
    player.adventure_last_completed_at_ticks["cave"] = 10
    player.internal_ticks = 13
    spec = _spec(cooldown_adventures=3)
    assert player.is_adventure_eligible("cave", spec, date.today()) is True


def test_cooldown_adventures_never_completed_no_cooldown() -> None:
    """cooldown_adventures set but never completed → eligible."""
    player = _make_player()
    spec = _spec(cooldown_adventures=3)
    assert player.is_adventure_eligible("cave", spec, date.today()) is True


# --- repeat controls validator ---


def test_repeatable_false_and_max_completions_raises() -> None:
    """Setting both repeatable: false and max_completions should raise ValidationError."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _spec(repeatable=False, max_completions=3)
