"""Integration tests for adventure-scope skill cooldown helpers.

Tests _skill_on_cooldown() and _set_skill_cooldown() from oscilla.engine.actions
against a live CharacterState to verify the full read/write cycle.
"""

from __future__ import annotations

import time
from uuid import uuid4

from oscilla.engine.actions import _set_skill_cooldown, _skill_on_cooldown
from oscilla.engine.character import CharacterState
from oscilla.engine.models.adventure import Cooldown

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bare_player() -> CharacterState:
    """Minimal CharacterState for cooldown helper tests."""
    return CharacterState(
        character_id=uuid4(),
        name="CooldownTester",
        character_class=None,
        prestige_count=0,
        stats={},
    )


# ---------------------------------------------------------------------------
# _skill_on_cooldown — no data → never on cooldown
# ---------------------------------------------------------------------------


def test_skill_on_cooldown_returns_false_with_no_data() -> None:
    """A skill with no expiry records is not on cooldown."""
    player = _bare_player()
    assert _skill_on_cooldown(player=player, skill_ref="fireball") is False


# ---------------------------------------------------------------------------
# _set_skill_cooldown — ticks path
# ---------------------------------------------------------------------------


def test_set_skill_cooldown_ticks_records_expiry() -> None:
    """Setting a ticks cooldown records the correct tick expiry."""
    player = _bare_player()
    player.internal_ticks = 10
    cooldown = Cooldown(ticks=5)

    _set_skill_cooldown(player=player, skill_ref="fireball", cooldown=cooldown)

    assert player.skill_tick_expiry["fireball"] == 15  # 10 + 5


def test_skill_on_cooldown_true_within_tick_window() -> None:
    """skill is on cooldown when internal_ticks < tick_expiry."""
    player = _bare_player()
    player.internal_ticks = 10
    cooldown = Cooldown(ticks=5)
    _set_skill_cooldown(player=player, skill_ref="fireball", cooldown=cooldown)

    # Still at tick 10 — expiry is 15, on cooldown
    assert _skill_on_cooldown(player=player, skill_ref="fireball") is True

    # Advance to tick 14 — still on cooldown
    player.internal_ticks = 14
    assert _skill_on_cooldown(player=player, skill_ref="fireball") is True


def test_skill_on_cooldown_false_at_expiry_tick() -> None:
    """Cooldown expires once internal_ticks reaches tick_expiry."""
    player = _bare_player()
    player.internal_ticks = 10
    cooldown = Cooldown(ticks=5)
    _set_skill_cooldown(player=player, skill_ref="fireball", cooldown=cooldown)

    # Advance to tick 15 — exactly at expiry, no longer on cooldown
    player.internal_ticks = 15
    assert _skill_on_cooldown(player=player, skill_ref="fireball") is False


# ---------------------------------------------------------------------------
# _set_skill_cooldown — seconds path
# ---------------------------------------------------------------------------


def test_set_skill_cooldown_seconds_records_real_expiry() -> None:
    """Setting a seconds cooldown records the correct real_expiry timestamp."""
    player = _bare_player()
    cooldown = Cooldown(seconds=3600)
    before = int(time.time())

    _set_skill_cooldown(player=player, skill_ref="warcry", cooldown=cooldown)

    after = int(time.time())
    expiry = player.skill_real_expiry["warcry"]
    assert before + 3600 <= expiry <= after + 3600


def test_skill_on_cooldown_true_within_real_window() -> None:
    """skill is on cooldown when now_ts < real_expiry."""
    player = _bare_player()
    # Plant a far-future expiry
    player.skill_real_expiry["warcry"] = int(time.time()) + 9999

    assert _skill_on_cooldown(player=player, skill_ref="warcry") is True


def test_skill_on_cooldown_false_after_real_expiry() -> None:
    """skill is not on cooldown when real_expiry is in the past."""
    player = _bare_player()
    # Plant an expiry 1 second in the past
    player.skill_real_expiry["warcry"] = int(time.time()) - 1

    assert _skill_on_cooldown(player=player, skill_ref="warcry") is False


# ---------------------------------------------------------------------------
# Combined ticks + seconds
# ---------------------------------------------------------------------------


def test_skill_on_cooldown_true_if_either_expiry_active() -> None:
    """Cooldown is considered active if either tick or real expiry is not yet met."""
    player = _bare_player()
    # Tick expiry in the past (met)
    player.internal_ticks = 20
    player.skill_tick_expiry["combo"] = 10

    # Real expiry in the future (not met)
    player.skill_real_expiry["combo"] = int(time.time()) + 9999

    assert _skill_on_cooldown(player=player, skill_ref="combo") is True


def test_skill_on_cooldown_false_when_both_expired() -> None:
    """Cooldown is cleared only when both expiry tracks are satisfied."""
    player = _bare_player()
    player.internal_ticks = 20
    player.skill_tick_expiry["combo"] = 10  # past
    player.skill_real_expiry["combo"] = int(time.time()) - 1  # past

    assert _skill_on_cooldown(player=player, skill_ref="combo") is False
