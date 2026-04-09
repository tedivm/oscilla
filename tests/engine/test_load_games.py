"""Tests for the load_games() multi-package loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from oscilla.engine.loader import ContentLoadError, load_games
from oscilla.engine.registry import ContentRegistry

FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"
MULTI_GAME_LIBRARY = FIXTURES / "multi-game-library"


def test_load_games_returns_both_packages() -> None:
    games, _warnings = load_games(MULTI_GAME_LIBRARY)
    assert set(games.keys()) == {"test-alpha", "test-beta"}
    assert isinstance(games["test-alpha"], ContentRegistry)
    assert isinstance(games["test-beta"], ContentRegistry)


def test_load_games_skips_dir_without_game_yaml() -> None:
    """Subdirectories without game.yaml (e.g. extras/) must be silently skipped."""
    games, _warnings = load_games(MULTI_GAME_LIBRARY)
    assert "extras" not in games


def test_load_games_each_package_has_expected_content() -> None:
    games, _warnings = load_games(MULTI_GAME_LIBRARY)
    for key in ("test-alpha", "test-beta"):
        reg = games[key]
        assert reg.game is not None
        assert reg.character_config is not None
        assert len(reg.regions) == 1
        assert len(reg.locations) == 1
        assert len(reg.adventures) == 1


def test_load_games_empty_library(tmp_path: Path) -> None:
    """A library root with no subdirectories returns an empty dict."""
    games, _warnings = load_games(tmp_path)
    assert games == {}


def test_load_games_single_package(tmp_path: Path) -> None:
    """A library root with exactly one valid package returns a single-entry dict."""
    import shutil

    shutil.copytree(MULTI_GAME_LIBRARY / "test-alpha", tmp_path / "test-alpha")
    games, _warnings = load_games(tmp_path)
    assert list(games.keys()) == ["test-alpha"]


def test_load_games_error_in_one_package_raises(tmp_path: Path) -> None:
    """If a package contains invalid content, ContentLoadError is raised with package prefix."""
    import shutil

    shutil.copytree(MULTI_GAME_LIBRARY / "test-alpha", tmp_path / "good-game")
    bad_game = tmp_path / "bad-game"
    bad_game.mkdir()
    # game.yaml exists so the package is detected but an adventure ref is broken
    (bad_game / "game.yaml").write_text(
        "apiVersion: oscilla/v1\nkind: Game\nmetadata:\n  name: bad-game\nspec:\n  displayName: Bad\n",
        encoding="utf-8",
    )
    (bad_game / "character-config.yaml").write_text(
        "apiVersion: oscilla/v1\nkind: CharacterConfig\nmetadata:\n  name: cfg\n"
        "spec:\n  public_stats: []\n  hidden_stats: []\n",
        encoding="utf-8",
    )
    (bad_game / "region.yaml").write_text(
        "apiVersion: oscilla/v1\nkind: Region\nmetadata:\n  name: r\nspec:\n  displayName: R\n  description: R\n",
        encoding="utf-8",
    )
    # Location references a nonexistent adventure to trigger a validation error
    (bad_game / "location.yaml").write_text(
        "apiVersion: oscilla/v1\nkind: Location\nmetadata:\n  name: loc\n"
        "spec:\n  displayName: L\n  description: L\n  region: r\n"
        "  adventures:\n    - ref: nonexistent-adventure\n      weight: 100\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentLoadError) as exc_info:
        load_games(tmp_path)

    assert "bad-game" in str(exc_info.value)
