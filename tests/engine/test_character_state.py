"""Tests for CharacterState factory and serialization — derived stat integration.

Covers task 11.5: verifies that new_character() does not produce hardcoded
level/xp/hp/max_hp top-level fields, that to_dict()/from_dict() round-trips
cleanly without those keys, and that derived stats live in _derived_shadows
rather than stats.
"""

from __future__ import annotations

from uuid import uuid4

from oscilla.engine.character import CharacterState
from oscilla.engine.models.base import Metadata
from oscilla.engine.models.character_config import CharacterConfigManifest, CharacterConfigSpec, StatDefinition
from oscilla.engine.models.game import GameManifest, GameSpec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_char_config(stats: list[dict] | None = None) -> CharacterConfigManifest:
    """Return a minimal CharacterConfigManifest with the given stats."""
    raw_stats = stats or [
        {"name": "strength", "type": "int", "default": 10},
    ]
    return CharacterConfigManifest(
        apiVersion="oscilla/v1",
        kind="CharacterConfig",
        metadata=Metadata(name="test-char-config"),
        spec=CharacterConfigSpec(
            public_stats=[StatDefinition(**s) for s in raw_stats],
            hidden_stats=[],
        ),
    )


def _make_game() -> GameManifest:
    return GameManifest(
        apiVersion="oscilla/v1",
        kind="Game",
        metadata=Metadata(name="test-game"),
        spec=GameSpec(displayName="Test"),
    )


def _new_char(char_config: CharacterConfigManifest | None = None) -> CharacterState:
    config = char_config or _make_char_config()
    game = _make_game()
    return CharacterState.new_character(
        name="Tester",
        game_manifest=game,
        character_config=config,
    )


# ---------------------------------------------------------------------------
# new_character() — no hardcoded progression fields
# ---------------------------------------------------------------------------


def test_new_character_has_no_level_attribute() -> None:
    """CharacterState must not have a top-level 'level' attribute."""
    state = _new_char()
    assert not hasattr(state, "level")


def test_new_character_has_no_xp_attribute() -> None:
    state = _new_char()
    assert not hasattr(state, "xp")


def test_new_character_has_no_hp_attribute() -> None:
    state = _new_char()
    assert not hasattr(state, "hp")


def test_new_character_has_no_max_hp_attribute() -> None:
    state = _new_char()
    assert not hasattr(state, "max_hp")


def test_new_character_stats_initialized_from_config() -> None:
    """Stats dict is populated from the CharacterConfig defaults."""
    config = _make_char_config([{"name": "strength", "type": "int", "default": 15}])
    state = _new_char(config)
    assert state.stats["strength"] == 15


# ---------------------------------------------------------------------------
# new_character() — derived stats not in stats dict
# ---------------------------------------------------------------------------


def test_new_character_derived_stat_absent_from_stats_dict() -> None:
    """Derived stats must not appear in the stored stats dict."""
    config = _make_char_config(
        [
            {"name": "xp", "type": "int", "default": 0},
            {
                "name": "level",
                "type": "int",
                "derived": "{{ 1 + (1 if player.stats['xp'] >= 100 else 0) }}",
            },
        ]
    )
    state = _new_char(config)
    assert "level" not in state.stats
    assert "xp" in state.stats


def test_new_character_derived_shadows_starts_empty() -> None:
    """_derived_shadows is empty immediately after new_character() (not yet computed)."""
    config = _make_char_config(
        [
            {"name": "xp", "type": "int", "default": 0},
            {
                "name": "level",
                "type": "int",
                "derived": "{{ 1 + (1 if player.stats['xp'] >= 100 else 0) }}",
            },
        ]
    )
    state = _new_char(config)
    # _derived_shadows is populated by _recompute_derived_stats, not by new_character.
    assert state._derived_shadows == {}


# ---------------------------------------------------------------------------
# to_dict() — no top-level progression keys
# ---------------------------------------------------------------------------


def test_to_dict_has_no_level_key() -> None:
    state = _new_char()
    d = state.to_dict()
    assert "level" not in d


def test_to_dict_has_no_xp_key() -> None:
    state = _new_char()
    d = state.to_dict()
    assert "xp" not in d


def test_to_dict_has_no_hp_key() -> None:
    state = _new_char()
    d = state.to_dict()
    assert "hp" not in d


def test_to_dict_has_no_max_hp_key() -> None:
    state = _new_char()
    d = state.to_dict()
    assert "max_hp" not in d


def test_to_dict_excludes_derived_shadows() -> None:
    """_derived_shadows must not appear in the serialized dict."""
    config = _make_char_config(
        [
            {"name": "xp", "type": "int", "default": 0},
            {
                "name": "level",
                "type": "int",
                "derived": "{{ 1 + (1 if player.stats['xp'] >= 100 else 0) }}",
            },
        ]
    )
    state = _new_char(config)
    state._derived_shadows["level"] = 2  # simulate a computed value
    d = state.to_dict()
    assert "_derived_shadows" not in d


def test_to_dict_stats_key_contains_stored_stats() -> None:
    """The 'stats' key in to_dict() contains only stored (non-derived) stat values."""
    config = _make_char_config(
        [
            {"name": "xp", "type": "int", "default": 50},
            {
                "name": "level",
                "type": "int",
                "derived": "{{ 1 + (1 if player.stats['xp'] >= 100 else 0) }}",
            },
        ]
    )
    state = _new_char(config)
    d = state.to_dict()
    assert "xp" in d["stats"]
    assert "level" not in d["stats"]


# ---------------------------------------------------------------------------
# from_dict() — resilient to absent progression keys
# ---------------------------------------------------------------------------


def test_from_dict_succeeds_without_level_xp_hp_keys() -> None:
    """from_dict() must not fail when level/xp/hp/max_hp are absent from data."""
    config = _make_char_config([{"name": "strength", "type": "int", "default": 10}])
    data = {
        "character_id": str(uuid4()),
        "prestige_count": 0,
        "name": "Tester",
        "current_location": None,
        "pronoun_set": "they_them",
        "milestones": {},
        "stacks": {},
        "instances": [],
        "equipment": {},
        "active_quests": {},
        "completed_quests": [],
        "failed_quests": [],
        "stats": {"strength": 10},
        "statistics": {
            "enemies_defeated": {},
            "locations_visited": {},
            "adventures_completed": {},
            "adventure_outcome_counts": {},
        },
        "active_adventure": None,
        "known_skills": [],
        "skill_tick_expiry": {},
        "skill_real_expiry": {},
        "adventure_last_completed_real_ts": {},
        "adventure_last_completed_at_ticks": {},
        "adventure_last_completed_game_ticks": {},
        "internal_ticks": 0,
        "game_ticks": 0,
        "era_started_at_ticks": {},
        "era_ended_at_ticks": {},
    }
    state = CharacterState.from_dict(data=data, character_config=config)
    assert state.name == "Tester"
    assert state.stats["strength"] == 10


def test_from_dict_round_trip() -> None:
    """to_dict() → from_dict() produces an equivalent state."""
    config = _make_char_config([{"name": "strength", "type": "int", "default": 10}])
    state = _new_char(config)
    state.stats["strength"] = 20
    data = state.to_dict()
    restored = CharacterState.from_dict(data=data, character_config=config)
    assert restored.stats["strength"] == 20
    assert restored.name == state.name
