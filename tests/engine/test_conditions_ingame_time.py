"""Tests for game_calendar_* condition predicates."""

from __future__ import annotations

from uuid import uuid4

from oscilla.engine.character import CharacterState
from oscilla.engine.conditions import evaluate
from oscilla.engine.ingame_time import InGameTimeResolver
from oscilla.engine.loader import compute_epoch_offset
from oscilla.engine.models.base import GameCalendarCycleCondition, GameCalendarEraCondition, GameCalendarTimeCondition
from oscilla.engine.models.time import EraSpec, GameTimeSpec, RootCycleSpec
from oscilla.engine.registry import ContentRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _player(
    game_ticks: int = 0,
    internal_ticks: int = 0,
    level: int = 1,
) -> CharacterState:
    p = CharacterState(
        character_id=uuid4(),
        name="Tester",
        character_class=None,
        level=level,
        xp=0,
        hp=20,
        max_hp=20,
        iteration=0,
        current_location=None,
        stats={},
    )
    p.game_ticks = game_ticks
    p.internal_ticks = internal_ticks
    return p


def _time_registry(
    game_ticks_player: int = 0, internal_ticks_player: int = 0
) -> tuple[ContentRegistry, CharacterState]:
    """Build a ContentRegistry with a real ingame_time_resolver and a matching player."""
    from oscilla.engine.models.base import Metadata
    from oscilla.engine.models.game import GameManifest, GameSpec
    from oscilla.engine.models.time import DerivedCycleSpec

    spec = GameTimeSpec(
        cycles=[
            RootCycleSpec(
                type="ticks",
                name="tick",
            ),
            DerivedCycleSpec(
                type="cycle",
                name="hour",
                parent="tick",
                count=4,
                labels=["Dawn", "Noon", "Dusk", "Midnight"],
            ),
            DerivedCycleSpec(
                type="cycle",
                name="day",
                parent="hour",
                count=3,
                labels=["Mon", "Tue", "Wed"],
            ),
        ],
        epoch={},
        eras=[
            EraSpec(
                name="golden-age",
                format="Year {count}",
                epoch_count=1,
                tracks="day",
                # No start_condition → always active
            ),
            EraSpec(
                name="shadow-age",
                format="Shadow {count}",
                epoch_count=1,
                tracks="day",
                start_condition={"type": "level", "value": 5},
            ),
        ],
    )
    game_spec = GameSpec(
        displayName="Test Time Game",
        xp_thresholds=[0, 100],
        hp_formula={"base_hp": 20, "hp_per_level": 5},
        time=spec,
    )
    game_manifest = GameManifest(
        apiVersion="game/v1",
        kind="Game",
        metadata=Metadata(name="test-time-game"),
        spec=game_spec,
    )
    registry = ContentRegistry.build(manifests=[game_manifest])
    # Manually attach resolver (mirrors what registry.build does when game has time)
    epoch_offset = compute_epoch_offset(spec)
    registry._ingame_time_resolver = InGameTimeResolver(spec=spec, epoch_offset=epoch_offset)
    player = _player(game_ticks=game_ticks_player, internal_ticks=internal_ticks_player)
    return registry, player


# ---------------------------------------------------------------------------
# GameCalendarTimeCondition — internal clock
# ---------------------------------------------------------------------------


def test_time_condition_internal_gte_pass() -> None:
    registry, player = _time_registry(internal_ticks_player=10)
    cond = GameCalendarTimeCondition(type="game_calendar_time_is", clock="internal", gte=10)
    assert evaluate(cond, player=player, registry=registry) is True


def test_time_condition_internal_gte_fail() -> None:
    registry, player = _time_registry(internal_ticks_player=9)
    cond = GameCalendarTimeCondition(type="game_calendar_time_is", clock="internal", gte=10)
    assert evaluate(cond, player=player, registry=registry) is False


def test_time_condition_internal_gt_pass() -> None:
    registry, player = _time_registry(internal_ticks_player=11)
    cond = GameCalendarTimeCondition(type="game_calendar_time_is", clock="internal", gt=10)
    assert evaluate(cond, player=player, registry=registry) is True


def test_time_condition_internal_gt_fail_at_boundary() -> None:
    registry, player = _time_registry(internal_ticks_player=10)
    cond = GameCalendarTimeCondition(type="game_calendar_time_is", clock="internal", gt=10)
    assert evaluate(cond, player=player, registry=registry) is False


def test_time_condition_internal_lt_pass() -> None:
    registry, player = _time_registry(internal_ticks_player=5)
    cond = GameCalendarTimeCondition(type="game_calendar_time_is", clock="internal", lt=10)
    assert evaluate(cond, player=player, registry=registry) is True


def test_time_condition_internal_eq_pass() -> None:
    registry, player = _time_registry(internal_ticks_player=7)
    cond = GameCalendarTimeCondition(type="game_calendar_time_is", clock="internal", eq=7)
    assert evaluate(cond, player=player, registry=registry) is True


def test_time_condition_internal_eq_fail() -> None:
    registry, player = _time_registry(internal_ticks_player=8)
    cond = GameCalendarTimeCondition(type="game_calendar_time_is", clock="internal", eq=7)
    assert evaluate(cond, player=player, registry=registry) is False


# ---------------------------------------------------------------------------
# GameCalendarTimeCondition — game clock
# ---------------------------------------------------------------------------


def test_time_condition_game_clock_gte_pass() -> None:
    registry, player = _time_registry(game_ticks_player=20)
    cond = GameCalendarTimeCondition(type="game_calendar_time_is", clock="game", gte=20)
    assert evaluate(cond, player=player, registry=registry) is True


def test_time_condition_game_clock_uses_game_ticks_not_internal() -> None:
    """Ensure game clock uses game_ticks, not internal_ticks."""
    registry, player = _time_registry(game_ticks_player=5, internal_ticks_player=100)
    cond = GameCalendarTimeCondition(type="game_calendar_time_is", clock="game", gte=10)
    # game_ticks=5 < 10 → False even though internal_ticks=100 would pass
    assert evaluate(cond, player=player, registry=registry) is False


def test_time_condition_internal_clock_uses_internal_ticks_not_game() -> None:
    """Ensure internal clock uses internal_ticks, not game_ticks."""
    registry, player = _time_registry(game_ticks_player=100, internal_ticks_player=5)
    cond = GameCalendarTimeCondition(type="game_calendar_time_is", clock="internal", gte=10)
    # internal_ticks=5 < 10 → False even though game_ticks=100 would pass
    assert evaluate(cond, player=player, registry=registry) is False


# ---------------------------------------------------------------------------
# GameCalendarCycleCondition
# ---------------------------------------------------------------------------


def test_cycle_condition_pass_on_matching_label() -> None:
    """At tick 1 the hour cycle is 'Noon'; condition testing for Noon should pass."""
    registry, player = _time_registry(game_ticks_player=1)
    cond = GameCalendarCycleCondition(type="game_calendar_cycle_is", cycle="hour", value="Noon")
    assert evaluate(cond, player=player, registry=registry) is True


def test_cycle_condition_fail_on_mismatched_label() -> None:
    """At tick 1 the hour cycle is 'Noon'; condition testing for Dawn should fail."""
    registry, player = _time_registry(game_ticks_player=1)
    cond = GameCalendarCycleCondition(type="game_calendar_cycle_is", cycle="hour", value="Dawn")
    assert evaluate(cond, player=player, registry=registry) is False


def test_cycle_condition_pass_on_derived_cycle() -> None:
    """At tick 8 the day cycle is 'Wed'.

    With hour.count=4 (parent=tick) and day.count=3 (parent=hour):
    ticks_per_hour=4, ticks_per_day=12. position=(8//4)%3=2 → 'Wed'.
    """
    registry, player = _time_registry(game_ticks_player=8)
    cond = GameCalendarCycleCondition(type="game_calendar_cycle_is", cycle="day", value="Wed")
    assert evaluate(cond, player=player, registry=registry) is True


def test_cycle_condition_unknown_cycle_returns_false() -> None:
    """Unknown cycle name → returns False with warning (no registry lookup)."""
    registry, player = _time_registry()
    cond = GameCalendarCycleCondition(type="game_calendar_cycle_is", cycle="nonexistent", value="Whatever")
    result = evaluate(cond, player=player, registry=registry)
    assert result is False


def test_cycle_condition_returns_false_without_time_system() -> None:
    """Condition returns False when registry has no ingame_time_resolver."""
    registry = ContentRegistry()  # no game manifest, no resolver
    player = _player()
    cond = GameCalendarCycleCondition(type="game_calendar_cycle_is", cycle="hour", value="Dawn")
    assert evaluate(cond, player=player, registry=registry) is False


# ---------------------------------------------------------------------------
# GameCalendarEraCondition
# ---------------------------------------------------------------------------


def test_era_condition_active_always_active_era() -> None:
    """golden-age has no start_condition → always active → 'active' condition passes."""
    registry, player = _time_registry()
    cond = GameCalendarEraCondition(type="game_calendar_era_is", era="golden-age", state="active")
    assert evaluate(cond, player=player, registry=registry) is True


def test_era_condition_inactive_always_active_era() -> None:
    """golden-age is always active → 'inactive' condition fails."""
    registry, player = _time_registry()
    cond = GameCalendarEraCondition(type="game_calendar_era_is", era="golden-age", state="inactive")
    assert evaluate(cond, player=player, registry=registry) is False


def test_era_condition_active_conditional_era_not_started() -> None:
    """shadow-age requires level 5; player is level 1 → not active → 'active' fails."""
    registry, player = _time_registry()
    # player level = 1, era start_condition = level 5 → era never started
    cond = GameCalendarEraCondition(type="game_calendar_era_is", era="shadow-age", state="active")
    assert evaluate(cond, player=player, registry=registry) is False


def test_era_condition_inactive_conditional_era_not_started() -> None:
    """shadow-age not started → 'inactive' condition passes."""
    registry, player = _time_registry()
    cond = GameCalendarEraCondition(type="game_calendar_era_is", era="shadow-age", state="inactive")
    assert evaluate(cond, player=player, registry=registry) is True


def test_era_condition_active_after_latch() -> None:
    """shadow-age active once era_started_at_ticks is set."""
    registry, player = _time_registry()
    player.era_started_at_ticks["shadow-age"] = 0
    cond = GameCalendarEraCondition(type="game_calendar_era_is", era="shadow-age", state="active")
    assert evaluate(cond, player=player, registry=registry) is True


def test_era_condition_unknown_era_returns_false() -> None:
    """Unknown era name → returns False."""
    registry, player = _time_registry()
    cond = GameCalendarEraCondition(type="game_calendar_era_is", era="nonexistent", state="active")
    assert evaluate(cond, player=player, registry=registry) is False


def test_era_condition_returns_false_without_time_system() -> None:
    """Condition returns False when registry has no ingame_time_resolver."""
    registry = ContentRegistry()  # no game manifest, no resolver
    player = _player()
    cond = GameCalendarEraCondition(type="game_calendar_era_is", era="golden-age", state="active")
    assert evaluate(cond, player=player, registry=registry) is False
