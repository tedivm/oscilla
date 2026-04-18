"""Tests for calendar condition predicates in the condition evaluator."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from oscilla.engine.character import CharacterState
from oscilla.engine.conditions import evaluate
from oscilla.engine.models.base import (
    AllCondition,
    ChineseZodiacIsCondition,
    DateBetweenCondition,
    DateIsCondition,
    DayOfWeekIsCondition,
    MonthIsCondition,
    MoonPhaseIsCondition,
    NotCondition,
    SeasonIsCondition,
    TimeBetweenCondition,
    ZodiacIsCondition,
)
from oscilla.engine.registry import ContentRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player() -> CharacterState:
    return CharacterState(
        character_id=uuid4(),
        name="Tester",
        prestige_count=0,
        stats={},
    )


def _make_registry(season_hemisphere: str = "northern", timezone: str | None = None) -> ContentRegistry:
    """Build a minimal ContentRegistry with a mocked game spec for hemisphere/timezone control."""
    registry = ContentRegistry()
    game_spec = MagicMock()
    game_spec.season_hemisphere = season_hemisphere
    game_spec.timezone = timezone
    game_manifest = MagicMock()
    game_manifest.spec = game_spec
    registry.game = game_manifest
    return registry


def _freeze_dt(monkeypatch: Any, year: int, month: int, day: int, hour: int = 14, minute: int = 0) -> None:
    """Patch calendar_utils.resolve_local_datetime to return a fixed datetime."""
    fixed = datetime.datetime(year, month, day, hour, minute)
    monkeypatch.setattr(
        "oscilla.engine.calendar_utils.resolve_local_datetime",
        lambda tz_name: fixed,
    )


# ---------------------------------------------------------------------------
# SeasonIsCondition
# ---------------------------------------------------------------------------


def test_season_is_true(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 7, 15)  # July = summer (northern)
    cond = SeasonIsCondition(type="season_is", value="summer")
    assert evaluate(cond, _make_player()) is True


def test_season_is_false(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 7, 15)  # July = summer, not winter
    cond = SeasonIsCondition(type="season_is", value="winter")
    assert evaluate(cond, _make_player()) is False


def test_season_is_southern_hemisphere(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 7, 15)  # July = winter in southern hemisphere
    cond = SeasonIsCondition(type="season_is", value="winter")
    registry = _make_registry(season_hemisphere="southern")
    assert evaluate(cond, _make_player(), registry=registry) is True


# ---------------------------------------------------------------------------
# MoonPhaseIsCondition — April 5, 2026 = Full Moon
# ---------------------------------------------------------------------------


def test_moon_phase_is_true(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 4, 5)
    cond = MoonPhaseIsCondition(type="moon_phase_is", value="Full Moon")
    assert evaluate(cond, _make_player()) is True


def test_moon_phase_is_false(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 4, 5)
    cond = MoonPhaseIsCondition(type="moon_phase_is", value="New Moon")
    assert evaluate(cond, _make_player()) is False


# ---------------------------------------------------------------------------
# ZodiacIsCondition — April 5, 2026 = Aries
# ---------------------------------------------------------------------------


def test_zodiac_is_true(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 4, 5)
    cond = ZodiacIsCondition(type="zodiac_is", value="Aries")
    assert evaluate(cond, _make_player()) is True


def test_zodiac_is_false(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 4, 5)
    cond = ZodiacIsCondition(type="zodiac_is", value="Taurus")
    assert evaluate(cond, _make_player()) is False


# ---------------------------------------------------------------------------
# ChineseZodiacIsCondition — 2026 = Horse
# ---------------------------------------------------------------------------


def test_chinese_zodiac_is_true(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 4, 5)
    cond = ChineseZodiacIsCondition(type="chinese_zodiac_is", value="Horse")
    assert evaluate(cond, _make_player()) is True


def test_chinese_zodiac_is_false(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 4, 5)
    cond = ChineseZodiacIsCondition(type="chinese_zodiac_is", value="Rat")
    assert evaluate(cond, _make_player()) is False


# ---------------------------------------------------------------------------
# MonthIsCondition
# ---------------------------------------------------------------------------


def test_month_is_integer_true(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 10, 31)
    cond = MonthIsCondition(type="month_is", value=10)
    assert evaluate(cond, _make_player()) is True


def test_month_is_integer_false(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 10, 31)
    cond = MonthIsCondition(type="month_is", value=12)
    assert evaluate(cond, _make_player()) is False


def test_month_is_string_true(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 10, 31)
    cond = MonthIsCondition(type="month_is", value="October")
    assert evaluate(cond, _make_player()) is True


def test_month_is_string_false(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 10, 31)
    cond = MonthIsCondition(type="month_is", value="December")
    assert evaluate(cond, _make_player()) is False


def test_month_is_invalid_string_raises() -> None:
    with pytest.raises(ValueError, match="Unrecognized month name"):
        MonthIsCondition(type="month_is", value="Octobr")


# ---------------------------------------------------------------------------
# DayOfWeekIsCondition — April 6, 2026 = Monday (weekday 0)
# ---------------------------------------------------------------------------


def test_day_of_week_is_integer_true(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 4, 6)  # Monday
    cond = DayOfWeekIsCondition(type="day_of_week_is", value=0)
    assert evaluate(cond, _make_player()) is True


def test_day_of_week_is_integer_false(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 4, 6)  # Monday, not Tuesday
    cond = DayOfWeekIsCondition(type="day_of_week_is", value=1)
    assert evaluate(cond, _make_player()) is False


def test_day_of_week_is_string_true(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 4, 6)  # Monday
    cond = DayOfWeekIsCondition(type="day_of_week_is", value="Monday")
    assert evaluate(cond, _make_player()) is True


def test_day_of_week_is_string_false(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 4, 6)  # Monday, not Friday
    cond = DayOfWeekIsCondition(type="day_of_week_is", value="Friday")
    assert evaluate(cond, _make_player()) is False


# ---------------------------------------------------------------------------
# DateIsCondition
# ---------------------------------------------------------------------------


def test_date_is_annual_true(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 12, 25)
    cond = DateIsCondition(type="date_is", month=12, day=25)
    assert evaluate(cond, _make_player()) is True


def test_date_is_annual_false(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 12, 24)
    cond = DateIsCondition(type="date_is", month=12, day=25)
    assert evaluate(cond, _make_player()) is False


def test_date_is_with_year_true(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 12, 25)
    cond = DateIsCondition(type="date_is", month=12, day=25, year=2026)
    assert evaluate(cond, _make_player()) is True


def test_date_is_with_year_false_wrong_year(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2027, 12, 25)
    cond = DateIsCondition(type="date_is", month=12, day=25, year=2026)
    assert evaluate(cond, _make_player()) is False


# ---------------------------------------------------------------------------
# TimeBetweenCondition
# ---------------------------------------------------------------------------


def test_time_between_same_day_window_inside(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 4, 5, hour=15, minute=0)  # 15:00
    cond = TimeBetweenCondition(type="time_between", start="10:00", end="18:00")
    assert evaluate(cond, _make_player()) is True


def test_time_between_same_day_window_outside(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 4, 5, hour=20, minute=0)  # 20:00
    cond = TimeBetweenCondition(type="time_between", start="10:00", end="18:00")
    assert evaluate(cond, _make_player()) is False


def test_time_between_midnight_wrap_true_after_start(monkeypatch: Any) -> None:
    # 23:30 is in the wrapping window 22:00-04:00 (after start)
    _freeze_dt(monkeypatch, 2026, 4, 5, hour=23, minute=30)
    cond = TimeBetweenCondition(type="time_between", start="22:00", end="04:00")
    assert evaluate(cond, _make_player()) is True


def test_time_between_midnight_wrap_true_before_end(monkeypatch: Any) -> None:
    # 02:00 is in the wrapping window 22:00-04:00 (before end)
    _freeze_dt(monkeypatch, 2026, 4, 5, hour=2, minute=0)
    cond = TimeBetweenCondition(type="time_between", start="22:00", end="04:00")
    assert evaluate(cond, _make_player()) is True


def test_time_between_midnight_wrap_false_in_gap(monkeypatch: Any) -> None:
    # 12:00 is outside the wrapping window 22:00-04:00
    _freeze_dt(monkeypatch, 2026, 4, 5, hour=12, minute=0)
    cond = TimeBetweenCondition(type="time_between", start="22:00", end="04:00")
    assert evaluate(cond, _make_player()) is False


def test_time_between_zero_duration_false(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 4, 5, hour=12, minute=0)
    cond = TimeBetweenCondition(type="time_between", start="12:00", end="12:00")
    assert evaluate(cond, _make_player()) is False


# ---------------------------------------------------------------------------
# DateBetweenCondition
# ---------------------------------------------------------------------------


def _make_date_between(
    start_month: int | str, start_day: int, end_month: int | str, end_day: int
) -> DateBetweenCondition:
    return DateBetweenCondition(
        type="date_between",
        start={"month": start_month, "day": start_day},
        end={"month": end_month, "day": end_day},
    )


def test_date_between_normal_window_pass(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 6, 15)  # June 15 in window Apr–Sep
    cond = _make_date_between(4, 1, 9, 30)
    assert evaluate(cond, _make_player()) is True


def test_date_between_normal_window_fail(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 11, 1)  # November 1 outside window Apr–Sep
    cond = _make_date_between(4, 1, 9, 30)
    assert evaluate(cond, _make_player()) is False


def test_date_between_start_boundary(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 4, 1)  # Exactly on start boundary
    cond = _make_date_between(4, 1, 9, 30)
    assert evaluate(cond, _make_player()) is True


def test_date_between_end_boundary(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 9, 30)  # Exactly on end boundary
    cond = _make_date_between(4, 1, 9, 30)
    assert evaluate(cond, _make_player()) is True


def test_date_between_year_wrap_pass_after_start(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 12, 15)  # December is in Dec 1 – Jan 31 window
    cond = _make_date_between(12, 1, 1, 31)
    assert evaluate(cond, _make_player()) is True


def test_date_between_year_wrap_pass_before_end(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 1, 15)  # January is in Dec 1 – Jan 31 window
    cond = _make_date_between(12, 1, 1, 31)
    assert evaluate(cond, _make_player()) is True


def test_date_between_year_wrap_fail_in_gap(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 6, 15)  # June is outside Dec 1 – Jan 31 window
    cond = _make_date_between(12, 1, 1, 31)
    assert evaluate(cond, _make_player()) is False


def test_date_between_zero_duration_always_false(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 12, 25)  # Same date as start == end
    cond = _make_date_between(12, 25, 12, 25)
    assert evaluate(cond, _make_player()) is False


def test_date_between_string_month_names(monkeypatch: Any) -> None:
    _freeze_dt(monkeypatch, 2026, 7, 4)  # July 4 in June–August window
    cond = _make_date_between("June", 1, "August", 31)
    assert evaluate(cond, _make_player()) is True


# ---------------------------------------------------------------------------
# Composition test: AllCondition with calendar conditions
# ---------------------------------------------------------------------------


def test_calendar_conditions_compose_with_all(monkeypatch: Any) -> None:
    # October 15, 2026 = Waxing Crescent moon; month 10
    _freeze_dt(monkeypatch, 2026, 10, 15)
    cond = AllCondition(
        type="all",
        conditions=[
            MonthIsCondition(type="month_is", value=10),
            MoonPhaseIsCondition(type="moon_phase_is", value="Waxing Crescent"),
        ],
    )
    assert evaluate(cond, _make_player()) is True


def test_calendar_conditions_compose_with_all_false(monkeypatch: Any) -> None:
    # October 15 is month 10 but not November
    _freeze_dt(monkeypatch, 2026, 10, 15)
    cond = AllCondition(
        type="all",
        conditions=[
            MonthIsCondition(type="month_is", value=11),
            MoonPhaseIsCondition(type="moon_phase_is", value="Waxing Crescent"),
        ],
    )
    assert evaluate(cond, _make_player()) is False


# ---------------------------------------------------------------------------
# NotCondition wrapping a calendar predicate (W2)
# ---------------------------------------------------------------------------


def test_calendar_predicate_under_not(monkeypatch: Any) -> None:
    # July = month 7, which is not 10, so not(month_is: 10) is True.
    _freeze_dt(monkeypatch, 2026, 7, 15)
    cond = NotCondition(
        type="not",
        condition=MonthIsCondition(type="month_is", value=10),
    )
    assert evaluate(cond, _make_player()) is True


def test_calendar_predicate_under_not_false(monkeypatch: Any) -> None:
    # October = month 10, so not(month_is: 10) is False.
    _freeze_dt(monkeypatch, 2026, 10, 15)
    cond = NotCondition(
        type="not",
        condition=MonthIsCondition(type="month_is", value=10),
    )
    assert evaluate(cond, _make_player()) is False


# ---------------------------------------------------------------------------
# season_is defaults to northern hemisphere when no registry provided (S1)
# ---------------------------------------------------------------------------


def test_season_is_defaults_to_northern_without_registry(monkeypatch: Any) -> None:
    # July = summer in the northern hemisphere.
    # Passing no registry should default to northern, so summer is True.
    _freeze_dt(monkeypatch, 2026, 7, 15)
    cond = SeasonIsCondition(type="season_is", value="summer")
    assert evaluate(cond, _make_player(), registry=None) is True


# ---------------------------------------------------------------------------
# TimeBetweenCondition — format validation at parse time (W1)
# ---------------------------------------------------------------------------


def test_time_between_rejects_ampm_notation() -> None:
    # AM/PM notation does not match ^\d{2}:\d{2}$ and must be rejected at load time.
    with pytest.raises(ValidationError):
        TimeBetweenCondition(type="time_between", start="9:00 AM", end="5:00 PM")


def test_time_between_rejects_no_leading_zero() -> None:
    # Single-digit hour without leading zero does not match ^\d{2}:\d{2}$ and must be rejected.
    with pytest.raises(ValidationError):
        TimeBetweenCondition(type="time_between", start="9:00", end="17:00")


# ---------------------------------------------------------------------------
# time_between respects registry timezone (W3)
# ---------------------------------------------------------------------------


def test_time_between_respects_registry_timezone(monkeypatch: Any) -> None:
    # Verify that _current_datetime receives the timezone string from the registry
    # so that the predicate evaluates against the correct clock.
    seen_tz: list[str | None] = []

    def fake_resolve(tz_name: str | None) -> datetime.datetime:
        seen_tz.append(tz_name)
        return datetime.datetime(2026, 4, 5, 14, 0)  # 14:00 — inside 09:00–17:00

    monkeypatch.setattr("oscilla.engine.calendar_utils.resolve_local_datetime", fake_resolve)
    registry = _make_registry(timezone="America/New_York")
    cond = TimeBetweenCondition(type="time_between", start="09:00", end="17:00")
    assert evaluate(cond, _make_player(), registry=registry) is True
    assert seen_tz == ["America/New_York"]
