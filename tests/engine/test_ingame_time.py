"""Unit tests for InGameTimeResolver and compute_epoch_offset."""

from __future__ import annotations

from uuid import uuid4

from oscilla.engine.character import CharacterState
from oscilla.engine.ingame_time import InGameTimeResolver
from oscilla.engine.loader import compute_epoch_offset
from oscilla.engine.models.time import DerivedCycleSpec, EraSpec, GameTimeSpec, RootCycleSpec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _root(name: str, aliases: list[str] | None = None) -> RootCycleSpec:
    return RootCycleSpec(
        type="ticks",
        name=name,
        aliases=aliases or [],
    )


def _derived(
    name: str,
    parent: str,
    count: int,
    labels: list[str] | None = None,
    aliases: list[str] | None = None,
) -> DerivedCycleSpec:
    return DerivedCycleSpec(
        type="cycle",
        name=name,
        parent=parent,
        count=count,
        labels=labels or [],
        aliases=aliases or [],
    )


def _spec(
    *cycles: RootCycleSpec | DerivedCycleSpec, epoch: dict | None = None, eras: list | None = None
) -> GameTimeSpec:
    return GameTimeSpec(cycles=list(cycles), epoch=epoch or {}, eras=eras or [])


def _resolver(spec: GameTimeSpec, epoch_offset: int = 0) -> InGameTimeResolver:
    return InGameTimeResolver(spec=spec, epoch_offset=epoch_offset)


def _player() -> CharacterState:
    return CharacterState(
        character_id=uuid4(),
        name="Tester",
        prestige_count=0,
        stats={},
    )


# ---------------------------------------------------------------------------
# Root cycle label resolution
# ---------------------------------------------------------------------------


def test_root_cycle_position_wraps() -> None:
    """Derived hour cycle position wraps after count parent ticks."""
    spec = _spec(_root("tick"), _derived("hour", parent="tick", count=4, labels=["Dawn", "Noon", "Dusk", "Midnight"]))
    resolver = _resolver(spec)
    view0 = resolver.resolve(game_ticks=0, internal_ticks=0, player=_player(), registry=None)
    view4 = resolver.resolve(game_ticks=4, internal_ticks=4, player=_player(), registry=None)
    assert view0.cycles["hour"].label == "Dawn"
    assert view4.cycles["hour"].label == "Dawn"


def test_root_cycle_all_labels() -> None:
    """Each tick within one full cycle maps to the correct label."""
    spec = _spec(_root("tick"), _derived("hour", parent="tick", count=4, labels=["Dawn", "Noon", "Dusk", "Midnight"]))
    resolver = _resolver(spec)
    expected = ["Dawn", "Noon", "Dusk", "Midnight"]
    for tick, label in enumerate(expected):
        view = resolver.resolve(game_ticks=tick, internal_ticks=0, player=_player(), registry=None)
        assert view.cycles["hour"].label == label, f"tick={tick}"


def test_root_cycle_no_labels_uses_default() -> None:
    """When no labels are declared, cycle displays as 'name N' (1-based)."""
    spec = _spec(_root("tick"), _derived("hour", parent="tick", count=4))
    resolver = _resolver(spec)
    view = resolver.resolve(game_ticks=0, internal_ticks=0, player=_player(), registry=None)
    assert view.cycles["hour"].label == "hour 1"
    view2 = resolver.resolve(game_ticks=1, internal_ticks=0, player=_player(), registry=None)
    assert view2.cycles["hour"].label == "hour 2"


def test_root_cycle_position_field() -> None:
    """CycleState.position is the 0-based index."""
    spec = _spec(_root("tick"), _derived("hour", parent="tick", count=4, labels=["Dawn", "Noon", "Dusk", "Midnight"]))
    resolver = _resolver(spec)
    view = resolver.resolve(game_ticks=1, internal_ticks=0, player=_player(), registry=None)
    assert view.cycles["hour"].position == 1


# ---------------------------------------------------------------------------
# Derived cycle advancement
# ---------------------------------------------------------------------------


def test_derived_cycle_advances_with_parent_ticks() -> None:
    """A day (3 hours) advances every 12 ticks (3 × 4) and cycles through 3 positions."""
    tick_root = _root("tick")
    hour = _derived("hour", parent="tick", count=4, labels=["Dawn", "Noon", "Dusk", "Midnight"])
    day = _derived("day", parent="hour", count=3, labels=["Mon", "Tue", "Wed"])
    spec = _spec(tick_root, hour, day)
    resolver = _resolver(spec)

    # 12 ticks = one full day cycle (4 ticks/hour × 3 hours/day)
    # Sample one tick per hour-slot: 0, 4, 8, 12, 16, 20
    labels_at_tick = [
        resolver.resolve(game_ticks=t, internal_ticks=0, player=_player(), registry=None).cycles["day"].label
        for t in range(0, 24, 4)
    ]
    assert labels_at_tick == ["Mon", "Tue", "Wed", "Mon", "Tue", "Wed"]


def test_derived_cycle_position_field() -> None:
    tick_root = _root("tick")
    hour = _derived("hour", parent="tick", count=4)
    day = _derived("day", parent="hour", count=3, labels=["Mon", "Tue", "Wed"])
    spec = _spec(tick_root, hour, day)
    resolver = _resolver(spec)
    # tick 8: day position = (8 // 4) % 3 = 2 → "Wed"
    view = resolver.resolve(game_ticks=8, internal_ticks=0, player=_player(), registry=None)
    assert view.cycles["day"].position == 2
    assert view.cycles["day"].label == "Wed"


# ---------------------------------------------------------------------------
# Alias resolution
# ---------------------------------------------------------------------------


def test_alias_resolution_in_view() -> None:
    """Cycles accessible by alias in the resolved InGameTimeView.cycles dict."""
    spec = _spec(
        _root("tick"),
        _derived("hour", parent="tick", count=4, labels=["Dawn", "Noon", "Dusk", "Midnight"], aliases=["hr"]),
    )
    resolver = _resolver(spec)
    view = resolver.resolve(game_ticks=1, internal_ticks=0, player=_player(), registry=None)
    # Both canonical name and alias should resolve to the same CycleState
    assert view.cycles["hour"].label == "Noon"
    assert view.cycles["hr"].label == "Noon"


# ---------------------------------------------------------------------------
# Epoch offset
# ---------------------------------------------------------------------------


def test_compute_epoch_offset_no_epoch() -> None:
    """Returns 0 when no epoch is configured."""
    spec = _spec(_root("tick"), _derived("hour", parent="tick", count=4, labels=["Dawn", "Noon", "Dusk", "Midnight"]))
    assert compute_epoch_offset(spec) == 0


def test_compute_epoch_offset_integer_first_position() -> None:
    """1-based integer 1 → idx 0 → offset 0."""
    spec = _spec(
        _root("tick"),
        _derived("hour", parent="tick", count=4, labels=["Dawn", "Noon", "Dusk", "Midnight"]),
        epoch={"hour": 1},
    )
    assert compute_epoch_offset(spec) == 0


def test_compute_epoch_offset_integer_second_position() -> None:
    """1-based integer 2 → idx 1 → offset 1 tick (idx × ticks_per_parent)."""
    spec = _spec(
        _root("tick"),
        _derived("hour", parent="tick", count=4, labels=["Dawn", "Noon", "Dusk", "Midnight"]),
        epoch={"hour": 2},
    )
    assert compute_epoch_offset(spec) == 1


def test_compute_epoch_offset_label() -> None:
    """Label 'Dusk' is at index 2 → offset 2 ticks (idx × ticks_per_parent)."""
    spec = _spec(
        _root("tick"),
        _derived("hour", parent="tick", count=4, labels=["Dawn", "Noon", "Dusk", "Midnight"]),
        epoch={"hour": "Dusk"},
    )
    assert compute_epoch_offset(spec) == 2


def test_epoch_offset_shifts_display_position() -> None:
    """game_ticks=0 with epoch offset Noon (idx=1) displays 'Noon', not 'Dawn'."""
    spec = _spec(
        _root("tick"),
        _derived("hour", parent="tick", count=4, labels=["Dawn", "Noon", "Dusk", "Midnight"]),
        epoch={"hour": "Noon"},
    )
    offset = compute_epoch_offset(spec)
    resolver = _resolver(spec, epoch_offset=offset)
    view = resolver.resolve(game_ticks=0, internal_ticks=0, player=_player(), registry=None)
    assert view.cycles["hour"].label == "Noon"


def test_epoch_offset_derived_cycle() -> None:
    """Epoch 'Tue' for a derived day cycle (idx=1, tpu_parent=4) offsets by 4."""
    tick_root = _root("tick")
    hour = _derived("hour", parent="tick", count=4, labels=["Dawn", "Noon", "Dusk", "Midnight"])
    day = _derived("day", parent="hour", count=3, labels=["Mon", "Tue", "Wed"])
    spec = _spec(tick_root, hour, day, epoch={"day": "Tue"})
    offset = compute_epoch_offset(spec)
    # idx=1 for "Tue"; ticks_per_unit["hour"]=4 → offset = 1 × 4 = 4
    assert offset == 4
    resolver = _resolver(spec, epoch_offset=offset)
    view = resolver.resolve(game_ticks=0, internal_ticks=0, player=_player(), registry=None)
    assert view.cycles["day"].label == "Tue"


# ---------------------------------------------------------------------------
# Era count progression
# ---------------------------------------------------------------------------


def test_era_count_starts_at_epoch_count() -> None:
    """Always-active era count equals epoch_count before any tracked cycle completes."""
    hour = _root("hour")
    day = _derived("day", parent="hour", count=3)
    # ticks_per_unit["day"] = 3 * ticks_per_unit["hour"] = 3 * 1 = 3
    era = EraSpec(name="year", format="{count} AC", epoch_count=5, tracks="day")
    spec = _spec(hour, day, eras=[era])
    resolver = _resolver(spec)
    player = _player()
    view = resolver.resolve(game_ticks=0, internal_ticks=0, player=player, registry=None)
    assert view.eras["year"].count == 5
    assert view.eras["year"].active is True


def test_era_count_increments_on_cycle_completion() -> None:
    """Era count increments by 1 for each full tracked cycle completed."""
    hour = _root("hour")
    day = _derived("day", parent="hour", count=3)
    era = EraSpec(name="year", format="{count} AC", epoch_count=1, tracks="day")
    spec = _spec(hour, day, eras=[era])
    resolver = _resolver(spec)
    player = _player()
    # ticks_per_unit["day"] = 3 × ticks_per_unit["hour"] = 3 × 1 = 3
    view3 = resolver.resolve(game_ticks=3, internal_ticks=0, player=player, registry=None)
    view6 = resolver.resolve(game_ticks=6, internal_ticks=0, player=player, registry=None)
    assert view3.eras["year"].count == 2  # 1 + 1 completed day
    assert view6.eras["year"].count == 3  # 1 + 2 completed days


# ---------------------------------------------------------------------------
# Era activation / deactivation
# ---------------------------------------------------------------------------


def test_era_not_active_before_start_condition() -> None:
    """Era with start_condition is inactive when era_started_at_ticks is absent."""
    hour = _root("hour")
    era = EraSpec(
        name="bronze-age",
        format="Bronze Age {count}",
        epoch_count=1,
        tracks="hour",
        start_condition={"type": "level", "value": 3},
    )
    spec = _spec(hour, eras=[era])
    resolver = _resolver(spec)
    player = _player()
    view = resolver.resolve(game_ticks=100, internal_ticks=100, player=player, registry=None)
    assert view.eras["bronze-age"].active is False


def test_era_active_after_start_latch() -> None:
    """Era is active once era_started_at_ticks is populated."""
    hour = _root("hour")
    era = EraSpec(
        name="bronze-age",
        format="Bronze Age {count}",
        epoch_count=1,
        tracks="hour",
        start_condition={"type": "level", "value": 3},
    )
    spec = _spec(hour, eras=[era])
    resolver = _resolver(spec)
    player = _player()
    # Simulate the latch being set (would normally happen in update_era_states)
    player.era_started_at_ticks["bronze-age"] = 10
    view = resolver.resolve(game_ticks=10, internal_ticks=10, player=player, registry=None)
    assert view.eras["bronze-age"].active is True


def test_era_inactive_after_end_latch() -> None:
    """Era is inactive once era_ended_at_ticks is populated."""
    hour = _root("hour")
    era = EraSpec(
        name="bronze-age",
        format="Bronze Age {count}",
        epoch_count=1,
        tracks="hour",
        end_condition={"type": "level", "value": 5},
    )
    spec = _spec(hour, eras=[era])
    resolver = _resolver(spec)
    player = _player()
    # No start_condition → always started
    player.era_ended_at_ticks["bronze-age"] = 20
    view = resolver.resolve(game_ticks=25, internal_ticks=25, player=player, registry=None)
    assert view.eras["bronze-age"].active is False


# ---------------------------------------------------------------------------
# InGameTimeView helper accessors
# ---------------------------------------------------------------------------


def test_view_cycle_accessor_returns_none_for_unknown() -> None:
    spec = _spec(_root("hour"))
    resolver = _resolver(spec)
    view = resolver.resolve(game_ticks=0, internal_ticks=0, player=_player(), registry=None)
    assert view.cycle("nonexistent") is None


def test_view_era_accessor_returns_none_for_unknown() -> None:
    spec = _spec(_root("hour"))
    resolver = _resolver(spec)
    view = resolver.resolve(game_ticks=0, internal_ticks=0, player=_player(), registry=None)
    assert view.era("nonexistent") is None


def test_view_cycle_accessor_returns_state() -> None:
    spec = _spec(_root("tick"), _derived("hour", parent="tick", count=4, labels=["Dawn", "Noon", "Dusk", "Midnight"]))
    resolver = _resolver(spec)
    view = resolver.resolve(game_ticks=1, internal_ticks=0, player=_player(), registry=None)
    state = view.cycle("hour")
    assert state is not None
    assert state.label == "Noon"
