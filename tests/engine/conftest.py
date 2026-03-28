"""Shared fixtures and helpers for engine tests."""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from oscilla.engine.loader import load
from oscilla.engine.player import PlayerState
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

    def __init__(self, menu_responses: List[int] | None = None) -> None:
        self.texts: List[str] = []
        self.menus: List[tuple[str, List[str]]] = []
        self.combat_rounds: List[tuple[int, int, str, str]] = []
        self.acks: int = 0
        self._menu_responses: List[int] = list(menu_responses or [])

    def show_text(self, text: str) -> None:
        self.texts.append(text)

    def show_menu(self, prompt: str, options: List[str]) -> int:
        self.menus.append((prompt, options))
        return self._menu_responses.pop(0) if self._menu_responses else 1

    def show_combat_round(
        self,
        player_hp: int,
        enemy_hp: int,
        player_name: str,
        enemy_name: str,
    ) -> None:
        self.combat_rounds.append((player_hp, enemy_hp, player_name, enemy_name))

    def wait_for_ack(self) -> None:
        self.acks += 1


# ---------------------------------------------------------------------------
# Registry fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def minimal_registry() -> ContentRegistry:
    return load(FIXTURES / "minimal")


@pytest.fixture(scope="session")
def combat_registry() -> ContentRegistry:
    return load(FIXTURES / "combat-pipeline")


@pytest.fixture(scope="session")
def condition_gates_registry() -> ContentRegistry:
    return load(FIXTURES / "condition-gates")


@pytest.fixture(scope="session")
def region_chain_registry() -> ContentRegistry:
    return load(FIXTURES / "region-chain")


# ---------------------------------------------------------------------------
# Player fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_player(minimal_registry: ContentRegistry) -> PlayerState:
    """Level-1 player built from the minimal fixture set."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None
    return PlayerState.new_player(
        name="Tester",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )


@pytest.fixture
def combat_player(combat_registry: ContentRegistry) -> PlayerState:
    """Level-1 player built from the combat-pipeline fixture set."""
    assert combat_registry.game is not None
    assert combat_registry.character_config is not None
    return PlayerState.new_player(
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
