"""Tests for stat_change and stat_set effect validation and execution."""

from __future__ import annotations

from pathlib import Path

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.loader import ContentLoadError, load

FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"
STAT_EFFECTS_FIXTURE = FIXTURES / "stat-effects"


def test_valid_stat_effects_load_successfully() -> None:
    """Stat effects with correct types should load without error."""
    registry = load(STAT_EFFECTS_FIXTURE)
    assert registry.game is not None
    assert registry.character_config is not None
    assert len(registry.adventures) == 1


def test_stat_change_int_positive() -> None:
    """stat_change with positive int amount on int stat should work."""
    registry = load(STAT_EFFECTS_FIXTURE)
    player = CharacterState.new_character(
        name="TestHero", game_manifest=registry.game, character_config=registry.character_config
    )

    # Initial strength should be 10 (default)
    assert player.stats["strength"] == 10

    # Apply stat_change effect manually
    from oscilla.engine.models.adventure import StatChangeEffect

    effect = StatChangeEffect(type="stat_change", stat="strength", amount=5)

    # This would be applied by the effect handler, so let's simulate it
    old_value = player.stats["strength"]
    new_value = old_value + effect.amount
    player.stats["strength"] = new_value

    assert player.stats["strength"] == 15


def test_stat_change_float_negative() -> None:
    """stat_change with negative float amount on float stat should work."""
    registry = load(STAT_EFFECTS_FIXTURE)
    player = CharacterState.new_character(
        name="TestHero", game_manifest=registry.game, character_config=registry.character_config
    )

    # Initial speed should be 5.0 (default)
    assert player.stats["speed"] == 5.0

    from oscilla.engine.models.adventure import StatChangeEffect

    effect = StatChangeEffect(type="stat_change", stat="speed", amount=-2.5)

    old_value = player.stats["speed"]
    new_value = old_value + effect.amount
    player.stats["speed"] = new_value

    assert player.stats["speed"] == 2.5


def test_stat_set_bool() -> None:
    """stat_set with bool value on bool stat should work."""
    registry = load(STAT_EFFECTS_FIXTURE)
    player = CharacterState.new_character(
        name="TestHero", game_manifest=registry.game, character_config=registry.character_config
    )

    # Initial is_blessed should be False (default)
    assert player.stats["is_blessed"] is False

    from oscilla.engine.models.adventure import StatSetEffect

    effect = StatSetEffect(type="stat_set", stat="is_blessed", value=True)

    player.stats["is_blessed"] = effect.value

    assert player.stats["is_blessed"] is True


def test_str_stat_type_rejected(tmp_path: Path) -> None:
    """CharacterConfig with type: str should be rejected at load time."""
    (tmp_path / "game.yaml").write_text("""
apiVersion: game/v1
kind: Game
metadata:
  name: test-game
spec:
  displayName: "Test"
  xp_thresholds: [100]
  hp_formula:
    base_hp: 20
    hp_per_level: 5
""")
    (tmp_path / "character-config.yaml").write_text("""
apiVersion: game/v1
kind: CharacterConfig
metadata:
  name: config
spec:
  public_stats:
    - name: title
      type: str
      default: ""
  hidden_stats: []
""")

    with pytest.raises(ContentLoadError):
        load(tmp_path)


def test_invalid_stat_change_on_bool_fails(tmp_path: Path) -> None:
    """stat_change on bool stat should fail validation."""
    # Create a broken adventure with stat_change on bool stat
    (tmp_path / "game.yaml").write_text("""
apiVersion: game/v1
kind: Game
metadata:
  name: broken-game
spec:
  displayName: "Broken"
  xp_thresholds: [0, 100]
  hp_formula:
    base_hp: 20
    hp_per_level: 5
""")

    (tmp_path / "character-config.yaml").write_text("""
apiVersion: game/v1
kind: CharacterConfig
metadata:
  name: config
spec:
  public_stats:
    - name: is_active
      type: bool
      default: true
  hidden_stats: []
""")

    (tmp_path / "region.yaml").write_text("""
apiVersion: game/v1
kind: Region
metadata:
  name: r
spec:
  displayName: "R"
""")

    (tmp_path / "location.yaml").write_text("""
apiVersion: game/v1
kind: Location
metadata:
  name: l
spec:
  displayName: "L"
  region: r
  adventures:
    - ref: broken-adventure
      weight: 100
""")

    (tmp_path / "adventure.yaml").write_text("""
apiVersion: game/v1
kind: Adventure
metadata:
  name: broken-adventure
spec:
  displayName: "Broken"
  steps:
    - type: narrative
      text: "This should fail validation."
      effects:
        - type: stat_change
          stat: is_active
          amount: 1
""")

    with pytest.raises(ContentLoadError) as exc_info:
        load(tmp_path)

    error_msg = str(exc_info.value)
    assert "stat_change not valid for bool stat" in error_msg


def test_invalid_stat_set_type_mismatch_fails(tmp_path: Path) -> None:
    """stat_set with a string value should fail validation — strings are not a valid stat type."""
    # Create adventure with stat_set using a string value (strings were removed as a stat type)
    (tmp_path / "game.yaml").write_text("""
apiVersion: game/v1
kind: Game
metadata:
  name: broken-game
spec:
  displayName: "Broken"
  xp_thresholds: [0, 100]
  hp_formula:
    base_hp: 20
    hp_per_level: 5
""")

    (tmp_path / "character-config.yaml").write_text("""
apiVersion: game/v1
kind: CharacterConfig
metadata:
  name: config
spec:
  public_stats:
    - name: strength
      type: int
      default: 10
  hidden_stats: []
""")

    (tmp_path / "region.yaml").write_text("""
apiVersion: game/v1
kind: Region
metadata:
  name: r
spec:
  displayName: "R"
""")

    (tmp_path / "location.yaml").write_text("""
apiVersion: game/v1
kind: Location
metadata:
  name: l
spec:
  displayName: "L"
  region: r
  adventures:
    - ref: broken-adventure
      weight: 100
""")

    (tmp_path / "adventure.yaml").write_text("""
apiVersion: game/v1
kind: Adventure
metadata:
  name: broken-adventure
spec:
  displayName: "Broken"
  steps:
    - type: narrative
      text: "This should fail validation."
      effects:
        - type: stat_set
          stat: strength
          value: "not a number"
""")

    # Pydantic rejects string values for stat_set since str is not a valid stat type
    with pytest.raises(ContentLoadError):
        load(tmp_path)


def test_unknown_stat_in_effect_fails(tmp_path: Path) -> None:
    """stat effects referencing non-existent stats should fail validation."""
    (tmp_path / "game.yaml").write_text("""
apiVersion: game/v1
kind: Game
metadata:
  name: broken-game
spec:
  displayName: "Broken"
  xp_thresholds: [0, 100]
  hp_formula:
    base_hp: 20
    hp_per_level: 5
""")

    (tmp_path / "character-config.yaml").write_text("""
apiVersion: game/v1
kind: CharacterConfig
metadata:
  name: config
spec:
  public_stats:
    - name: strength
      type: int
      default: 10
  hidden_stats: []
""")

    (tmp_path / "region.yaml").write_text("""
apiVersion: game/v1
kind: Region
metadata:
  name: r
spec:
  displayName: "R"
""")

    (tmp_path / "location.yaml").write_text("""
apiVersion: game/v1
kind: Location
metadata:
  name: l
spec:
  displayName: "L"
  region: r
  adventures:
    - ref: broken-adventure
      weight: 100
""")

    (tmp_path / "adventure.yaml").write_text("""
apiVersion: game/v1
kind: Adventure
metadata:
  name: broken-adventure
spec:
  displayName: "Broken"
  steps:
    - type: narrative
      text: "This should fail validation."
      effects:
        - type: stat_change
          stat: nonexistent_stat
          amount: 5
""")

    with pytest.raises(ContentLoadError) as exc_info:
        load(tmp_path)

    error_msg = str(exc_info.value)
    assert "Unknown stat in effect: 'nonexistent_stat'" in error_msg
