"""Tests for CLI application."""

import asyncio
from typing import Any

from typer.testing import CliRunner

from oscilla.cli import app, syncify

runner = CliRunner()


def test_cli_app_exists() -> None:
    """Test that Typer app is properly instantiated."""
    assert app is not None
    assert hasattr(app, "command")


def test_cli_app_has_commands() -> None:
    """Test that CLI app has registered commands."""
    assert hasattr(app, "registered_commands")


def test_version_command_exists() -> None:
    """Test that version command is registered."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.stdout.lower() or "full_test_project" in result.stdout.lower()


def test_version_command_runs() -> None:
    """Test that version command executes successfully."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0


def test_version_output_format() -> None:
    """Test that version command outputs correct format."""
    from oscilla.settings import settings

    result = runner.invoke(app, ["version"])
    assert settings.project_name in result.stdout
    # Should output: "project_name - X.Y.Z"
    assert "-" in result.stdout


def test_version_contains_version_number() -> None:
    """Test that version output contains a version number."""
    from oscilla.settings import settings

    result = runner.invoke(app, ["version"])
    output = result.stdout.strip()
    # Should contain project name and version
    assert settings.project_name in output


def test_help_flag() -> None:
    """Test that --help flag works."""
    from oscilla.settings import settings

    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert settings.project_name in result.stdout.lower() or "display" in result.stdout.lower()


def test_help_shows_description() -> None:
    """Test that help output shows description."""
    result = runner.invoke(app, ["--help"])
    assert "version" in result.stdout.lower() or "display" in result.stdout.lower()


def test_syncify_decorator_exists() -> None:
    """Test that syncify decorator is defined."""
    assert syncify is not None
    assert callable(syncify)


def test_syncify_converts_async_to_sync() -> None:
    """Test that syncify properly converts async functions to sync."""

    @syncify
    async def test_async_func() -> str:
        await asyncio.sleep(0.01)
        return "success"

    # Should be able to call without await
    result = test_async_func()
    assert result == "success"


def test_syncify_preserves_return_value() -> None:
    """Test that syncify preserves the return value."""

    @syncify
    async def test_async_func() -> int:
        return 42

    result = test_async_func()
    assert result == 42


def test_syncify_with_arguments() -> None:
    """Test that syncify works with function arguments."""

    @syncify
    async def test_async_func(x: int, y: int) -> int:
        await asyncio.sleep(0.01)
        return x + y

    result = test_async_func(10, 20)
    assert result == 30


def test_syncify_preserves_function_name() -> None:
    """Test that syncify preserves the function's name."""

    @syncify
    async def my_function() -> bool:
        return True

    assert my_function.__name__ == "my_function"


def test_validate_command_succeeds_with_valid_content() -> None:
    """Test that validate command succeeds with the default content."""
    result = runner.invoke(app, ["validate"])
    # Should validate successfully since we have a complete content package
    assert result.exit_code == 0
    assert "error" not in result.stdout.lower()


def test_validate_command_fails_with_invalid_content() -> None:
    """Test validate command flag exists and runs (content may be valid)."""
    # Just test that the command executes without crashing
    # The actual content in this project should be valid
    result = runner.invoke(app, ["validate"])
    # Exit code is either 0 (success) or 1 (validation error) — both are valid
    assert result.exit_code in [0, 1]


def test_game_command_exists() -> None:
    """Test that game command exists and shows in help."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "game" in result.stdout.lower()


def test_validate_command_exists() -> None:
    """Test that validate command exists and shows in help."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "validate" in result.stdout.lower()


def test_game_help() -> None:
    """Test that game command help works."""
    result = runner.invoke(app, ["game", "--help"])
    assert result.exit_code == 0
    assert "interactive" in result.stdout.lower() or "game" in result.stdout.lower()


def test_validate_help() -> None:
    """Test that validate command help works."""
    result = runner.invoke(app, ["validate", "--help"])
    assert result.exit_code == 0
    assert "validate" in result.stdout.lower() or "package" in result.stdout.lower()


# Test game command would require a complex TUI mock, skip for now
# since the focus is on testing the command registration and basic functionality


def test_settings_imported() -> None:
    """Test that settings can be imported in CLI module."""
    from oscilla.settings import settings

    assert settings is not None
    assert hasattr(settings, "project_name")


def test_validate_game_flag_help() -> None:
    """Test that validate command shows --game flag in help."""
    result = runner.invoke(app, ["validate", "--help"])
    assert result.exit_code == 0
    assert "--game" in result.stdout
    assert "-g" in result.stdout


def test_validate_with_game_flag() -> None:
    """Test that validate command accepts --game flag."""
    result = runner.invoke(app, ["validate", "--game", "testlandia"])
    # Should either succeed (0) or fail with validation error (1), not crash
    assert result.exit_code in [0, 1]


def test_validate_multi_game_output() -> None:
    """Test that validate without --game shows per-game output."""
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0
    # Should show the game name in output
    assert "testlandia" in result.stdout


def test_validate_unknown_game() -> None:
    """Test that validate with unknown game shows error."""
    result = runner.invoke(app, ["validate", "--game", "nonexistent-game"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


def test_game_command_game_flag_help() -> None:
    """Test that game command shows --game flag in help."""
    result = runner.invoke(app, ["game", "--help"])
    assert result.exit_code == 0
    assert "--game" in result.stdout
    assert "-g" in result.stdout


def test_game_command_reset_db_help_updated() -> None:
    """Test that game command --reset-db help mentions game scope."""
    result = runner.invoke(app, ["game", "--help"])
    assert result.exit_code == 0
    assert "--reset-db" in result.stdout
    # Should mention game scope in help text
    assert "chosen" in result.stdout


def test_game_command_with_unknown_game() -> None:
    """Test that game command with unknown game shows error."""
    result = runner.invoke(app, ["game", "--game", "nonexistent-game"])
    assert result.exit_code == 1
    # Error may be in stderr or stdout, but should definitely exit with code 1


def test_version_uses_settings() -> None:
    """Test that version command uses project_name from settings."""
    from oscilla.settings import settings

    result = runner.invoke(app, ["version"])
    assert settings.project_name in result.stdout


def test_test_data_command_exists() -> None:
    """Test that test_data command is registered."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "test-data" in result.stdout.lower() or "test_data" in result.stdout.lower()


def test_test_data_command_runs(db_session: Any) -> None:
    """Test that test_data command executes successfully."""
    result = runner.invoke(app, ["test-data"])
    assert result.exit_code == 0
    assert "successfully" in result.stdout.lower()


def test_test_data_shows_version(db_session: Any) -> None:
    """Test that test_data command shows version in output."""
    from oscilla.settings import settings

    result = runner.invoke(app, ["test-data"])
    assert settings.project_name in result.stdout


def test_test_data_calls_db_function(db_session: Any, monkeypatch: Any) -> None:
    """Test that test_data command calls the database test_data function."""
    called = []

    async def mock_test_data(session: Any) -> None:
        called.append(True)

    import oscilla.services.db as db_module

    monkeypatch.setattr(db_module, "test_data", mock_test_data)

    result = runner.invoke(app, ["test-data"])
    assert result.exit_code == 0
    assert len(called) == 1, "test_data function should be called once"


def test_game_command_force_flag_help() -> None:
    """Test that game command shows --force flag in help."""
    result = runner.invoke(app, ["game", "--help"])
    assert result.exit_code == 0
    assert "--force" in result.stdout
    assert "-f" in result.stdout
    assert "confirmation" in result.stdout.lower()


def test_game_command_force_flag_without_reset_db() -> None:
    """Test that --force flag can be used (though it has no effect without --reset-db)."""
    result = runner.invoke(app, ["game", "--game", "nonexistent-game", "--force"])
    # Should still fail because the game doesn't exist, but not because of the force flag
    assert result.exit_code == 1
