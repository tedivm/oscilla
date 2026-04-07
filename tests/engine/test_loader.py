"""Tests for the content loader — scan, parse, validate_references, build_effective_conditions."""

from __future__ import annotations

from pathlib import Path

import pytest

from oscilla.engine.loader import ContentLoadError, load, parse, scan
from oscilla.engine.models.base import AllCondition, LevelCondition
from oscilla.engine.registry import ContentRegistry

FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"


def test_scan_returns_sorted_yaml_paths() -> None:
    paths = scan(FIXTURES / "minimal")
    assert len(paths) > 0
    assert all(p.suffix in {".yaml", ".yml"} for p in paths)
    assert paths == sorted(paths)


def test_load_minimal_succeeds(minimal_registry: ContentRegistry) -> None:
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None
    assert len(minimal_registry.regions) == 1
    assert len(minimal_registry.locations) == 1
    assert len(minimal_registry.adventures) == 1
    assert len(minimal_registry.enemies) == 1
    assert len(minimal_registry.items) == 1


def test_load_broken_refs_raises() -> None:
    with pytest.raises(ContentLoadError) as exc_info:
        load(FIXTURES / "broken-refs")
    # The error message should mention the missing adventure reference
    assert "nonexistent-adventure" in str(exc_info.value)


def test_parse_bad_yaml_accumulates_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("key: [unclosed bracket\n", encoding="utf-8")
    _, errors = parse([bad])
    assert len(errors) == 1
    assert "YAML parse error" in errors[0].message


def test_parse_unknown_kind_accumulates_error(tmp_path: Path) -> None:
    unknown = tmp_path / "unknown.yaml"
    unknown.write_text(
        "apiVersion: game/v1\nkind: NotARealKind\nmetadata:\n  name: x\nspec: {}\n",
        encoding="utf-8",
    )
    _, errors = parse([unknown])
    assert len(errors) == 1
    assert "Unknown kind" in errors[0].message


def test_region_chain_effective_unlock_inherits_ancestors(
    region_chain_registry: ContentRegistry,
) -> None:
    """The deep location's effective_unlock must require BOTH level 2 and level 3."""
    loc = region_chain_registry.locations.require("test-location-deep", "Location")
    cond = loc.spec.effective_unlock
    assert isinstance(cond, AllCondition)
    # Collect all level values from the flattened condition tree
    level_values = {c.value for c in cond.conditions if isinstance(c, LevelCondition)}
    assert 2 in level_values, "Level-2 ancestor condition should be present"
    assert 3 in level_values, "Level-3 own condition should be present"


def test_region_root_has_no_effective_unlock(
    region_chain_registry: ContentRegistry,
) -> None:
    root = region_chain_registry.regions.require("test-region-root", "Region")
    assert root.spec.effective_unlock is None


_MINIMAL_GAME_YAML = """\
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
"""


def test_loader_rejects_float_stat_type(tmp_path: Path) -> None:
    """A CharacterConfig with type: float is rejected at parse/load time."""
    (tmp_path / "game.yaml").write_text(_MINIMAL_GAME_YAML, encoding="utf-8")
    (tmp_path / "char.yaml").write_text(
        """\
apiVersion: game/v1
kind: CharacterConfig
metadata:
  name: test-config
spec:
  public_stats:
    - name: speed
      type: float
      default: 1.0
""",
        encoding="utf-8",
    )
    with pytest.raises(ContentLoadError):
        load(tmp_path)


def test_loader_rejects_bounds_on_bool_stat(tmp_path: Path) -> None:
    """A CharacterConfig with bounds on a bool stat is rejected at load time."""
    (tmp_path / "game.yaml").write_text(_MINIMAL_GAME_YAML, encoding="utf-8")
    (tmp_path / "char.yaml").write_text(
        """\
apiVersion: game/v1
kind: CharacterConfig
metadata:
  name: test-config
spec:
  public_stats:
    - name: is_blessed
      type: bool
      default: false
      bounds:
        min: 0
        max: 1
""",
        encoding="utf-8",
    )
    with pytest.raises(ContentLoadError):
        load(tmp_path)


_GAME_YAML_WITHOUT_PRESTIGE = """\
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
"""

_GAME_YAML_WITH_PRESTIGE = """\
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
  prestige:
    carry_stats: []
"""

_ADVENTURE_WITH_PRESTIGE_EFFECT = """\
apiVersion: game/v1
kind: Adventure
metadata:
  name: test-prestige-adventure
spec:
  displayName: "Prestige Ceremony"
  steps:
    - type: narrative
      text: "Your journey resets."
      effects:
        - type: prestige
"""


def test_loader_rejects_prestige_effect_without_prestige_config(tmp_path: Path) -> None:
    """A prestige effect in an adventure raises ContentLoadError when prestige: is absent from game.yaml."""
    (tmp_path / "game.yaml").write_text(_GAME_YAML_WITHOUT_PRESTIGE, encoding="utf-8")
    (tmp_path / "adventure.yaml").write_text(_ADVENTURE_WITH_PRESTIGE_EFFECT, encoding="utf-8")
    with pytest.raises(ContentLoadError) as exc_info:
        load(tmp_path)
    assert "prestige" in str(exc_info.value).lower()


def test_loader_accepts_prestige_effect_when_prestige_config_declared(tmp_path: Path) -> None:
    """A prestige effect is accepted when the game.yaml declares a prestige: block."""
    (tmp_path / "game.yaml").write_text(_GAME_YAML_WITH_PRESTIGE, encoding="utf-8")
    (tmp_path / "adventure.yaml").write_text(_ADVENTURE_WITH_PRESTIGE_EFFECT, encoding="utf-8")
    # Should not raise — warnings are fine.
    load(tmp_path)
