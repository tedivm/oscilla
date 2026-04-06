"""Tests for _validate_trigger_adventures loader validation."""

from __future__ import annotations

from typing import Dict, List

from oscilla.engine.loader import _validate_trigger_adventures
from oscilla.engine.models.adventure import AdventureManifest, AdventureSpec, NarrativeStep
from oscilla.engine.models.base import Metadata
from oscilla.engine.models.game import (
    GameManifest,
    GameSpec,
    GameTriggers,
    HpFormula,
    StatThresholdTrigger,
)
from oscilla.engine.registry import ContentRegistry


def _make_game_manifest(
    trigger_adventures: Dict[str, List[str]] | None = None,
    custom_triggers: List[str] | None = None,
    on_stat_threshold: List[StatThresholdTrigger] | None = None,
    outcomes: List[str] | None = None,
) -> GameManifest:
    """Build a minimal GameManifest for validation tests."""
    return GameManifest(
        apiVersion="game/v1",
        kind="Game",
        metadata=Metadata(name="test-game"),
        spec=GameSpec(
            displayName="Test Game",
            xp_thresholds=[100, 300, 600],
            hp_formula=HpFormula(base_hp=20, hp_per_level=5),
            outcomes=outcomes or [],
            triggers=GameTriggers(
                custom=custom_triggers or [],
                on_stat_threshold=on_stat_threshold or [],
            ),
            trigger_adventures=trigger_adventures or {},
        ),
    )


def _make_adventure_manifest(name: str) -> AdventureManifest:
    """Build a minimal one-step AdventureManifest."""
    return AdventureManifest(
        apiVersion="game/v1",
        kind="Adventure",
        metadata=Metadata(name=name),
        spec=AdventureSpec(
            displayName=name,
            steps=[NarrativeStep(type="narrative", text="Test step")],
        ),
    )


def _build_registry(
    game: GameManifest,
    adventures: List[AdventureManifest] | None = None,
) -> ContentRegistry:
    """Build a ContentRegistry with the given game manifest and optional adventures."""
    registry = ContentRegistry()
    registry.game = game
    for adv in adventures or []:
        registry.adventures.register(adv)
    return registry


# ---------------------------------------------------------------------------
# Unknown trigger key (task 7.5)
# ---------------------------------------------------------------------------


def test_unknown_trigger_key_is_load_warning() -> None:
    """A trigger_adventures key that is not a valid trigger name produces a load warning."""
    adv = _make_adventure_manifest("some-adv")
    game = _make_game_manifest(trigger_adventures={"on_mistyped_event": ["some-adv"]})
    registry = _build_registry(game, adventures=[adv])

    warnings = _validate_trigger_adventures(registry)

    assert any("on_mistyped_event" in str(w) for w in warnings)


# ---------------------------------------------------------------------------
# Unknown adventure ref (task 7.5)
# ---------------------------------------------------------------------------


def test_unknown_adventure_ref_is_load_warning() -> None:
    """A trigger_adventures value referencing a non-existent adventure produces a warning."""
    game = _make_game_manifest(trigger_adventures={"on_level_up": ["no-such-adv"]})
    # Register no adventures — the ref will not resolve.
    registry = _build_registry(game)

    warnings = _validate_trigger_adventures(registry)

    assert any("no-such-adv" in str(w) for w in warnings)


# ---------------------------------------------------------------------------
# Valid on_outcome_<custom> (task 7.5)
# ---------------------------------------------------------------------------


def test_on_outcome_custom_valid_when_declared() -> None:
    """on_outcome_<custom> produces no warning when the outcome is declared in game.yaml."""
    adv = _make_adventure_manifest("discovery-adv")
    game = _make_game_manifest(
        outcomes=["discovered"],
        trigger_adventures={"on_outcome_discovered": ["discovery-adv"]},
    )
    registry = _build_registry(game, adventures=[adv])

    warnings = _validate_trigger_adventures(registry)

    assert warnings == []


# ---------------------------------------------------------------------------
# Invalid on_outcome_<custom> (task 7.5)
# ---------------------------------------------------------------------------


def test_on_outcome_unknown_is_load_warning() -> None:
    """on_outcome_<name> for an undeclared outcome produces a load warning."""
    adv = _make_adventure_manifest("disc-adv")
    # No outcomes declared in game.yaml spec; "discovered" is not built-in.
    game = _make_game_manifest(trigger_adventures={"on_outcome_discovered": ["disc-adv"]})
    registry = _build_registry(game, adventures=[adv])

    warnings = _validate_trigger_adventures(registry)

    assert any("on_outcome_discovered" in str(w) for w in warnings)


# ---------------------------------------------------------------------------
# Duplicate threshold name (task 7.6)
# ---------------------------------------------------------------------------


def test_duplicate_threshold_name_is_load_warning() -> None:
    """Two on_stat_threshold entries with the same name produce a load warning."""
    thresholds = [
        StatThresholdTrigger(stat="gold", threshold=50, name="gold-milestone"),
        StatThresholdTrigger(stat="gold", threshold=100, name="gold-milestone"),  # duplicate
    ]
    game = _make_game_manifest(on_stat_threshold=thresholds)
    registry = _build_registry(game)

    warnings = _validate_trigger_adventures(registry)

    assert any("gold-milestone" in str(w) for w in warnings)


# ---------------------------------------------------------------------------
# emit_trigger with undeclared custom name (task 7.7)
# ---------------------------------------------------------------------------


def test_emit_trigger_undeclared_custom_name_is_load_warning() -> None:
    """An emit_trigger effect whose trigger name is not in triggers.custom is a load warning."""
    from oscilla.engine.models.adventure import EmitTriggerEffect

    # Build an adventure that emits an undeclared custom trigger.
    from oscilla.engine.models.adventure import AdventureSpec, NarrativeStep

    adv = AdventureManifest(
        apiVersion="game/v1",
        kind="Adventure",
        metadata=Metadata(name="emitting-adv"),
        spec=AdventureSpec(
            displayName="Emitting Adventure",
            steps=[
                NarrativeStep(
                    type="narrative",
                    text="You act.",
                    effects=[EmitTriggerEffect(type="emit_trigger", trigger="undeclared-event")],
                )
            ],
        ),
    )
    # No custom triggers declared.
    game = _make_game_manifest()
    registry = _build_registry(game, adventures=[adv])

    warnings = _validate_trigger_adventures(registry)

    assert any("undeclared-event" in str(w) for w in warnings)
