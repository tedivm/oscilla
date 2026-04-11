"""Shared fixtures and helpers for engine tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.loader import load_from_disk
from oscilla.engine.registry import ContentRegistry

FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"


# ---------------------------------------------------------------------------
# MockTUI
# ---------------------------------------------------------------------------


class MockTUI:
    """Implements TUICallbacks for testing. Records all calls and replays
    pre-configured menu responses in order. Returns choice 1 when the queue
    is exhausted.
    """

    def __init__(
        self,
        menu_responses: List[int] | None = None,
        text_responses: List[str] | None = None,
        skill_menu_responses: List[int | None] | None = None,
    ) -> None:
        self.texts: List[str] = []
        self.menus: List[tuple[str, List[str]]] = []
        self.combat_rounds: List[tuple[int, int, str, str]] = []
        self.acks: int = 0
        self.input_prompts: List[str] = []
        self.skill_menus: List[List[Dict[str, Any]]] = []
        self._menu_responses: List[int] = list(menu_responses or [])
        self._text_responses: List[str] = list(text_responses or [])
        self._skill_menu_responses: List[int | None] = list(skill_menu_responses or [])

    async def show_text(self, text: str) -> None:
        self.texts.append(text)

    async def show_menu(self, prompt: str, options: List[str]) -> int:
        self.menus.append((prompt, options))
        return self._menu_responses.pop(0) if self._menu_responses else 1

    async def show_combat_round(
        self,
        player_hp: int,
        enemy_hp: int,
        player_name: str,
        enemy_name: str,
    ) -> None:
        self.combat_rounds.append((player_hp, enemy_hp, player_name, enemy_name))

    async def wait_for_ack(self) -> None:
        self.acks += 1

    async def input_text(self, prompt: str) -> str:
        self.input_prompts.append(prompt)
        return self._text_responses.pop(0) if self._text_responses else "TestCharacter"

    async def show_skill_menu(self, skills: List[Dict[str, Any]]) -> int | None:
        self.skill_menus.append(skills)
        if self._skill_menu_responses:
            return self._skill_menu_responses.pop(0)
        # Fall back to _menu_responses for backward compatibility.
        if self._menu_responses:
            choice = self._menu_responses.pop(0)
            return choice if choice > 0 else None
        return None


# ---------------------------------------------------------------------------
# Registry fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def minimal_registry() -> ContentRegistry:
    registry, _warnings = load_from_disk(FIXTURES / "minimal")
    return registry


@pytest.fixture(scope="session")
def combat_registry() -> ContentRegistry:
    registry, _warnings = load_from_disk(FIXTURES / "combat-pipeline")
    return registry


@pytest.fixture(scope="session")
def condition_gates_registry() -> ContentRegistry:
    registry, _warnings = load_from_disk(FIXTURES / "condition-gates")
    return registry


@pytest.fixture(scope="session")
def region_chain_registry() -> ContentRegistry:
    registry, _warnings = load_from_disk(FIXTURES / "region-chain")
    return registry


@pytest.fixture(scope="session")
def ingame_time_registry() -> ContentRegistry:
    registry, _warnings = load_from_disk(FIXTURES / "ingame-time")
    return registry


# ---------------------------------------------------------------------------
# Player fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_player(minimal_registry: ContentRegistry) -> CharacterState:
    """Level-1 player built from the minimal fixture set."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None
    return CharacterState.new_character(
        name="Tester",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )


@pytest.fixture
def combat_player(combat_registry: ContentRegistry) -> CharacterState:
    """Level-1 player built from the combat-pipeline fixture set."""
    assert combat_registry.game is not None
    assert combat_registry.character_config is not None
    return CharacterState.new_character(
        name="Fighter",
        game_manifest=combat_registry.game,
        character_config=combat_registry.character_config,
    )


# ---------------------------------------------------------------------------
# TUI fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_tui() -> MockTUI:
    return MockTUI()


@pytest.fixture
def minimal_quest_registry() -> ContentRegistry:
    """Registry with a two-stage quest (stage-a → stage-b terminal) for unit tests."""
    from oscilla.engine.models.quest import QuestManifest

    registry = ContentRegistry()
    quest = QuestManifest.model_validate(
        {
            "apiVersion": "oscilla/v1",
            "kind": "Quest",
            "metadata": {"name": "test-quest"},
            "spec": {
                "displayName": "Test Quest",
                "entry_stage": "stage-a",
                "stages": [
                    {
                        "name": "stage-a",
                        "advance_on": ["quest-a-done"],
                        "next_stage": "stage-b",
                    },
                    {
                        "name": "stage-b",
                        "terminal": True,
                        "completion_effects": [{"type": "milestone_grant", "milestone": "quest-complete"}],
                    },
                ],
            },
        }
    )
    registry.quests.register(quest)
    return registry
