"""Unit tests for oscilla.engine.calendar_utils."""

from __future__ import annotations

import datetime

import pytest

from oscilla.engine import calendar_utils

# ---------------------------------------------------------------------------
# season()
# ---------------------------------------------------------------------------


def test_season_spring() -> None:
    assert calendar_utils.season(datetime.date(2024, 3, 20)) == "spring"
    assert calendar_utils.season(datetime.date(2024, 4, 1)) == "spring"
    assert calendar_utils.season(datetime.date(2024, 5, 31)) == "spring"


def test_season_summer() -> None:
    assert calendar_utils.season(datetime.date(2024, 6, 1)) == "summer"
    assert calendar_utils.season(datetime.date(2024, 7, 15)) == "summer"
    assert calendar_utils.season(datetime.date(2024, 8, 31)) == "summer"


def test_season_autumn() -> None:
    assert calendar_utils.season(datetime.date(2024, 9, 1)) == "autumn"
    assert calendar_utils.season(datetime.date(2024, 10, 31)) == "autumn"
    assert calendar_utils.season(datetime.date(2024, 11, 30)) == "autumn"


def test_season_winter() -> None:
    assert calendar_utils.season(datetime.date(2024, 12, 1)) == "winter"
    assert calendar_utils.season(datetime.date(2024, 1, 15)) == "winter"
    assert calendar_utils.season(datetime.date(2024, 2, 28)) == "winter"


# ---------------------------------------------------------------------------
# month_name()
# ---------------------------------------------------------------------------


def test_month_name_returns_string() -> None:
    assert isinstance(calendar_utils.month_name(1), str)
    assert calendar_utils.month_name(1) == "January"
    assert calendar_utils.month_name(12) == "December"


def test_month_name_invalid_raises() -> None:
    with pytest.raises(ValueError):
        calendar_utils.month_name(0)
    with pytest.raises(ValueError):
        calendar_utils.month_name(13)


# ---------------------------------------------------------------------------
# day_name()
# ---------------------------------------------------------------------------


def test_day_name_returns_string() -> None:
    # Monday is 0 in Python calendar convention
    result = calendar_utils.day_name(0)
    assert isinstance(result, str)
    assert len(result) > 0


def test_day_name_invalid_raises() -> None:
    with pytest.raises(ValueError):
        calendar_utils.day_name(-1)
    with pytest.raises(ValueError):
        calendar_utils.day_name(7)


# ---------------------------------------------------------------------------
# week_number()
# ---------------------------------------------------------------------------


def test_week_number_returns_int_in_range() -> None:
    wn = calendar_utils.week_number(datetime.date(2024, 6, 15))
    assert isinstance(wn, int)
    assert 1 <= wn <= 53


# ---------------------------------------------------------------------------
# mean()
# ---------------------------------------------------------------------------


def test_mean_correct_average() -> None:
    assert calendar_utils.mean([1, 2, 3, 4, 5]) == 3.0


def test_mean_empty_raises() -> None:
    with pytest.raises((ValueError, Exception)):
        calendar_utils.mean([])


# ---------------------------------------------------------------------------
# zodiac_sign()
# ---------------------------------------------------------------------------


def test_zodiac_sign_returns_string() -> None:
    result = calendar_utils.zodiac_sign(datetime.date(2024, 3, 21))
    assert isinstance(result, str)
    assert len(result) > 0


def test_zodiac_sign_aries() -> None:
    # March 21 is within Aries
    assert calendar_utils.zodiac_sign(datetime.date(2024, 3, 21)) == "Aries"


def test_zodiac_sign_capricorn() -> None:
    # January 10 is within Capricorn
    assert calendar_utils.zodiac_sign(datetime.date(2024, 1, 10)) == "Capricorn"


# ---------------------------------------------------------------------------
# chinese_zodiac()
# ---------------------------------------------------------------------------


def test_chinese_zodiac_returns_string() -> None:
    result = calendar_utils.chinese_zodiac(2024)
    assert isinstance(result, str)
    assert len(result) > 0


def test_chinese_zodiac_12_year_cycle() -> None:
    # Same zodiac should repeat every 12 years
    sign_2024 = calendar_utils.chinese_zodiac(2024)
    assert calendar_utils.chinese_zodiac(2024 + 12) == sign_2024
    assert calendar_utils.chinese_zodiac(2024 - 12) == sign_2024


# ---------------------------------------------------------------------------
# moon_phase()
# ---------------------------------------------------------------------------


_VALID_MOON_PHASES = {
    "New Moon",
    "Waxing Crescent",
    "First Quarter",
    "Waxing Gibbous",
    "Full Moon",
    "Waning Gibbous",
    "Last Quarter",
    "Waning Crescent",
}


def test_moon_phase_returns_valid_phase() -> None:
    result = calendar_utils.moon_phase(datetime.date(2024, 6, 22))
    assert isinstance(result, str)
    assert result in _VALID_MOON_PHASES
