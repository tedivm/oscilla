"""Integration tests for the ``oscilla content`` CLI subapp."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from oscilla.cli import app
from oscilla.engine.loader import load_from_disk

# TERM=dumb prevents Rich from injecting ANSI escape codes into captured output.
runner = CliRunner(env={"TERM": "dumb"})


def test_content_help_shows_subcommands() -> None:
    result = runner.invoke(app, ["content", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "show" in result.stdout
    assert "graph" in result.stdout


def test_content_list_adventures() -> None:
    result = runner.invoke(app, ["content", "list", "adventures", "--game", "testlandia"])
    assert result.exit_code == 0


def test_content_list_regions() -> None:
    result = runner.invoke(app, ["content", "list", "regions", "--game", "testlandia"])
    assert result.exit_code == 0


def test_content_list_locations() -> None:
    result = runner.invoke(app, ["content", "list", "locations", "--game", "testlandia"])
    assert result.exit_code == 0


def test_content_list_json_output_is_parseable() -> None:
    result = runner.invoke(
        app,
        ["content", "list", "adventures", "--game", "testlandia", "--format", "json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)


def test_content_list_json_rows_have_name_field() -> None:
    result = runner.invoke(
        app,
        ["content", "list", "adventures", "--game", "testlandia", "--format", "json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    if data:
        assert "name" in data[0]


def test_content_list_enemies() -> None:
    result = runner.invoke(app, ["content", "list", "enemies", "--game", "testlandia"])
    assert result.exit_code == 0


def test_content_list_unknown_kind_exits_nonzero() -> None:
    result = runner.invoke(app, ["content", "list", "wombats", "--game", "testlandia"])
    assert result.exit_code != 0


def test_content_schema_shows_schema() -> None:
    result = runner.invoke(app, ["content", "schema", "adventure"])
    assert result.exit_code == 0
    assert "adventure" in result.stdout.lower() or "$schema" in result.stdout


def test_content_schema_json_output_is_valid() -> None:
    result = runner.invoke(app, ["content", "schema", "adventure"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, dict)


def test_content_schema_unknown_kind_exits_nonzero() -> None:
    result = runner.invoke(app, ["content", "schema", "not-a-kind"])
    assert result.exit_code != 0


def test_content_trace_adventure() -> None:
    """Run trace on an adventure from testlandia."""
    # First, find an adventure name using list
    result = runner.invoke(
        app,
        ["content", "list", "adventures", "--game", "testlandia", "--format", "json"],
    )
    assert result.exit_code == 0
    adventures = json.loads(result.stdout)
    if not adventures:
        pytest.skip("No adventures found in testlandia")

    adv_name = adventures[0]["name"]
    trace_result = runner.invoke(
        app,
        ["content", "trace", adv_name, "--game", "testlandia"],
    )
    assert trace_result.exit_code == 0


def test_content_graph_world() -> None:
    result = runner.invoke(
        app,
        ["content", "graph", "world", "--game", "testlandia", "--format", "ascii"],
    )
    assert result.exit_code == 0


def test_content_graph_unknown_type_exits_nonzero() -> None:
    result = runner.invoke(
        app,
        ["content", "graph", "unknown-graph-type", "--game", "testlandia"],
    )
    assert result.exit_code != 0


def test_content_test_validates_game() -> None:
    """The test command should run validation on testlandia."""
    result = runner.invoke(app, ["content", "test", "--game", "testlandia"])
    # A valid content package should exit 0
    assert result.exit_code == 0


_TESTLANDIA_PATH = Path(__file__).parent.parent / "content" / "testlandia"


def test_testlandia_character_creation_adventure_is_in_registry() -> None:
    """The character-creation adventure must be present in the loaded testlandia registry."""
    registry, _warnings = load_from_disk(_TESTLANDIA_PATH)
    assert "character-creation" in registry.adventures


def test_testlandia_character_creation_adventure_has_at_least_three_steps() -> None:
    """The testlandia character-creation adventure must have at least 3 steps."""
    registry, _warnings = load_from_disk(_TESTLANDIA_PATH)
    adventure = registry.adventures.require("character-creation", "Adventure")
    assert len(adventure.spec.steps) >= 3


# ---------------------------------------------------------------------------
# content schema --vscode tests
# ---------------------------------------------------------------------------


def test_schema_vscode_default_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--vscode with no --output writes to .vscode/oscilla-schemas/ by default."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["content", "schema", "--vscode"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".vscode" / "oscilla-schemas" / "manifest.json").exists()
    assert (tmp_path / ".vscode" / "oscilla-schemas" / "adventure.json").exists()


def test_schema_vscode_updates_settings_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--vscode writes a content glob association pointing at manifest.json into settings.json."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["content", "schema", "--vscode"])
    settings_path = tmp_path / ".vscode" / "settings.json"
    assert settings_path.exists()
    settings = json.loads(settings_path.read_text())
    assert "yaml.schemas" in settings
    # The value for the manifest.json key should be the **/*.yaml glob.
    manifest_entries = {k: v for k, v in settings["yaml.schemas"].items() if "manifest.json" in k}
    assert manifest_entries, "No manifest.json entry found in yaml.schemas"
    assert "**/*.yaml" in manifest_entries.values()


def test_schema_vscode_preserves_existing_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing settings.json content is preserved when --vscode updates the file."""
    monkeypatch.chdir(tmp_path)
    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    (vscode_dir / "settings.json").write_text(json.dumps({"peacock.color": "#ff0000"}))
    runner.invoke(app, ["content", "schema", "--vscode"])
    settings = json.loads((vscode_dir / "settings.json").read_text())
    assert "peacock.color" in settings
    assert settings["peacock.color"] == "#ff0000"
    assert "yaml.schemas" in settings


# ---------------------------------------------------------------------------
# content test: alias tests (4.11 – 4.12)
# ---------------------------------------------------------------------------


def test_content_test_still_works_as_alias() -> None:
    """content test on testlandia should still exit 0 after it became a thin wrapper."""
    result = runner.invoke(app, ["content", "test", "--game", "testlandia"])
    assert result.exit_code == 0


def test_content_test_json_format() -> None:
    """content test --format json returns valid JSON with errors/warnings/summary."""
    result = runner.invoke(
        app,
        ["content", "test", "--game", "testlandia", "--format", "json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "errors" in data
    assert "warnings" in data
    assert "summary" in data
