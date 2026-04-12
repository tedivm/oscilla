"""Unit tests for WebCallbacks and DecisionPauseException.

Tests cover: event queuing, sentinel placement, DecisionPauseException raising,
resume-mode short-circuit, session_output accumulation.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from oscilla.engine.web_callbacks import DecisionPauseException, WebCallbacks


def _make_cb(**kwargs: Any) -> WebCallbacks:
    return WebCallbacks(
        location_ref="test-loc",
        location_name="Test Location",
        region_name="Test Region",
        **kwargs,
    )


async def _drain_queue(cb: WebCallbacks) -> List[Dict[str, Any] | None]:
    """Drain the queue until it is empty and return all items."""
    items: List[Dict[str, Any] | None] = []
    while not cb.queue.empty():
        items.append(cb.queue.get_nowait())
    return items


# ---------------------------------------------------------------------------
# show_text
# ---------------------------------------------------------------------------


async def test_show_text_puts_narrative_event() -> None:
    """show_text puts a narrative event on the queue and appends to session_output."""
    cb = _make_cb()
    await cb.show_text("You open the door.")

    items = await _drain_queue(cb)
    assert len(items) == 1
    event = items[0]
    assert event is not None
    assert event["type"] == "narrative"
    assert event["data"]["text"] == "You open the door."
    assert len(cb.session_output) == 1


# ---------------------------------------------------------------------------
# show_menu
# ---------------------------------------------------------------------------


async def test_show_menu_puts_choice_event_and_raises() -> None:
    """show_menu puts a choice event and sentinel, then raises DecisionPauseException."""
    cb = _make_cb()
    with pytest.raises(DecisionPauseException):
        await cb.show_menu(prompt="What do you do?", options=["Fight", "Flee"])

    items = await _drain_queue(cb)
    assert len(items) == 2  # event + sentinel
    assert items[0] is not None
    assert items[0]["type"] == "choice"
    assert items[0]["data"]["options"] == ["Fight", "Flee"]
    assert items[1] is None  # sentinel
    assert len(cb.session_output) == 1  # sentinel not in session_output


async def test_show_menu_resume_mode_returns_choice_without_pausing() -> None:
    """show_menu in resume mode returns the choice without queuing events or raising."""
    cb = _make_cb(player_choice=2)
    result = await cb.show_menu(prompt="Choose:", options=["Option A", "Option B"])
    assert result == 2
    assert cb.queue.empty()
    assert len(cb.session_output) == 0
    # player_choice is consumed — next call would pause
    assert cb._player_choice is None


# ---------------------------------------------------------------------------
# wait_for_ack
# ---------------------------------------------------------------------------


async def test_wait_for_ack_puts_ack_event_and_raises() -> None:
    """wait_for_ack puts ack_required and sentinel, then raises DecisionPauseException."""
    cb = _make_cb()
    with pytest.raises(DecisionPauseException):
        await cb.wait_for_ack()

    items = await _drain_queue(cb)
    assert len(items) == 2
    assert items[0] is not None
    assert items[0]["type"] == "ack_required"
    assert items[1] is None
    assert len(cb.session_output) == 1


async def test_wait_for_ack_resume_mode_returns_without_pausing() -> None:
    """wait_for_ack in resume mode (player_ack=True) returns without pausing."""
    cb = _make_cb(player_ack=True)
    await cb.wait_for_ack()  # must not raise
    assert cb.queue.empty()
    assert len(cb.session_output) == 0


# ---------------------------------------------------------------------------
# input_text
# ---------------------------------------------------------------------------


async def test_input_text_puts_event_and_raises() -> None:
    """input_text puts text_input and sentinel, then raises DecisionPauseException."""
    cb = _make_cb()
    with pytest.raises(DecisionPauseException):
        await cb.input_text("What is your name?")

    items = await _drain_queue(cb)
    assert len(items) == 2
    assert items[0] is not None
    assert items[0]["type"] == "text_input"
    assert items[0]["data"]["prompt"] == "What is your name?"
    assert items[1] is None
    assert len(cb.session_output) == 1


async def test_input_text_resume_mode_returns_string() -> None:
    """input_text in resume mode returns the pre-loaded string without pausing."""
    cb = _make_cb(player_text_input="Aldric")
    result = await cb.input_text("What is your name?")
    assert result == "Aldric"
    assert cb.queue.empty()
    assert len(cb.session_output) == 0


# ---------------------------------------------------------------------------
# show_skill_menu
# ---------------------------------------------------------------------------


async def test_show_skill_menu_puts_event_and_raises() -> None:
    """show_skill_menu puts skill_menu and sentinel, then raises DecisionPauseException."""
    cb = _make_cb()
    skills = [{"ref": "fireball", "name": "Fireball", "description": "Burn things."}]
    with pytest.raises(DecisionPauseException):
        await cb.show_skill_menu(skills=skills)

    items = await _drain_queue(cb)
    assert len(items) == 2
    assert items[0] is not None
    assert items[0]["type"] == "skill_menu"
    assert items[0]["data"]["skills"] == skills
    assert items[1] is None
    assert len(cb.session_output) == 1


async def test_show_skill_menu_resume_mode_returns_choice() -> None:
    """show_skill_menu in resume mode returns the pre-loaded choice."""
    cb = _make_cb(player_skill_choice=1)
    skills = [{"ref": "fireball", "name": "Fireball", "description": "Burn things."}]
    result = await cb.show_skill_menu(skills=skills)
    assert result == 1
    assert cb.queue.empty()
    assert len(cb.session_output) == 0


# ---------------------------------------------------------------------------
# show_combat_round
# ---------------------------------------------------------------------------


async def test_show_combat_round_puts_combat_state_event() -> None:
    """show_combat_round puts a combat_state event with the correct fields."""
    cb = _make_cb()
    await cb.show_combat_round(
        player_hp=42,
        enemy_hp=18,
        player_name="Aldric",
        enemy_name="Goblin",
    )

    items = await _drain_queue(cb)
    assert len(items) == 1
    event = items[0]
    assert event is not None
    assert event["type"] == "combat_state"
    data = event["data"]
    assert data["player_hp"] == 42
    assert data["enemy_hp"] == 18
    assert data["player_name"] == "Aldric"
    assert data["enemy_name"] == "Goblin"
    assert len(cb.session_output) == 1


# ---------------------------------------------------------------------------
# session_output accumulation
# ---------------------------------------------------------------------------


async def test_session_output_contains_only_non_sentinel_events() -> None:
    """session_output contains exactly the non-sentinel events after a sequence of calls."""
    cb = _make_cb()
    await cb.show_text("Step 1.")
    await cb.show_text("Step 2.")
    await cb.show_combat_round(player_hp=10, enemy_hp=5, player_name="Hero", enemy_name="Rat")
    with pytest.raises(DecisionPauseException):
        await cb.show_menu(prompt="Choose:", options=["A", "B"])

    # The sentinel (None) must NOT be in session_output.
    assert len(cb.session_output) == 4
    types = [e["type"] for e in cb.session_output]
    assert types == ["narrative", "narrative", "combat_state", "choice"]
