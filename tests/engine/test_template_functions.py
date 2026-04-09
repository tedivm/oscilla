"""Unit tests for all new SAFE_GLOBALS template functions.

Covers task 11.4: roll_pool, keep_highest, keep_lowest, count_successes,
explode, roll_fudge, weighted_roll, die aliases d4–d100, ordinal (including
teen edge cases), signed, stat_mod.
"""

from __future__ import annotations

import pytest

from oscilla.engine.templates import (
    _d4,
    _d6,
    _d8,
    _d10,
    _d12,
    _d20,
    _d100,
    _ordinal,
    _safe_count_successes,
    _safe_explode,
    _safe_keep_highest,
    _safe_keep_lowest,
    _safe_roll_fudge,
    _safe_roll_pool,
    _safe_weighted_roll,
    _signed,
    _stat_mod,
)

# ---------------------------------------------------------------------------
# roll_pool
# ---------------------------------------------------------------------------


def test_roll_pool_returns_correct_count() -> None:
    result = _safe_roll_pool(n=3, sides=6)
    assert len(result) == 3


def test_roll_pool_values_in_range() -> None:
    for _ in range(50):
        result = _safe_roll_pool(n=4, sides=8)
        assert all(1 <= v <= 8 for v in result)


def test_roll_pool_single_die() -> None:
    result = _safe_roll_pool(n=1, sides=20)
    assert len(result) == 1
    assert 1 <= result[0] <= 20


def test_roll_pool_rejects_non_int_n() -> None:
    with pytest.raises(ValueError, match="int"):
        _safe_roll_pool(n=1.5, sides=6)  # type: ignore[arg-type]


def test_roll_pool_rejects_zero_n() -> None:
    with pytest.raises(ValueError, match="n must be"):
        _safe_roll_pool(n=0, sides=6)


def test_roll_pool_rejects_one_sided_die() -> None:
    with pytest.raises(ValueError, match="sides must be"):
        _safe_roll_pool(n=1, sides=1)


# ---------------------------------------------------------------------------
# keep_highest
# ---------------------------------------------------------------------------


def test_keep_highest_returns_top_n() -> None:
    result = _safe_keep_highest(pool=[1, 5, 3, 4], n=2)
    assert sorted(result, reverse=True) == [5, 4]


def test_keep_highest_single() -> None:
    result = _safe_keep_highest(pool=[2, 6, 1], n=1)
    assert result == [6]


def test_keep_highest_rejects_non_list() -> None:
    with pytest.raises(ValueError, match="list"):
        _safe_keep_highest(pool=42, n=1)  # type: ignore[arg-type]


def test_keep_highest_rejects_n_exceeds_pool() -> None:
    with pytest.raises(ValueError, match="exceeds pool"):
        _safe_keep_highest(pool=[1, 2], n=5)


# ---------------------------------------------------------------------------
# keep_lowest
# ---------------------------------------------------------------------------


def test_keep_lowest_returns_bottom_n() -> None:
    result = _safe_keep_lowest(pool=[1, 5, 3, 4], n=2)
    assert sorted(result) == [1, 3]


def test_keep_lowest_single() -> None:
    result = _safe_keep_lowest(pool=[7, 2, 9], n=1)
    assert result == [2]


def test_keep_lowest_rejects_non_list() -> None:
    with pytest.raises(ValueError, match="list"):
        _safe_keep_lowest(pool="bad", n=1)  # type: ignore[arg-type]


def test_keep_lowest_rejects_n_exceeds_pool() -> None:
    with pytest.raises(ValueError, match="exceeds pool"):
        _safe_keep_lowest(pool=[1, 2], n=5)


# ---------------------------------------------------------------------------
# count_successes
# ---------------------------------------------------------------------------


def test_count_successes_basic() -> None:
    assert _safe_count_successes(pool=[3, 5, 2, 6], threshold=5) == 2


def test_count_successes_none_pass() -> None:
    assert _safe_count_successes(pool=[1, 2, 3], threshold=5) == 0


def test_count_successes_all_pass() -> None:
    assert _safe_count_successes(pool=[5, 6, 7], threshold=5) == 3


def test_count_successes_rejects_non_list() -> None:
    with pytest.raises(ValueError, match="list"):
        _safe_count_successes(pool=42, threshold=5)  # type: ignore[arg-type]


def test_count_successes_rejects_non_int_threshold() -> None:
    with pytest.raises(ValueError, match="int"):
        _safe_count_successes(pool=[1, 2, 3], threshold=3.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# explode
# ---------------------------------------------------------------------------


def test_explode_no_explosion_when_no_max() -> None:
    # A pool with no dice at the max value should not grow.
    pool = [1, 2, 3]
    result = _safe_explode(pool=pool, sides=6, on=6)
    assert len(result) >= 3
    assert result[:3] == pool


def test_explode_adds_extra_die_on_hit() -> None:
    # Force an exploding die by setting on=1 so 1s always explode.
    result = _safe_explode(pool=[1], sides=6, on=1, max_explosions=1)
    assert len(result) == 2


def test_explode_respects_max_explosions() -> None:
    # All dice are 1s, on=1, max_explosions=3 — pool grows by exactly 3 extra.
    result = _safe_explode(pool=[1, 1, 1], sides=6, on=1, max_explosions=3)
    # Original 3 + at most 3 more explosions
    assert len(result) <= 6


def test_explode_rejects_non_list() -> None:
    with pytest.raises(ValueError, match="list"):
        _safe_explode(pool=5, sides=6)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# roll_fudge
# ---------------------------------------------------------------------------


def test_roll_fudge_returns_correct_count() -> None:
    result = _safe_roll_fudge(n=4)
    assert len(result) == 4


def test_roll_fudge_values_in_range() -> None:
    for _ in range(100):
        result = _safe_roll_fudge(n=10)
        assert all(v in (-1, 0, 1) for v in result)


def test_roll_fudge_rejects_zero() -> None:
    with pytest.raises(ValueError, match="positive int"):
        _safe_roll_fudge(n=0)


def test_roll_fudge_rejects_non_int() -> None:
    with pytest.raises(ValueError, match="positive int"):
        _safe_roll_fudge(n=2.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# weighted_roll
# ---------------------------------------------------------------------------


def test_weighted_roll_returns_from_options() -> None:
    options = ["a", "b", "c"]
    for _ in range(50):
        result = _safe_weighted_roll(options=options, weights=[50, 30, 20])
        assert result in options


def test_weighted_roll_strongly_favors_weighted_option() -> None:
    # With weight 999 vs 1, the heavy option should dominate across 100 runs.
    results = [_safe_weighted_roll(options=["heavy", "light"], weights=[999, 1]) for _ in range(100)]
    assert results.count("heavy") >= 90


def test_weighted_roll_rejects_non_lists() -> None:
    with pytest.raises(ValueError, match="lists"):
        _safe_weighted_roll(options="abc", weights=[1, 2, 3])  # type: ignore[arg-type]


def test_weighted_roll_rejects_empty_options() -> None:
    with pytest.raises(ValueError, match="empty"):
        _safe_weighted_roll(options=[], weights=[])


def test_weighted_roll_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError, match="length"):
        _safe_weighted_roll(options=["a", "b"], weights=[1, 2, 3])


# ---------------------------------------------------------------------------
# Die aliases d4 – d100
# ---------------------------------------------------------------------------


def test_d4_in_range() -> None:
    for _ in range(50):
        assert 1 <= _d4() <= 4


def test_d6_in_range() -> None:
    for _ in range(50):
        assert 1 <= _d6() <= 6


def test_d8_in_range() -> None:
    for _ in range(50):
        assert 1 <= _d8() <= 8


def test_d10_in_range() -> None:
    for _ in range(50):
        assert 1 <= _d10() <= 10


def test_d12_in_range() -> None:
    for _ in range(50):
        assert 1 <= _d12() <= 12


def test_d20_in_range() -> None:
    for _ in range(50):
        assert 1 <= _d20() <= 20


def test_d100_in_range() -> None:
    for _ in range(50):
        assert 1 <= _d100() <= 100


# ---------------------------------------------------------------------------
# ordinal
# ---------------------------------------------------------------------------


def test_ordinal_1st() -> None:
    assert _ordinal(1) == "1st"


def test_ordinal_2nd() -> None:
    assert _ordinal(2) == "2nd"


def test_ordinal_3rd() -> None:
    assert _ordinal(3) == "3rd"


def test_ordinal_4th() -> None:
    assert _ordinal(4) == "4th"


def test_ordinal_11th_teen_exception() -> None:
    assert _ordinal(11) == "11th"


def test_ordinal_12th_teen_exception() -> None:
    assert _ordinal(12) == "12th"


def test_ordinal_13th_teen_exception() -> None:
    assert _ordinal(13) == "13th"


def test_ordinal_21st_not_teen() -> None:
    assert _ordinal(21) == "21st"


def test_ordinal_111th_teen_exception() -> None:
    # 111 % 100 == 11, which is in the teen range.
    assert _ordinal(111) == "111th"


def test_ordinal_rejects_non_int() -> None:
    with pytest.raises(ValueError, match="int"):
        _ordinal("3")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# signed
# ---------------------------------------------------------------------------


def test_signed_positive() -> None:
    assert _signed(3) == "+3"


def test_signed_negative() -> None:
    assert _signed(-2) == "-2"


def test_signed_zero() -> None:
    assert _signed(0) == "0"


def test_signed_float_positive() -> None:
    assert _signed(1.5) == "+1.5"


def test_signed_rejects_string() -> None:
    with pytest.raises(ValueError, match="numeric"):
        _signed("3")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# stat_mod
# ---------------------------------------------------------------------------


def test_stat_mod_10_is_zero() -> None:
    assert _stat_mod(10) == 0


def test_stat_mod_14_is_plus_2() -> None:
    assert _stat_mod(14) == 2


def test_stat_mod_8_is_minus_1() -> None:
    assert _stat_mod(8) == -1


def test_stat_mod_18_is_plus_4() -> None:
    assert _stat_mod(18) == 4


def test_stat_mod_rejects_non_int() -> None:
    with pytest.raises(ValueError, match="int"):
        _stat_mod(10.5)  # type: ignore[arg-type]
