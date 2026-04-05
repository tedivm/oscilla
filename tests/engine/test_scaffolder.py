"""Tests for scaffolder.py — YAML manifest file creation."""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from oscilla.engine.scaffolder import (
    scaffold_adventure,
    scaffold_enemy,
    scaffold_item,
    scaffold_location,
    scaffold_quest,
    scaffold_region,
)

_yaml = YAML(typ="safe")


def test_scaffold_region_creates_file(tmp_path: Path) -> None:
    result = scaffold_region(
        games_path=tmp_path,
        game_name="test-game",
        name="dark-forest",
        display_name="Dark Forest",
    )
    assert result.exists()


def test_scaffold_region_yaml_has_kind(tmp_path: Path) -> None:
    result = scaffold_region(
        games_path=tmp_path,
        game_name="test-game",
        name="dark-forest",
        display_name="Dark Forest",
    )
    with result.open() as f:
        data = _yaml.load(f)
    assert data["kind"] == "Region"


def test_scaffold_region_yaml_has_name(tmp_path: Path) -> None:
    result = scaffold_region(
        games_path=tmp_path,
        game_name="test-game",
        name="dark-forest",
        display_name="Dark Forest",
    )
    with result.open() as f:
        data = _yaml.load(f)
    assert data["metadata"]["name"] == "dark-forest"


def test_scaffold_region_with_parent(tmp_path: Path) -> None:
    result = scaffold_region(
        games_path=tmp_path,
        game_name="test-game",
        name="deep-forest",
        display_name="Deep Forest",
        parent="dark-forest",
    )
    with result.open() as f:
        data = _yaml.load(f)
    assert data["spec"]["parent"] == "dark-forest"


def test_scaffold_location_creates_file(tmp_path: Path) -> None:
    result = scaffold_location(
        games_path=tmp_path,
        game_name="test-game",
        name="old-mill",
        display_name="Old Mill",
        region="dark-forest",
    )
    assert result.exists()


def test_scaffold_location_yaml_has_region(tmp_path: Path) -> None:
    result = scaffold_location(
        games_path=tmp_path,
        game_name="test-game",
        name="old-mill",
        display_name="Old Mill",
        region="dark-forest",
    )
    with result.open() as f:
        data = _yaml.load(f)
    assert data["spec"]["region"] == "dark-forest"


def test_scaffold_adventure_creates_file(tmp_path: Path) -> None:
    result = scaffold_adventure(
        games_path=tmp_path,
        game_name="test-game",
        name="find-key",
        display_name="Find the Key",
        region="dark-forest",
        location="old-mill",
    )
    assert result.exists()


def test_scaffold_adventure_yaml_has_steps(tmp_path: Path) -> None:
    result = scaffold_adventure(
        games_path=tmp_path,
        game_name="test-game",
        name="find-key",
        display_name="Find the Key",
        region="dark-forest",
        location="old-mill",
    )
    with result.open() as f:
        data = _yaml.load(f)
    assert len(data["spec"]["steps"]) > 0


def test_scaffold_enemy_creates_file(tmp_path: Path) -> None:
    result = scaffold_enemy(
        games_path=tmp_path,
        game_name="test-game",
        name="troll",
        display_name="Bridge Troll",
    )
    assert result.exists()


def test_scaffold_enemy_yaml_has_kind(tmp_path: Path) -> None:
    result = scaffold_enemy(
        games_path=tmp_path,
        game_name="test-game",
        name="troll",
        display_name="Bridge Troll",
    )
    with result.open() as f:
        data = _yaml.load(f)
    assert data["kind"] == "Enemy"


def test_scaffold_item_creates_file(tmp_path: Path) -> None:
    result = scaffold_item(
        games_path=tmp_path,
        game_name="test-game",
        name="iron-key",
        display_name="Iron Key",
        category="key",
    )
    assert result.exists()


def test_scaffold_item_yaml_has_kind(tmp_path: Path) -> None:
    result = scaffold_item(
        games_path=tmp_path,
        game_name="test-game",
        name="iron-key",
        display_name="Iron Key",
        category="key",
    )
    with result.open() as f:
        data = _yaml.load(f)
    assert data["kind"] == "Item"


def test_scaffold_quest_creates_file(tmp_path: Path) -> None:
    result = scaffold_quest(
        games_path=tmp_path,
        game_name="test-game",
        name="main-quest",
        display_name="Main Quest",
    )
    assert result.exists()


def test_scaffold_quest_yaml_has_kind(tmp_path: Path) -> None:
    result = scaffold_quest(
        games_path=tmp_path,
        game_name="test-game",
        name="main-quest",
        display_name="Main Quest",
    )
    with result.open() as f:
        data = _yaml.load(f)
    assert data["kind"] == "Quest"
