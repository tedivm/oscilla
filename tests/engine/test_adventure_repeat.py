"""Tests for adventure repeat controls (is_adventure_eligible)."""

from __future__ import annotations

import time
from uuid import uuid4

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.models.adventure import AdventureSpec


def _make_player() -> CharacterState:
    return CharacterState(
        character_id=uuid4(),
        name="Tester",
        prestige_count=0,
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
    assert player.is_adventure_eligible("cave", spec, now_ts=int(time.time())) is True


def test_eligible_no_constraints_played_many_times() -> None:
    """No constraints → eligible regardless of previous completions."""
    player = _make_player()
    player.statistics.adventures_completed["cave"] = 99
    spec = _spec()
    assert player.is_adventure_eligible("cave", spec, now_ts=int(time.time())) is True


# --- repeatable: false ---


def test_repeatable_false_not_yet_completed() -> None:
    """repeatable: false → eligible before first completion."""
    player = _make_player()
    spec = _spec(repeatable=False)
    assert player.is_adventure_eligible("cave", spec, now_ts=int(time.time())) is True


def test_repeatable_false_hides_after_completion() -> None:
    """repeatable: false → ineligible after first completion."""
    player = _make_player()
    player.statistics.adventures_completed["cave"] = 1
    spec = _spec(repeatable=False)
    assert player.is_adventure_eligible("cave", spec, now_ts=int(time.time())) is False


# --- max_completions ---


def test_max_completions_below_cap() -> None:
    """max_completions=2 → eligible when completions < 2."""
    player = _make_player()
    player.statistics.adventures_completed["cave"] = 1
    spec = _spec(max_completions=2)
    assert player.is_adventure_eligible("cave", spec, now_ts=int(time.time())) is True


def test_max_completions_at_cap() -> None:
    """max_completions=2 → ineligible at exactly 2 completions."""
    player = _make_player()
    player.statistics.adventures_completed["cave"] = 2
    spec = _spec(max_completions=2)
    assert player.is_adventure_eligible("cave", spec, now_ts=int(time.time())) is False


def test_max_completions_above_cap() -> None:
    """max_completions=2 → ineligible above cap."""
    player = _make_player()
    player.statistics.adventures_completed["cave"] = 5
    spec = _spec(max_completions=2)
    assert player.is_adventure_eligible("cave", spec, now_ts=int(time.time())) is False


# --- cooldown: seconds ---


def test_cooldown_seconds_within_window_hidden() -> None:
    """cooldown seconds=86400 → ineligible when completed less than 86400 seconds ago."""
    player = _make_player()
    now_ts = int(time.time())
    player.adventure_last_completed_real_ts["cave"] = now_ts - 100  # 100 seconds ago
    spec = _spec(cooldown={"seconds": 86400})
    assert player.is_adventure_eligible("cave", spec, now_ts=now_ts) is False


def test_cooldown_seconds_past_window_visible() -> None:
    """cooldown seconds=86400 → eligible when completed more than 86400 seconds ago."""
    player = _make_player()
    now_ts = int(time.time())
    player.adventure_last_completed_real_ts["cave"] = now_ts - 86401  # just over 1 day ago
    spec = _spec(cooldown={"seconds": 86400})
    assert player.is_adventure_eligible("cave", spec, now_ts=now_ts) is True


def test_cooldown_seconds_never_completed_no_cooldown() -> None:
    """cooldown seconds set but never completed → eligible."""
    player = _make_player()
    spec = _spec(cooldown={"seconds": 3600})
    assert player.is_adventure_eligible("cave", spec, now_ts=int(time.time())) is True


# --- cooldown: ticks ---


def test_cooldown_ticks_below_threshold() -> None:
    """cooldown ticks=3 → ineligible when < 3 ticks have elapsed."""
    player = _make_player()
    # Last completed at tick 10; only 2 ticks have elapsed (internal_ticks=12) → ineligible
    player.adventure_last_completed_at_ticks["cave"] = 10
    player.internal_ticks = 12
    spec = _spec(cooldown={"ticks": 3})
    assert player.is_adventure_eligible("cave", spec, now_ts=int(time.time())) is False


def test_cooldown_ticks_at_threshold() -> None:
    """cooldown ticks=3 → eligible at exactly 3 ticks elapsed."""
    player = _make_player()
    # Last completed at tick 10; 3 ticks have elapsed (internal_ticks=13) → eligible
    player.adventure_last_completed_at_ticks["cave"] = 10
    player.internal_ticks = 13
    spec = _spec(cooldown={"ticks": 3})
    assert player.is_adventure_eligible("cave", spec, now_ts=int(time.time())) is True


def test_cooldown_ticks_never_completed_no_cooldown() -> None:
    """cooldown ticks set but never completed → eligible."""
    player = _make_player()
    spec = _spec(cooldown={"ticks": 3})
    assert player.is_adventure_eligible("cave", spec, now_ts=int(time.time())) is True


# --- repeat controls validator ---


def test_repeatable_false_and_max_completions_raises() -> None:
    """Setting both repeatable: false and max_completions should raise ValidationError."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _spec(repeatable=False, max_completions=3)
