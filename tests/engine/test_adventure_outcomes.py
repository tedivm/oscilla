"""Tests for adventure outcome definitions and outcome tracking."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from oscilla.engine.character import CharacterState, CharacterStatistics
from oscilla.engine.loader import ContentLoadError, load_from_disk

# ---------------------------------------------------------------------------
# Helpers — inline YAML snippets for loader-based tests
# ---------------------------------------------------------------------------

_MINIMAL_GAME_YAML = """\
apiVersion: oscilla/v1
kind: Game
metadata:
  name: test-game
spec:
  displayName: "Test"
"""

_GAME_YAML_WITH_OUTCOMES = """\
apiVersion: oscilla/v1
kind: Game
metadata:
  name: test-game
spec:
  displayName: "Test"
  outcomes:
    - discovered
    - rescued
"""

_CHAR_CONFIG_YAML = """\
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test-config
spec:
  public_stats: []
"""

_REGION_YAML = """\
apiVersion: oscilla/v1
kind: Region
metadata:
  name: test-region-root
spec:
  displayName: "Test Region"
"""

_LOCATION_YAML = """\
apiVersion: oscilla/v1
kind: Location
metadata:
  name: test-location
spec:
  displayName: "Test Location"
  region: test-region-root
"""


def _write_base_content(tmp_path: Path, game_yaml: str = _MINIMAL_GAME_YAML) -> None:
    """Write the minimum required manifests into tmp_path."""
    (tmp_path / "game.yaml").write_text(game_yaml, encoding="utf-8")
    (tmp_path / "char.yaml").write_text(_CHAR_CONFIG_YAML, encoding="utf-8")
    (tmp_path / "region.yaml").write_text(_REGION_YAML, encoding="utf-8")
    (tmp_path / "location.yaml").write_text(_LOCATION_YAML, encoding="utf-8")


def _adventure_yaml(outcome: str) -> str:
    return f"""\
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: test-adventure
spec:
  displayName: "Test Adventure"
  steps:
    - type: narrative
      text: "Hello"
      effects:
        - type: end_adventure
          outcome: "{outcome}"
"""


# ---------------------------------------------------------------------------
# Loader validation tests
# ---------------------------------------------------------------------------


def test_loader_accepts_builtin_outcome_completed(tmp_path: Path) -> None:
    """Built-in outcome 'completed' is accepted without declaring in game.yaml."""
    _write_base_content(tmp_path)
    (tmp_path / "adventure.yaml").write_text(_adventure_yaml("completed"), encoding="utf-8")
    registry, _ = load_from_disk(tmp_path)
    assert registry.adventures.require("test-adventure", "Adventure") is not None


def test_loader_accepts_builtin_outcome_defeated(tmp_path: Path) -> None:
    """Built-in outcome 'defeated' is accepted without declaring in game.yaml."""
    _write_base_content(tmp_path)
    (tmp_path / "adventure.yaml").write_text(_adventure_yaml("defeated"), encoding="utf-8")
    registry, _ = load_from_disk(tmp_path)
    assert registry.adventures.require("test-adventure", "Adventure") is not None


def test_loader_accepts_builtin_outcome_fled(tmp_path: Path) -> None:
    """Built-in outcome 'fled' is accepted without declaring in game.yaml."""
    _write_base_content(tmp_path)
    (tmp_path / "adventure.yaml").write_text(_adventure_yaml("fled"), encoding="utf-8")
    registry, _ = load_from_disk(tmp_path)
    assert registry.adventures.require("test-adventure", "Adventure") is not None


def test_loader_accepts_custom_outcome_declared_in_game_yaml(tmp_path: Path) -> None:
    """A custom outcome declared in game.yaml outcomes list is accepted."""
    _write_base_content(tmp_path, game_yaml=_GAME_YAML_WITH_OUTCOMES)
    (tmp_path / "adventure.yaml").write_text(_adventure_yaml("discovered"), encoding="utf-8")
    registry, _ = load_from_disk(tmp_path)
    assert registry.adventures.require("test-adventure", "Adventure") is not None


def test_loader_rejects_undeclared_custom_outcome(tmp_path: Path) -> None:
    """An outcome that is neither built-in nor declared in game.yaml raises ContentLoadError."""
    _write_base_content(tmp_path)
    (tmp_path / "adventure.yaml").write_text(_adventure_yaml("secret-ending"), encoding="utf-8")
    with pytest.raises(ContentLoadError) as exc_info:
        load_from_disk(tmp_path)
    assert "secret-ending" in str(exc_info.value)


def test_loader_rejects_undeclared_custom_outcome_not_in_list(tmp_path: Path) -> None:
    """A custom outcome not in the declared list even when some outcomes exist is rejected."""
    _write_base_content(tmp_path, game_yaml=_GAME_YAML_WITH_OUTCOMES)
    # "rescued" is in game.yaml but "mystery" is not
    (tmp_path / "adventure.yaml").write_text(_adventure_yaml("mystery"), encoding="utf-8")
    with pytest.raises(ContentLoadError) as exc_info:
        load_from_disk(tmp_path)
    assert "mystery" in str(exc_info.value)


# ---------------------------------------------------------------------------
# CharacterStatistics.record_adventure_outcome unit tests
# ---------------------------------------------------------------------------


def _make_statistics() -> CharacterStatistics:
    return CharacterStatistics()


def test_record_adventure_outcome_first_entry() -> None:
    """First outcome for an adventure initialises the nested dict with count 1."""
    stats = _make_statistics()
    stats.record_adventure_outcome(adventure_ref="cave", outcome="completed")
    assert stats.adventure_outcome_counts == {"cave": {"completed": 1}}


def test_record_adventure_outcome_increments_on_repeat() -> None:
    """Repeated outcomes for the same adventure increment the count."""
    stats = _make_statistics()
    stats.record_adventure_outcome(adventure_ref="cave", outcome="completed")
    stats.record_adventure_outcome(adventure_ref="cave", outcome="completed")
    stats.record_adventure_outcome(adventure_ref="cave", outcome="completed")
    assert stats.adventure_outcome_counts["cave"]["completed"] == 3


def test_record_adventure_outcome_multiple_outcomes_tracked_independently() -> None:
    """Different outcome names for the same adventure are tracked independently."""
    stats = _make_statistics()
    stats.record_adventure_outcome(adventure_ref="cave", outcome="completed")
    stats.record_adventure_outcome(adventure_ref="cave", outcome="fled")
    stats.record_adventure_outcome(adventure_ref="cave", outcome="completed")
    assert stats.adventure_outcome_counts["cave"]["completed"] == 2
    assert stats.adventure_outcome_counts["cave"]["fled"] == 1


def test_record_adventure_outcome_multiple_adventures_tracked_independently() -> None:
    """Outcomes for different adventures are tracked under separate keys."""
    stats = _make_statistics()
    stats.record_adventure_outcome(adventure_ref="cave", outcome="completed")
    stats.record_adventure_outcome(adventure_ref="forest", outcome="completed")
    assert "cave" in stats.adventure_outcome_counts
    assert "forest" in stats.adventure_outcome_counts
    assert stats.adventure_outcome_counts["cave"]["completed"] == 1
    assert stats.adventure_outcome_counts["forest"]["completed"] == 1


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


def _make_player() -> CharacterState:
    return CharacterState(
        character_id=uuid4(),
        name="Tester",
        character_class=None,
        prestige_count=0,
        current_location=None,
        stats={},
    )


def test_adventure_outcome_counts_serialized_in_to_dict() -> None:
    """adventure_outcome_counts is included under the 'statistics' key in to_dict()."""
    player = _make_player()
    player.statistics.record_adventure_outcome(adventure_ref="cave", outcome="completed")
    player.statistics.record_adventure_outcome(adventure_ref="cave", outcome="fled")
    player.statistics.record_adventure_outcome(adventure_ref="forest", outcome="completed")

    data = player.to_dict()
    stats = data["statistics"]
    assert stats["adventure_outcome_counts"] == {
        "cave": {"completed": 1, "fled": 1},
        "forest": {"completed": 1},
    }


def test_adventure_outcome_counts_defaults_to_empty_dict() -> None:
    """A fresh CharacterState / CharacterStatistics has an empty adventure_outcome_counts."""
    player = _make_player()
    assert player.statistics.adventure_outcome_counts == {}
