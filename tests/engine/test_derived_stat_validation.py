"""Load-time validation tests for derived stat definitions.

Covers task 11.5:
- stat_change targeting a derived stat is rejected at load time
- stat_set targeting a derived stat is rejected at load time
- Circular dependency between derived stats raises ContentLoadError
- Self-referential derived stat raises ContentLoadError
- Derived stat with a non-None default raises ContentLoadError
- bool derived stat raises ContentLoadError
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oscilla.engine.loader import ContentLoadError, load

# ---------------------------------------------------------------------------
# Common inline YAML helpers
# ---------------------------------------------------------------------------

_GAME_YAML = """\
apiVersion: oscilla/v1
kind: Game
metadata:
  name: test-game
spec:
  displayName: "Validation Test"
"""

_REGION_YAML = """\
apiVersion: oscilla/v1
kind: Region
metadata:
  name: test-region-root
spec:
  displayName: "Test Region"
  description: "Root region."
"""

_LOCATION_YAML = """\
apiVersion: oscilla/v1
kind: Location
metadata:
  name: test-location
spec:
  displayName: "Test Location"
  description: "A location."
  region: test-region-root
  adventures:
    - ref: test-adventure
      weight: 100
"""

_CHAR_CONFIG_WITH_DERIVED = """\
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test-config
spec:
  public_stats:
    - name: power
      type: int
      default: 10
      description: "Base power"
    - name: power_mod
      type: int
      derived: "{{ player.stats['power'] // 2 }}"
      description: "Half of power"
  hidden_stats: []
"""


def _write_base(tmp_path: Path) -> None:
    """Write the files common to every test scenario."""
    (tmp_path / "game.yaml").write_text(_GAME_YAML, encoding="utf-8")
    (tmp_path / "region.yaml").write_text(_REGION_YAML, encoding="utf-8")
    (tmp_path / "location.yaml").write_text(_LOCATION_YAML, encoding="utf-8")
    (tmp_path / "character-config.yaml").write_text(_CHAR_CONFIG_WITH_DERIVED, encoding="utf-8")


# ---------------------------------------------------------------------------
# stat_change / stat_set targeting a derived stat
# ---------------------------------------------------------------------------


def test_stat_change_targeting_derived_raises(tmp_path: Path) -> None:
    """stat_change effect that targets a derived stat is rejected at load time."""
    _write_base(tmp_path)
    (tmp_path / "test-adventure.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: test-adventure
spec:
  displayName: "Bad Adventure"
  steps:
    - type: narrative
      text: "This step writes to a derived stat."
      effects:
        - type: stat_change
          stat: power_mod
          amount: 1
""",
        encoding="utf-8",
    )
    with pytest.raises(ContentLoadError) as exc_info:
        load(tmp_path)
    assert "power_mod" in str(exc_info.value)


def test_stat_set_targeting_derived_raises(tmp_path: Path) -> None:
    """stat_set effect that targets a derived stat is rejected at load time."""
    _write_base(tmp_path)
    (tmp_path / "test-adventure.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: test-adventure
spec:
  displayName: "Bad Adventure"
  steps:
    - type: narrative
      text: "This step sets a derived stat directly."
      effects:
        - type: stat_set
          stat: power_mod
          value: 5
""",
        encoding="utf-8",
    )
    with pytest.raises(ContentLoadError) as exc_info:
        load(tmp_path)
    assert "power_mod" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Circular dependency detection
# ---------------------------------------------------------------------------


def test_circular_dependency_between_two_derived_raises(tmp_path: Path) -> None:
    """A → B → A circular dependency between two derived stats raises ContentLoadError."""
    (tmp_path / "game.yaml").write_text(_GAME_YAML, encoding="utf-8")
    (tmp_path / "region.yaml").write_text(_REGION_YAML, encoding="utf-8")
    (tmp_path / "location.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: Location
metadata:
  name: test-location
spec:
  displayName: "Test Location"
  description: "A location."
  region: test-region-root
  adventures:
    - ref: test-adventure
      weight: 100
""",
        encoding="utf-8",
    )
    # Minimal valid adventure (no derived-stat writes)
    (tmp_path / "test-adventure.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: test-adventure
spec:
  displayName: "Adventure"
  steps:
    - type: narrative
      text: "Hello."
""",
        encoding="utf-8",
    )
    (tmp_path / "character-config.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test-config
spec:
  public_stats:
    - name: base
      type: int
      default: 10
      description: "Base stat"
    - name: derived_a
      type: int
      derived: "{{ player.stats['derived_b'] + 1 }}"
      description: "Depends on derived_b"
    - name: derived_b
      type: int
      derived: "{{ player.stats['derived_a'] + 1 }}"
      description: "Depends on derived_a — circular!"
  hidden_stats: []
""",
        encoding="utf-8",
    )
    with pytest.raises(ContentLoadError) as exc_info:
        load(tmp_path)
    # Error message should mention circularity
    assert "circular" in str(exc_info.value).lower() or "cycle" in str(exc_info.value).lower()


def test_self_referential_derived_raises(tmp_path: Path) -> None:
    """A derived stat whose formula references itself raises ContentLoadError."""
    (tmp_path / "game.yaml").write_text(_GAME_YAML, encoding="utf-8")
    (tmp_path / "region.yaml").write_text(_REGION_YAML, encoding="utf-8")
    (tmp_path / "location.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: Location
metadata:
  name: test-location
spec:
  displayName: "Test Location"
  description: "A location."
  region: test-region-root
  adventures:
    - ref: test-adventure
      weight: 100
""",
        encoding="utf-8",
    )
    (tmp_path / "test-adventure.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: test-adventure
spec:
  displayName: "Adventure"
  steps:
    - type: narrative
      text: "Hello."
""",
        encoding="utf-8",
    )
    (tmp_path / "character-config.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test-config
spec:
  public_stats:
    - name: base
      type: int
      default: 10
      description: "Base stat"
    - name: self_loop
      type: int
      derived: "{{ player.stats['self_loop'] + 1 }}"
      description: "References itself — circular!"
  hidden_stats: []
""",
        encoding="utf-8",
    )
    with pytest.raises(ContentLoadError) as exc_info:
        load(tmp_path)
    assert "circular" in str(exc_info.value).lower() or "cycle" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Invalid derived stat definitions (caught by Pydantic validators)
# ---------------------------------------------------------------------------


def test_derived_stat_with_default_raises(tmp_path: Path) -> None:
    """A derived stat that also declares a default value is rejected at load time."""
    (tmp_path / "game.yaml").write_text(_GAME_YAML, encoding="utf-8")
    (tmp_path / "region.yaml").write_text(_REGION_YAML, encoding="utf-8")
    (tmp_path / "location.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: Location
metadata:
  name: test-location
spec:
  displayName: "Test Location"
  description: "A location."
  region: test-region-root
  adventures:
    - ref: test-adventure
      weight: 100
""",
        encoding="utf-8",
    )
    (tmp_path / "test-adventure.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: test-adventure
spec:
  displayName: "Adventure"
  steps:
    - type: narrative
      text: "Hello."
""",
        encoding="utf-8",
    )
    (tmp_path / "character-config.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test-config
spec:
  public_stats:
    - name: base
      type: int
      default: 10
      description: "Base stat"
    - name: derived_with_default
      type: int
      default: 0
      derived: "{{ player.stats['base'] * 2 }}"
      description: "Has both default and derived — invalid"
  hidden_stats: []
""",
        encoding="utf-8",
    )
    with pytest.raises(ContentLoadError):
        load(tmp_path)


def test_bool_derived_stat_raises(tmp_path: Path) -> None:
    """A bool stat with a derived formula is rejected at load time."""
    (tmp_path / "game.yaml").write_text(_GAME_YAML, encoding="utf-8")
    (tmp_path / "region.yaml").write_text(_REGION_YAML, encoding="utf-8")
    (tmp_path / "location.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: Location
metadata:
  name: test-location
spec:
  displayName: "Test Location"
  description: "A location."
  region: test-region-root
  adventures:
    - ref: test-adventure
      weight: 100
""",
        encoding="utf-8",
    )
    (tmp_path / "test-adventure.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: test-adventure
spec:
  displayName: "Adventure"
  steps:
    - type: narrative
      text: "Hello."
""",
        encoding="utf-8",
    )
    (tmp_path / "character-config.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test-config
spec:
  public_stats:
    - name: base
      type: int
      default: 10
      description: "Base stat"
    - name: bool_derived
      type: bool
      derived: "{{ player.stats['base'] > 5 }}"
      description: "Bool with derived formula — invalid"
  hidden_stats: []
""",
        encoding="utf-8",
    )
    with pytest.raises(ContentLoadError):
        load(tmp_path)
