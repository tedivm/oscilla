"""Pure calendar and astronomical utility functions.

Shared between the template engine (oscilla/engine/templates.py) and the
future condition evaluator so the same logic is never duplicated. All
functions are pure Python with no external dependencies beyond the standard
library.
"""

from __future__ import annotations

import calendar
import datetime
import statistics
from typing import List

# ---------------------------------------------------------------------------
# Date-derived helpers
# ---------------------------------------------------------------------------

# Meteorological seasons: month ranges map to season names.
# Meteorological (not astronomical) convention is used because it avoids
# solstice/equinox edge cases and is what most authors intuitively expect.
_SEASON_MONTHS: tuple[tuple[int, int, str], ...] = (
    (3, 5, "spring"),
    (6, 8, "summer"),
    (9, 11, "autumn"),
    (12, 12, "winter"),
    (1, 2, "winter"),
)


def season(date: datetime.date) -> str:
    """Return the meteorological season for the given date.

    Returns one of: "spring", "summer", "autumn", "winter".
    """
    m = date.month
    for start, end, name in _SEASON_MONTHS:
        if start <= m <= end:
            return name
    return "winter"  # unreachable; satisfies type checker


def month_name(n: int) -> str:
    """Return the English name of month n (1 = January ... 12 = December).

    Raises ValueError for out-of-range month numbers.
    """
    if n < 1 or n > 12:
        raise ValueError(f"month_name(): n={n} must be 1-12")
    return calendar.month_name[n]


def day_name(n: int) -> str:
    """Return the English name of weekday n (0 = Monday ... 6 = Sunday).

    Matches Python convention: Monday is 0, Sunday is 6.
    Raises ValueError for out-of-range weekday numbers.
    """
    if n < 0 or n > 6:
        raise ValueError(f"day_name(): n={n} must be 0-6")
    return calendar.day_name[n]


def week_number(date: datetime.date) -> int:
    """Return the ISO week number (1-53) for the given date."""
    return date.isocalendar().week


# ---------------------------------------------------------------------------
# Statistical helper
# ---------------------------------------------------------------------------


def mean(values: List[float]) -> float:
    """Return the arithmetic mean of a list of numeric values.

    Raises StatisticsError (subclass of ValueError) for an empty list.
    Thin wrapper around statistics.mean() exposed under the shorter name.
    """
    return statistics.mean(values)


# ---------------------------------------------------------------------------
# Astrology / novelty
# ---------------------------------------------------------------------------

# Each tuple is (cutoff_month, cutoff_day, sign_name).
# Signs are listed in order; the first entry whose (month, day) is >= the
# input date wins. The final Capricorn entry covers Dec 22-31.
_ZODIAC: tuple[tuple[int, int, str], ...] = (
    (1, 19, "Capricorn"),
    (2, 19, "Aquarius"),
    (3, 20, "Pisces"),
    (4, 19, "Aries"),
    (5, 20, "Taurus"),
    (6, 20, "Gemini"),
    (7, 22, "Cancer"),
    (8, 22, "Leo"),
    (9, 22, "Virgo"),
    (10, 22, "Libra"),
    (11, 21, "Scorpio"),
    (12, 21, "Sagittarius"),
    (12, 31, "Capricorn"),
)


def zodiac_sign(date: datetime.date) -> str:
    """Return the Western zodiac sign for the given date.

    Uses conventional Sun-entry boundary dates. Returns one of the twelve
    standard sign names (e.g. "Aries", "Taurus", "Gemini").
    """
    m, d = date.month, date.day
    for cutoff_month, cutoff_day, sign in _ZODIAC:
        if m < cutoff_month or (m == cutoff_month and d <= cutoff_day):
            return sign
    return "Capricorn"  # Dec 22-31


_CHINESE_ANIMALS: tuple[str, ...] = (
    "Rat",
    "Ox",
    "Tiger",
    "Rabbit",
    "Dragon",
    "Snake",
    "Horse",
    "Goat",
    "Monkey",
    "Rooster",
    "Dog",
    "Pig",
)


def chinese_zodiac(year: int) -> str:
    """Return the Chinese zodiac animal for the given year.

    Uses a simple 12-year cycle anchored to 4 CE (the Rat year).
    Does not account for the Lunar New Year boundary (Jan/Feb); if that
    precision matters, the author can compare today().month.
    Returns one of: "Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake",
    "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig".
    """
    return _CHINESE_ANIMALS[(year - 4) % 12]


_KNOWN_NEW_MOON = datetime.date(2000, 1, 6)  # verified new moon anchor
_LUNAR_CYCLE = 29.53058770576  # mean synodic month (days)
_PHASE_NAMES: tuple[str, ...] = (
    "New Moon",
    "Waxing Crescent",
    "First Quarter",
    "Waxing Gibbous",
    "Full Moon",
    "Waning Gibbous",
    "Last Quarter",
    "Waning Crescent",
)


def moon_phase(date: datetime.date) -> str:
    """Return the approximate lunar phase name for the given date.

    Uses the mean synodic month (29.53 days) anchored to the known new moon
    of 2000-01-06. Accuracy is +/-1 day — suitable for narrative flavour but
    not for astronomical precision.
    Returns one of eight phase names: "New Moon", "Waxing Crescent",
    "First Quarter", "Waxing Gibbous", "Full Moon", "Waning Gibbous",
    "Last Quarter", "Waning Crescent".
    """
    days_since = (date - _KNOWN_NEW_MOON).days % _LUNAR_CYCLE
    phase_index = int(days_since / _LUNAR_CYCLE * 8) % 8
    return _PHASE_NAMES[phase_index]
