"""Integration tests for the ``oscilla content`` CLI subapp."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from oscilla.cli import app

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
