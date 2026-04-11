"""Trigger test fixture helpers.

Provides ``build_trigger_test_registry``, a factory that loads the minimal
trigger_tests content package and overrides the game's trigger configuration
with caller-supplied values. This lets each integration test wire up exactly
the trigger_adventures it needs without forking separate YAML packages.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from oscilla.engine.loader import _build_stat_threshold_index, _build_trigger_index, load_from_disk
from oscilla.engine.models.game import GameRejoinTrigger, StatThresholdTrigger
from oscilla.engine.registry import ContentRegistry

_FIXTURE_DIR = Path(__file__).parent


def build_trigger_test_registry(
    trigger_adventures: Dict[str, List[str]] | None = None,
    custom_triggers: List[str] | None = None,
    on_stat_threshold: List[StatThresholdTrigger] | None = None,
    on_game_rejoin: GameRejoinTrigger | None = None,
) -> ContentRegistry:
    """Load the trigger_tests content package and override trigger configuration.

    All parameters are optional. When omitted the base game.yaml values are used.
    After overriding, the ``trigger_index`` and ``stat_threshold_index`` are
    rebuilt so the returned registry is consistent and usable in a GameSession.

    Args:
        trigger_adventures: Mapping from trigger name to ordered adventure ref list.
        custom_triggers: Replaces ``triggers.custom`` in the game spec.
        on_stat_threshold: Replaces ``triggers.on_stat_threshold`` in the game spec.
        on_game_rejoin: Sets ``triggers.on_game_rejoin`` in the game spec.

    Returns:
        A fully-initialized ContentRegistry ready for use in integration tests.
    """
    registry, _warnings = load_from_disk(_FIXTURE_DIR)

    if registry.game is None:
        raise RuntimeError("trigger_tests fixture is missing a Game manifest")

    spec = registry.game.spec

    if trigger_adventures is not None:
        spec.trigger_adventures = trigger_adventures
    if custom_triggers is not None:
        spec.triggers.custom = custom_triggers
    if on_stat_threshold is not None:
        spec.triggers.on_stat_threshold = on_stat_threshold
    if on_game_rejoin is not None:
        spec.triggers.on_game_rejoin = on_game_rejoin

    # Rebuild runtime indexes to reflect the overridden spec.
    registry.trigger_index = _build_trigger_index(registry.game)
    registry.stat_threshold_index = _build_stat_threshold_index(registry.game)

    return registry
