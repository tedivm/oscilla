"""Unit tests for oscilla.engine.templates — GameTemplateEngine, filters, functions."""

from __future__ import annotations

import datetime
from typing import Set

import pytest

from oscilla.engine.templates import (
    DEFAULT_PRONOUN_SET,
    CombatContextView,
    ExpressionContext,
    GameTemplateEngine,
    PlayerContext,
    PlayerMilestoneView,
    PlayerPronounView,
    TemplateRuntimeError,
    TemplateValidationError,
    preprocess_pronouns,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player(
    name: str = "Tester",
    level: int = 1,
    stats: dict | None = None,
    milestones: Set[str] | None = None,
) -> PlayerContext:
    pronouns = PlayerPronounView.from_set(DEFAULT_PRONOUN_SET)
    return PlayerContext(
        name=name,
        level=level,
        iteration=0,
        hp=20,
        max_hp=20,
        stats=stats or {"strength": 10},
        milestones=PlayerMilestoneView(_milestones=milestones or set()),
        pronouns=pronouns,
    )


def _make_engine(stat_names: list[str] | None = None) -> GameTemplateEngine:
    return GameTemplateEngine(stat_names=stat_names or ["strength", "luck"])


def _make_ctx(player: PlayerContext | None = None, combat: CombatContextView | None = None) -> ExpressionContext:
    return ExpressionContext(player=player or _make_player(), combat=combat)


# ---------------------------------------------------------------------------
# preprocess_pronouns()
# ---------------------------------------------------------------------------


def test_preprocess_they_lowercase() -> None:
    result = preprocess_pronouns("{they}")
    assert "player.pronouns.subject" in result
    assert "|" not in result.replace("{{", "").replace("}}", "")


def test_preprocess_they_capitalize() -> None:
    result = preprocess_pronouns("{They}")
    assert "capitalize" in result


def test_preprocess_they_upper() -> None:
    result = preprocess_pronouns("{THEY}")
    assert "upper" in result


def test_preprocess_them() -> None:
    result = preprocess_pronouns("{them}")
    assert "player.pronouns.object" in result


def test_preprocess_their() -> None:
    result = preprocess_pronouns("{their}")
    assert "player.pronouns.possessive" in result


def test_preprocess_is_verb() -> None:
    result = preprocess_pronouns("{is}")
    assert "player.pronouns.uses_plural_verbs" in result


def test_preprocess_are_verb() -> None:
    result = preprocess_pronouns("{are}")
    assert "player.pronouns.uses_plural_verbs" in result


def test_preprocess_was_verb() -> None:
    result = preprocess_pronouns("{was}")
    assert "player.pronouns.uses_plural_verbs" in result


def test_preprocess_has_verb() -> None:
    result = preprocess_pronouns("{has}")
    assert "player.pronouns.uses_plural_verbs" in result


def test_preprocess_unknown_placeholder_unchanged() -> None:
    result = preprocess_pronouns("{goblincount}")
    assert "{goblincount}" in result


def test_preprocess_jinja_blocks_not_affected() -> None:
    raw = "{% if player.level > 1 %}veteran{% endif %}"
    result = preprocess_pronouns(raw)
    assert result == raw


# ---------------------------------------------------------------------------
# GameTemplateEngine — basic precompile + render
# ---------------------------------------------------------------------------


def test_render_player_name() -> None:
    engine = _make_engine()
    ctx = _make_ctx(_make_player(name="Elara"))
    engine.precompile_and_validate("Hello {{ player.name }}!", "test-name", "adventure")
    result = engine.render("test-name", ctx)
    assert result == "Hello Elara!"


def test_render_player_stat() -> None:
    engine = _make_engine(["strength"])
    ctx = _make_ctx(_make_player(stats={"strength": 15}))
    engine.precompile_and_validate("Strength: {{ player.stats.strength }}", "test-stat", "adventure")
    result = engine.render("test-stat", ctx)
    assert result == "Strength: 15"


def test_render_player_level() -> None:
    engine = _make_engine()
    ctx = _make_ctx(_make_player(level=5))
    engine.precompile_and_validate("Level: {{ player.level }}", "test-level", "adventure")
    result = engine.render("test-level", ctx)
    assert result == "Level: 5"


def test_render_pronoun() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{they} explore!", "test-pronoun", "adventure")
    result = engine.render("test-pronoun", ctx)
    assert result == "they explore!"


def test_render_roll_within_range() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ roll(1, 6) }}", "test-roll", "adventure")
    result = int(engine.render("test-roll", ctx))
    assert 1 <= result <= 6


def test_render_choice() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ choice(['a', 'b', 'c']) }}", "test-choice", "adventure")
    result = engine.render("test-choice", ctx)
    assert result in {"a", "b", "c"}


def test_render_math_abs() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ abs(-5) }}", "test-math", "adventure")
    result = engine.render("test-math", ctx)
    assert result == "5"


def test_render_now_returns_datetime() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ now().year }}", "test-now", "adventure")
    result = int(engine.render("test-now", ctx))
    assert result == datetime.datetime.now().year


def test_render_today_returns_date() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ today().year }}", "test-today", "adventure")
    result = int(engine.render("test-today", ctx))
    assert result == datetime.date.today().year


# ---------------------------------------------------------------------------
# Validation failures
# ---------------------------------------------------------------------------


def test_invalid_player_property_raises_validation_error() -> None:
    engine = _make_engine()
    with pytest.raises(TemplateValidationError):
        engine.precompile_and_validate("{{ player.nonexistent_field }}", "test-invalid", "adventure")


def test_invalid_stat_name_raises_validation_error() -> None:
    engine = _make_engine(stat_names=["strength"])
    # Template accessing an unknown stat key in the mock stats dict should fail.
    with pytest.raises(TemplateValidationError):
        engine.precompile_and_validate("{{ player.stats.unknown_stat }}", "test-bad-stat", "adventure")


def test_combat_context_unavailable_in_adventure_context() -> None:
    engine = _make_engine()
    with pytest.raises(TemplateValidationError):
        engine.precompile_and_validate("{{ combat.enemy_hp }}", "test-combat-in-adventure", "adventure")


def test_combat_context_available_in_combat_context() -> None:
    engine = _make_engine()
    # Should NOT raise — combat context is available in "combat" context type.
    engine.precompile_and_validate("{{ combat.enemy_hp }}", "test-combat-in-combat", "combat")
    combat_view = CombatContextView(enemy_hp=30, enemy_name="Goblin", turn=1)
    ctx = ExpressionContext(player=_make_player(), combat=combat_view)
    result = engine.render("test-combat-in-combat", ctx)
    assert result == "30"


# ---------------------------------------------------------------------------
# Built-in function validation
# ---------------------------------------------------------------------------


def test_roll_within_range() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ roll(1, 10) }}", "roll-range", "adventure")
    for _ in range(10):
        value = int(engine.render("roll-range", ctx))
        assert 1 <= value <= 10


def test_roll_with_low_greater_than_high_raises() -> None:
    # roll(10, 1) is invalid — mock render catches this at validation time.
    engine = _make_engine()
    with pytest.raises(TemplateValidationError):
        engine.precompile_and_validate("{{ roll(10, 1) }}", "roll-invalid", "adventure")


def test_choice_from_list() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ choice(['x', 'y', 'z']) }}", "choice-list", "adventure")
    result = engine.render("choice-list", ctx)
    assert result in {"x", "y", "z"}


def test_choice_empty_list_raises() -> None:
    # choice([]) is invalid — mock render catches this at validation time.
    engine = _make_engine()
    with pytest.raises(TemplateValidationError):
        engine.precompile_and_validate("{{ choice([]) }}", "choice-empty", "adventure")


def test_sample_returns_unique_elements() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ sample([1, 2, 3, 4, 5], 3) | join(',') }}", "sample-3", "adventure")
    result = engine.render("sample-3", ctx)
    values = [int(x) for x in result.split(",")]
    assert len(values) == 3
    assert len(set(values)) == 3


def test_sample_k_exceeds_length_raises() -> None:
    # sample([1, 2], 10) is invalid — mock render catches this at validation time.
    engine = _make_engine()
    with pytest.raises(TemplateValidationError):
        engine.precompile_and_validate("{{ sample([1, 2], 10) }}", "sample-overflow", "adventure")


def test_clamp_within_bounds() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ clamp(5, 1, 10) }}", "clamp-within", "adventure")
    assert engine.render("clamp-within", ctx) == "5"
    engine.precompile_and_validate("{{ clamp(0, 1, 10) }}", "clamp-below", "adventure")
    assert engine.render("clamp-below", ctx) == "1"
    engine.precompile_and_validate("{{ clamp(15, 1, 10) }}", "clamp-above", "adventure")
    assert engine.render("clamp-above", ctx) == "10"


def test_random_returns_float() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ random() }}", "rand-float", "adventure")
    result = float(engine.render("rand-float", ctx))
    assert 0.0 <= result < 1.0


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def test_stat_modifier_positive() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ 14 | stat_modifier }}", "mod-pos", "adventure")
    result = engine.render("mod-pos", ctx)
    assert result == "+2"


def test_stat_modifier_negative() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ 8 | stat_modifier }}", "mod-neg", "adventure")
    result = engine.render("mod-neg", ctx)
    assert result == "-1"


def test_pluralize_singular() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ 1 | pluralize('goblin', 'goblins') }}", "plural-s", "adventure")
    assert engine.render("plural-s", ctx) == "goblin"


def test_pluralize_plural() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ 3 | pluralize('goblin', 'goblins') }}", "plural-p", "adventure")
    assert engine.render("plural-p", ctx) == "goblins"


# ---------------------------------------------------------------------------
# render_int()
# ---------------------------------------------------------------------------


def test_render_int_succeeds() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("{{ roll(5, 5) }}", "roll-fixed", "adventure")
    assert engine.render_int("roll-fixed", ctx) == 5


def test_render_int_non_integer_raises() -> None:
    engine = _make_engine()
    ctx = _make_ctx()
    engine.precompile_and_validate("hello", "non-int", "adventure")
    with pytest.raises(TemplateRuntimeError):
        engine.render_int("non-int", ctx)


# ---------------------------------------------------------------------------
# is_template()
# ---------------------------------------------------------------------------


def test_is_template_jinja_expression() -> None:
    engine = _make_engine()
    assert engine.is_template("{{ player.name }}")


def test_is_template_jinja_block() -> None:
    engine = _make_engine()
    assert engine.is_template("{% if player.level > 1 %}...{% endif %}")


def test_is_template_pronoun_shorthand() -> None:
    engine = _make_engine()
    assert engine.is_template("{they}")


def test_is_template_plain_string() -> None:
    engine = _make_engine()
    assert not engine.is_template("Hello, adventurer!")
