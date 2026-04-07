"""Tests for the quest_stage condition type."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.conditions import evaluate
from oscilla.engine.loader import ContentLoadError, load
from oscilla.engine.models.base import QuestStageCondition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player() -> CharacterState:
    return CharacterState(
        character_id=uuid4(),
        name="Tester",
        character_class=None,
        level=1,
        xp=0,
        hp=20,
        max_hp=20,
        prestige_count=0,
        current_location=None,
        stats={},
    )


def _cond(quest: str, stage: str) -> QuestStageCondition:
    return QuestStageCondition(type="quest_stage", quest=quest, stage=stage)


# ---------------------------------------------------------------------------
# Condition evaluator tests (pure unit — no loader needed)
# ---------------------------------------------------------------------------


def test_quest_stage_true_when_active_at_matching_stage() -> None:
    """Returns True when the quest is active and at the specified stage."""
    player = _make_player()
    player.active_quests["find-artifact"] = "searching"
    assert evaluate(condition=_cond("find-artifact", "searching"), player=player) is True


def test_quest_stage_false_when_active_at_different_stage() -> None:
    """Returns False when the quest is active but at a different stage."""
    player = _make_player()
    player.active_quests["find-artifact"] = "found"
    assert evaluate(condition=_cond("find-artifact", "searching"), player=player) is False


def test_quest_stage_false_when_quest_not_active() -> None:
    """Returns False when the quest is not in active_quests at all."""
    player = _make_player()
    assert evaluate(condition=_cond("find-artifact", "searching"), player=player) is False


def test_quest_stage_false_when_quest_completed() -> None:
    """Returns False when the quest is completed (in completed_quests, not active_quests)."""
    player = _make_player()
    player.completed_quests.add("find-artifact")
    assert evaluate(condition=_cond("find-artifact", "searching"), player=player) is False


# ---------------------------------------------------------------------------
# Loader validation tests
# ---------------------------------------------------------------------------

_GAME_YAML = """\
apiVersion: oscilla/v1
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

_LOCATION_YAML_TEMPLATE = """\
apiVersion: oscilla/v1
kind: Location
metadata:
  name: test-location
spec:
  displayName: "Test Location"
  region: test-region-root
{extra}"""

_QUEST_YAML = """\
apiVersion: oscilla/v1
kind: Quest
metadata:
  name: test-quest
spec:
  displayName: "Test Quest"
  entry_stage: searching
  stages:
    - name: searching
      description: "Looking for the item."
      advance_on:
        - item-found
      next_stage: done
    - name: done
      description: "Quest complete."
      terminal: true
"""


def _write_base(tmp_path: Path, include_quest: bool = True) -> None:
    (tmp_path / "game.yaml").write_text(_GAME_YAML, encoding="utf-8")
    (tmp_path / "char.yaml").write_text(_CHAR_CONFIG_YAML, encoding="utf-8")
    (tmp_path / "region.yaml").write_text(_REGION_YAML, encoding="utf-8")
    if include_quest:
        (tmp_path / "quest.yaml").write_text(_QUEST_YAML, encoding="utf-8")


def test_loader_accepts_valid_quest_stage_condition(tmp_path: Path) -> None:
    """A location with a valid quest_stage condition loads without error."""
    _write_base(tmp_path)
    location_yaml = _LOCATION_YAML_TEMPLATE.format(
        extra="  unlock:\n    type: quest_stage\n    quest: test-quest\n    stage: searching"
    )
    (tmp_path / "location.yaml").write_text(location_yaml, encoding="utf-8")
    registry, _ = load(tmp_path)
    assert registry.locations.require("test-location", "Location") is not None


def test_loader_rejects_unknown_quest_ref(tmp_path: Path) -> None:
    """A quest_stage condition referencing a non-existent quest raises ContentLoadError."""
    _write_base(tmp_path)
    location_yaml = _LOCATION_YAML_TEMPLATE.format(
        extra="  unlock:\n    type: quest_stage\n    quest: nonexistent-quest\n    stage: searching"
    )
    (tmp_path / "location.yaml").write_text(location_yaml, encoding="utf-8")
    with pytest.raises(ContentLoadError) as exc_info:
        load(tmp_path)
    assert "nonexistent-quest" in str(exc_info.value)


def test_loader_rejects_unknown_stage_name(tmp_path: Path) -> None:
    """A quest_stage condition referencing a non-existent stage name raises ContentLoadError."""
    _write_base(tmp_path)
    location_yaml = _LOCATION_YAML_TEMPLATE.format(
        extra="  unlock:\n    type: quest_stage\n    quest: test-quest\n    stage: nonexistent-stage"
    )
    (tmp_path / "location.yaml").write_text(location_yaml, encoding="utf-8")
    with pytest.raises(ContentLoadError) as exc_info:
        load(tmp_path)
    assert "nonexistent-stage" in str(exc_info.value)
