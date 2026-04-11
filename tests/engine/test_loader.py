"""Tests for the content loader — scan, parse, validate_references, build_effective_conditions."""

from __future__ import annotations

from pathlib import Path

import pytest

from oscilla.engine.loader import ContentLoadError, load_from_disk, parse, scan
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
        load_from_disk(FIXTURES / "broken-refs")
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
        "apiVersion: oscilla/v1\nkind: NotARealKind\nmetadata:\n  name: x\nspec: {}\n",
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
apiVersion: oscilla/v1
kind: Game
metadata:
  name: test-game
spec:
  displayName: "Test"
"""


def test_loader_rejects_float_stat_type(tmp_path: Path) -> None:
    """A CharacterConfig with type: float is rejected at parse/load time."""
    (tmp_path / "game.yaml").write_text(_MINIMAL_GAME_YAML, encoding="utf-8")
    (tmp_path / "char.yaml").write_text(
        """\
apiVersion: oscilla/v1
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
        load_from_disk(tmp_path)


def test_loader_rejects_bounds_on_bool_stat(tmp_path: Path) -> None:
    """A CharacterConfig with bounds on a bool stat is rejected at load time."""
    (tmp_path / "game.yaml").write_text(_MINIMAL_GAME_YAML, encoding="utf-8")
    (tmp_path / "char.yaml").write_text(
        """\
apiVersion: oscilla/v1
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
        load_from_disk(tmp_path)


_GAME_YAML_WITHOUT_PRESTIGE = """\
apiVersion: oscilla/v1
kind: Game
metadata:
  name: test-game
spec:
  displayName: "Test"
"""

_GAME_YAML_WITH_PRESTIGE = """\
apiVersion: oscilla/v1
kind: Game
metadata:
  name: test-game
spec:
  displayName: "Test"
  prestige:
    carry_stats: []
"""

_ADVENTURE_WITH_PRESTIGE_EFFECT = """\
apiVersion: oscilla/v1
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
        load_from_disk(tmp_path)
    assert "prestige" in str(exc_info.value).lower()


def test_loader_accepts_prestige_effect_when_prestige_config_declared(tmp_path: Path) -> None:
    """A prestige effect is accepted when the game.yaml declares a prestige: block."""
    (tmp_path / "game.yaml").write_text(_GAME_YAML_WITH_PRESTIGE, encoding="utf-8")
    (tmp_path / "adventure.yaml").write_text(_ADVENTURE_WITH_PRESTIGE_EFFECT, encoding="utf-8")
    # Should not raise — warnings are fine.
    load_from_disk(tmp_path)


# ---------------------------------------------------------------------------
# Multi-document YAML parsing tests
# ---------------------------------------------------------------------------

_ITEM_DOC_SWORD = """\
apiVersion: oscilla/v1
kind: Item
metadata:
  name: sword
spec:
  displayName: "Sword"
  description: "A sharp sword."
  category: weapon
  stackable: false
  value: 10
"""

_ITEM_DOC_SHIELD = """\
apiVersion: oscilla/v1
kind: Item
metadata:
  name: shield
spec:
  displayName: "Shield"
  description: "A sturdy shield."
  category: armor
  stackable: false
  value: 8
"""

_ENEMY_DOC_GOBLIN = """\
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin
spec:
  displayName: "Goblin"
  description: "A small goblin."
  hp: 10
  attack: 3
  defense: 0
  xp_reward: 5
  loot: []
"""


def test_parse_multi_document_file(tmp_path: Path) -> None:
    """Two valid documents in one file both load successfully."""
    multi = tmp_path / "items.yaml"
    multi.write_text(_ITEM_DOC_SWORD + "---\n" + _ITEM_DOC_SHIELD, encoding="utf-8")
    manifests, errors = parse([multi])
    assert errors == []
    assert len(manifests) == 2
    names = {m.metadata.name for m in manifests}
    assert names == {"sword", "shield"}


def test_parse_multi_document_mixed_kinds(tmp_path: Path) -> None:
    """Documents of different kinds in one file both load successfully."""
    multi = tmp_path / "mixed.yaml"
    multi.write_text(_ITEM_DOC_SWORD + "---\n" + _ENEMY_DOC_GOBLIN, encoding="utf-8")
    manifests, errors = parse([multi])
    assert errors == []
    assert len(manifests) == 2
    kinds = {m.kind for m in manifests}
    assert kinds == {"Item", "Enemy"}


def test_parse_multi_document_error_attribution(tmp_path: Path) -> None:
    """An error in doc 2 of a multi-doc file cites [doc 2] in the error message."""
    # doc 2 has displayName as a number — invalid (must be a string)
    bad_doc = """\
apiVersion: oscilla/v1
kind: Item
metadata:
  name: bad-item
spec:
  displayName: 999
  description: "Bad"
  category: material
  stackable: false
  value: 1
"""
    multi = tmp_path / "items.yaml"
    multi.write_text(_ITEM_DOC_SWORD + "---\n" + bad_doc, encoding="utf-8")
    manifests, errors = parse([multi])
    assert len(errors) >= 1
    assert any("[doc 2]" in e.message for e in errors)


def test_parse_single_document_no_doc_index_suffix(tmp_path: Path) -> None:
    """Single-document files do not include [doc N] in error messages."""
    bad_doc = """\
apiVersion: oscilla/v1
kind: Item
metadata:
  name: bad-item
spec:
  displayName: 999
  description: "Bad"
  category: material
  stackable: false
  value: 1
"""
    single = tmp_path / "item.yaml"
    single.write_text(bad_doc, encoding="utf-8")
    _, errors = parse([single])
    assert all("[doc" not in e.message for e in errors)


def test_parse_empty_document_in_multi_doc_file(tmp_path: Path) -> None:
    """An empty document between --- dividers is reported as an error, not silently skipped."""
    multi = tmp_path / "items.yaml"
    multi.write_text(_ITEM_DOC_SWORD + "---\n" + "---\n" + _ITEM_DOC_SHIELD, encoding="utf-8")
    manifests, errors = parse([multi])
    # The two valid documents load; the empty one produces an error.
    assert len(manifests) == 2
    assert len(errors) == 1
    assert "Manifest must be a YAML mapping" in errors[0].message


_MINIMAL_CHAR_CONFIG_YAML = """\
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test-char-config
spec:
  public_stats:
    - name: strength
      type: int
      default: 10
      description: "Physical power"
  hidden_stats: []
"""


def test_load_single_file_path(tmp_path: Path) -> None:
    """load_from_disk() accepts a path to a single YAML file and processes all documents in it."""
    content_file = tmp_path / "content.yaml"
    content_file.write_text(_MINIMAL_GAME_YAML + "---\n" + _MINIMAL_CHAR_CONFIG_YAML, encoding="utf-8")
    registry, warnings = load_from_disk(content_file)
    assert registry.game is not None
    assert registry.character_config is not None


# ---------------------------------------------------------------------------
# Archetype reference validation tests (task 8.12)
# ---------------------------------------------------------------------------

_MINIMAL_ARCHETYPE_YAML = """\
apiVersion: oscilla/v1
kind: Archetype
metadata:
  name: test-warrior
spec:
  displayName: "Test Warrior"
"""

_MINIMAL_ADVENTURE_HAS_ARCHETYPE_YAML = """\
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: test-adv
spec:
  displayName: "Archetype Adventure"
  steps:
    - type: narrative
      text: "You become a warrior."
      effects:
        - type: archetype_add
          name: test-warrior
"""

_ADVENTURE_UNKNOWN_ARCHETYPE_YAML = """\
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: bad-adv
spec:
  displayName: "Bad Adventure"
  steps:
    - type: narrative
      text: "You are something."
      effects:
        - type: archetype_add
          name: undeclared-archetype
"""

_ADVENTURE_HAS_ARCHETYPE_CONDITION_YAML = """\
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: cond-adv
spec:
  displayName: "Condition Adventure"
  steps:
    - type: stat_check
      condition:
        type: has_archetype
        name: undeclared-archetype
"""


def test_archetype_refs_valid_passes(tmp_path: Path) -> None:
    """Valid archetype references in effects produce no errors."""
    (tmp_path / "game.yaml").write_text(_MINIMAL_GAME_YAML, encoding="utf-8")
    (tmp_path / "archetype.yaml").write_text(_MINIMAL_ARCHETYPE_YAML, encoding="utf-8")
    (tmp_path / "adventure.yaml").write_text(_MINIMAL_ADVENTURE_HAS_ARCHETYPE_YAML, encoding="utf-8")
    # Should not raise
    load_from_disk(tmp_path)


def test_archetype_add_unknown_ref_raises(tmp_path: Path) -> None:
    """archetype_add referring to an undeclared archetype raises ContentLoadError."""
    (tmp_path / "game.yaml").write_text(_MINIMAL_GAME_YAML, encoding="utf-8")
    (tmp_path / "adventure.yaml").write_text(_ADVENTURE_UNKNOWN_ARCHETYPE_YAML, encoding="utf-8")
    with pytest.raises(ContentLoadError) as exc_info:
        load_from_disk(tmp_path)
    assert "undeclared-archetype" in str(exc_info.value)


def test_archetype_condition_unknown_ref_raises(tmp_path: Path) -> None:
    """has_archetype condition referring to an undeclared archetype raises ContentLoadError."""
    (tmp_path / "game.yaml").write_text(_MINIMAL_GAME_YAML, encoding="utf-8")
    (tmp_path / "adventure.yaml").write_text(_ADVENTURE_HAS_ARCHETYPE_CONDITION_YAML, encoding="utf-8")
    with pytest.raises(ContentLoadError) as exc_info:
        load_from_disk(tmp_path)
    assert "undeclared-archetype" in str(exc_info.value)
