"""Tests for the set_location effect."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.models.adventure import SetLocationEffect
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.steps.effects import run_effect


def _make_player(current_location: str | None = None) -> CharacterState:
    return CharacterState(
        character_id=uuid4(),
        name="Tester",
        character_class=None,
        prestige_count=0,
        current_location=current_location,
        stats={},
    )


def _make_registry_with_location(location_ref: str) -> ContentRegistry:
    from oscilla.engine.models.location import LocationManifest

    registry = ContentRegistry()
    registry.locations.register(
        LocationManifest.model_validate(
            {
                "apiVersion": "oscilla/v1",
                "kind": "Location",
                "metadata": {"name": location_ref},
                "spec": {"displayName": "Test Location", "description": "", "region": "test-region"},
            }
        )
    )
    return registry


@pytest.mark.asyncio
async def test_set_location_moves_player() -> None:
    """set_location sets current_location to the given ref."""
    player = _make_player()
    registry = _make_registry_with_location("starting-area")
    tui = AsyncMock()

    effect = SetLocationEffect(type="set_location", location="starting-area")
    await run_effect(effect=effect, player=player, registry=registry, tui=tui)

    assert player.current_location == "starting-area"


@pytest.mark.asyncio
async def test_set_location_clears_location_when_null() -> None:
    """set_location with location=null clears current_location."""
    player = _make_player(current_location="old-area")
    registry = ContentRegistry()
    tui = AsyncMock()

    effect = SetLocationEffect(type="set_location", location=None)
    await run_effect(effect=effect, player=player, registry=registry, tui=tui)

    assert player.current_location is None


@pytest.mark.asyncio
async def test_set_location_unknown_ref_is_noop(caplog: pytest.LogCaptureFixture) -> None:
    """set_location with an unknown ref logs a warning and leaves current_location unchanged."""
    player = _make_player(current_location="existing-area")
    registry = ContentRegistry()
    tui = AsyncMock()

    effect = SetLocationEffect(type="set_location", location="no-such-place")
    with caplog.at_level("WARNING"):
        await run_effect(effect=effect, player=player, registry=registry, tui=tui)

    assert player.current_location == "existing-area"
    assert "no-such-place" in caplog.text
