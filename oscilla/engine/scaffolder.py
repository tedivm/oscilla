"""YAML manifest scaffolding for the content create command."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from ruamel.yaml import YAML

_yaml = YAML()
_yaml.default_flow_style = False


def _write_yaml(path: Path, data: Dict) -> None:
    """Write a YAML file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        _yaml.dump(data, f)


def scaffold_region(
    games_path: Path,
    game_name: str,
    name: str,
    display_name: str,
    description: str = "",
    parent: str | None = None,
) -> Path:
    data: Dict = {
        "apiVersion": "oscilla/v1",
        "kind": "Region",
        "metadata": {"name": name},
        "spec": {"displayName": display_name, "description": description},
    }
    if parent:
        data["spec"]["parent"] = parent
    path = games_path / game_name / "regions" / name / f"{name}.yaml"
    _write_yaml(path, data)
    return path


def scaffold_location(
    games_path: Path,
    game_name: str,
    name: str,
    display_name: str,
    region: str,
    description: str = "",
) -> Path:
    data: Dict = {
        "apiVersion": "oscilla/v1",
        "kind": "Location",
        "metadata": {"name": name},
        "spec": {
            "displayName": display_name,
            "description": description,
            "region": region,
            "adventures": [],
        },
    }
    path = games_path / game_name / "regions" / region / "locations" / name / f"{name}.yaml"
    _write_yaml(path, data)
    return path


def scaffold_adventure(
    games_path: Path,
    game_name: str,
    name: str,
    display_name: str,
    region: str,
    location: str,
    description: str = "",
) -> Path:
    data: Dict = {
        "apiVersion": "oscilla/v1",
        "kind": "Adventure",
        "metadata": {"name": name},
        "spec": {
            "displayName": display_name,
            "description": description,
            "steps": [
                {
                    "type": "narrative",
                    "text": "Your adventure begins here.",
                    "effects": [{"type": "end_adventure", "outcome": "completed"}],
                }
            ],
        },
    }
    path = games_path / game_name / "regions" / region / "locations" / location / "adventures" / f"{name}.yaml"
    _write_yaml(path, data)
    return path


def scaffold_enemy(
    games_path: Path,
    game_name: str,
    name: str,
    display_name: str,
    hp: int = 30,
    attack: int = 5,
    defense: int = 2,
    xp_reward: int = 20,
    description: str = "",
) -> Path:
    data: Dict = {
        "apiVersion": "oscilla/v1",
        "kind": "Enemy",
        "metadata": {"name": name},
        "spec": {
            "displayName": display_name,
            "description": description,
            "hp": hp,
            "attack": attack,
            "defense": defense,
            "xp_reward": xp_reward,
            "loot": [],
        },
    }
    path = games_path / game_name / "enemies" / f"{name}.yaml"
    _write_yaml(path, data)
    return path


def scaffold_item(
    games_path: Path,
    game_name: str,
    name: str,
    display_name: str,
    category: str,
    description: str = "",
) -> Path:
    data: Dict = {
        "apiVersion": "oscilla/v1",
        "kind": "Item",
        "metadata": {"name": name},
        "spec": {
            "displayName": display_name,
            "description": description,
            "category": category,
            "use_effects": [],
        },
    }
    path = games_path / game_name / "items" / f"{name}.yaml"
    _write_yaml(path, data)
    return path


def scaffold_quest(
    games_path: Path,
    game_name: str,
    name: str,
    display_name: str,
    entry_stage: str = "stage-1",
    description: str = "",
) -> Path:
    data: Dict = {
        "apiVersion": "oscilla/v1",
        "kind": "Quest",
        "metadata": {"name": name},
        "spec": {
            "displayName": display_name,
            "description": description,
            "entry_stage": entry_stage,
            "stages": [
                {
                    "name": entry_stage,
                    "description": "First stage",
                    "advance_on": ["my-milestone"],
                    "next_stage": "stage-complete",
                },
                {
                    "name": "stage-complete",
                    "description": "Quest complete",
                    "terminal": True,
                    "completion_effects": [],
                },
            ],
        },
    }
    path = games_path / game_name / "quests" / f"{name}.yaml"
    _write_yaml(path, data)
    return path
