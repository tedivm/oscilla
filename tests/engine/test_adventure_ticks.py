"""Tests for tick advancement during adventure pipeline execution."""

from __future__ import annotations


from oscilla.engine.character import CharacterState
from oscilla.engine.models.adventure import (
    AdventureManifest,
    AdventureSpec,
    AdjustGameTicksEffect,
    EndAdventureEffect,
    NarrativeStep,
)
from oscilla.engine.models.base import Metadata
from oscilla.engine.pipeline import AdventurePipeline
from oscilla.engine.registry import ContentRegistry
from tests.engine.conftest import MockTUI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player(registry: ContentRegistry) -> CharacterState:
    assert registry.game is not None
    assert registry.character_config is not None
    return CharacterState.new_character(
        name="Tester",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )


def _simple_adventure(name: str = "test-tick-adventure") -> AdventureManifest:
    """Build a minimal one-step adventure that ends as 'completed'."""
    return AdventureManifest(
        apiVersion="oscilla/v1",
        kind="Adventure",
        metadata=Metadata(name=name),
        spec=AdventureSpec(
            displayName="Tick Adventure",
            steps=[
                NarrativeStep(
                    type="narrative",
                    text="You do something.",
                    effects=[EndAdventureEffect(type="end_adventure", outcome="completed")],
                )
            ],
        ),
    )


def _tick_adventure(ticks: int, name: str = "test-tick-adventure") -> AdventureManifest:
    """Build an adventure with a configured ticks cost."""
    return AdventureManifest(
        apiVersion="oscilla/v1",
        kind="Adventure",
        metadata=Metadata(name=name),
        spec=AdventureSpec(
            displayName="Tick Adventure",
            ticks=ticks,
            steps=[
                NarrativeStep(
                    type="narrative",
                    text="You do something.",
                    effects=[EndAdventureEffect(type="end_adventure", outcome="completed")],
                )
            ],
        ),
    )


def _adjust_ticks_adventure(delta: int, name: str = "test-adjust-adventure") -> AdventureManifest:
    """Build an adventure that adjusts game_ticks and ends."""
    return AdventureManifest(
        apiVersion="oscilla/v1",
        kind="Adventure",
        metadata=Metadata(name=name),
        spec=AdventureSpec(
            displayName="Adjust Ticks Adventure",
            steps=[
                NarrativeStep(
                    type="narrative",
                    text="Time shifts.",
                    effects=[
                        AdjustGameTicksEffect(type="adjust_game_ticks", delta=delta),
                        EndAdventureEffect(type="end_adventure", outcome="completed"),
                    ],
                )
            ],
        ),
    )


# ---------------------------------------------------------------------------
# Tick advancement via pipeline
# ---------------------------------------------------------------------------


async def test_internal_ticks_advance_on_completion(
    ingame_time_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    """internal_ticks increments by ticks_per_adventure (default=1) on adventure completion."""
    player = _make_player(ingame_time_registry)
    assert player.internal_ticks == 0

    pipeline = AdventurePipeline(
        registry=ingame_time_registry,
        player=player,
        tui=mock_tui,
    )
    await pipeline.run("test-narrative")
    # The fixture game has ticks_per_adventure=1
    assert player.internal_ticks == 1


async def test_game_ticks_advance_on_completion(
    ingame_time_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    """game_ticks increments by ticks_per_adventure (default=1) on adventure completion."""
    player = _make_player(ingame_time_registry)
    assert player.game_ticks == 0

    pipeline = AdventurePipeline(
        registry=ingame_time_registry,
        player=player,
        tui=mock_tui,
    )
    await pipeline.run("test-narrative")
    assert player.game_ticks == 1


async def test_both_clocks_advance_together(
    ingame_time_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    """Both clocks advance by the same tick cost per adventure by default."""
    player = _make_player(ingame_time_registry)

    pipeline = AdventurePipeline(
        registry=ingame_time_registry,
        player=player,
        tui=mock_tui,
    )
    await pipeline.run("test-narrative")
    assert player.internal_ticks == player.game_ticks


async def test_adventure_last_completed_at_ticks_is_recorded(
    ingame_time_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    """adventure_last_completed_at_ticks is updated with internal_ticks on completion."""
    player = _make_player(ingame_time_registry)

    pipeline = AdventurePipeline(
        registry=ingame_time_registry,
        player=player,
        tui=mock_tui,
    )
    await pipeline.run("test-narrative")
    assert "test-narrative" in player.adventure_last_completed_at_ticks
    assert player.adventure_last_completed_at_ticks["test-narrative"] == player.internal_ticks


# ---------------------------------------------------------------------------
# Per-adventure ticks cost
# ---------------------------------------------------------------------------


async def test_custom_ticks_cost_advances_by_spec_value(
    ingame_time_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    """Adventures with spec.ticks cost are used instead of ticks_per_adventure."""
    # Build a registry variant with a custom-tick adventure
    from oscilla.engine.models.location import AdventurePoolEntry, LocationManifest, LocationSpec

    adv = _tick_adventure(ticks=5, name="test-five-tick-adv")
    loc = LocationManifest(
        apiVersion="oscilla/v1",
        kind="Location",
        metadata=Metadata(name="test-location-extra"),
        spec=LocationSpec(
            displayName="Extra Location",
            region="test-region-root",
            adventures=[AdventurePoolEntry(ref="test-five-tick-adv", weight=1)],
        ),
    )
    from oscilla.engine.loader import load
    from pathlib import Path

    FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"
    base_registry, _ = load(FIXTURES / "ingame-time")
    # Inject the new adventure and location into the existing registry
    base_registry.adventures.register(adv)
    base_registry.locations.register(loc)

    player = _make_player(base_registry)
    pipeline = AdventurePipeline(registry=base_registry, player=player, tui=mock_tui)
    await pipeline.run("test-five-tick-adv")
    assert player.internal_ticks == 5
    assert player.game_ticks == 5


# ---------------------------------------------------------------------------
# adjust_game_ticks effect
# ---------------------------------------------------------------------------


async def test_adjust_game_ticks_positive_delta(
    ingame_time_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    """adjust_game_ticks with positive delta advances game_ticks beyond normal tick cost."""
    from oscilla.engine.models.location import AdventurePoolEntry, LocationManifest, LocationSpec
    from oscilla.engine.loader import load
    from pathlib import Path

    FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"
    registry, _ = load(FIXTURES / "ingame-time")

    adv = _adjust_ticks_adventure(delta=10, name="test-adjust-pos")
    loc = LocationManifest(
        apiVersion="oscilla/v1",
        kind="Location",
        metadata=Metadata(name="test-loc-adjust-pos"),
        spec=LocationSpec(
            displayName="Adjust Loc",
            region="test-region-root",
            adventures=[AdventurePoolEntry(ref="test-adjust-pos", weight=1)],
        ),
    )
    registry.adventures.register(adv)
    registry.locations.register(loc)

    player = _make_player(registry)
    pipeline = AdventurePipeline(registry=registry, player=player, tui=mock_tui)
    await pipeline.run("test-adjust-pos")
    # Pipeline advances game_ticks by ticks_per_adventure (1), then effect adds 10
    assert player.game_ticks == 11
    # internal_ticks is NOT affected by adjust_game_ticks
    assert player.internal_ticks == 1


async def test_adjust_game_ticks_negative_delta_clamp(
    ingame_time_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    """adjust_game_ticks clamps to 0 when pre_epoch_behavior=clamp and delta pushes below 0."""
    from oscilla.engine.models.location import AdventurePoolEntry, LocationManifest, LocationSpec
    from oscilla.engine.loader import load
    from pathlib import Path

    FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"
    registry, _ = load(FIXTURES / "ingame-time")

    # delta=-100 on tick 0 — net game_ticks would go negative; clamp kicks in
    adv = _adjust_ticks_adventure(delta=-100, name="test-adjust-neg")
    loc = LocationManifest(
        apiVersion="oscilla/v1",
        kind="Location",
        metadata=Metadata(name="test-loc-adjust-neg"),
        spec=LocationSpec(
            displayName="Adjust Neg Loc",
            region="test-region-root",
            adventures=[AdventurePoolEntry(ref="test-adjust-neg", weight=1)],
        ),
    )
    registry.adventures.register(adv)
    registry.locations.register(loc)

    player = _make_player(registry)
    pipeline = AdventurePipeline(registry=registry, player=player, tui=mock_tui)
    await pipeline.run("test-adjust-neg")
    # The effect fires during steps (game_ticks=0 → clamped to 0).
    # Then the pipeline tick advance adds tick_cost=1 on completion.
    # Final: game_ticks = max(0, 0 + (-100)) + 1 = 0 + 1 = 1.
    assert player.game_ticks == 1
    # internal_ticks is unaffected by adjust_game_ticks
    assert player.internal_ticks == 1


async def test_adjust_game_ticks_does_not_affect_internal_ticks(
    ingame_time_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    """adjust_game_ticks never changes internal_ticks."""
    from oscilla.engine.models.location import AdventurePoolEntry, LocationManifest, LocationSpec
    from oscilla.engine.loader import load
    from pathlib import Path

    FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"
    registry, _ = load(FIXTURES / "ingame-time")

    adv = _adjust_ticks_adventure(delta=50, name="test-adjust-internal")
    loc = LocationManifest(
        apiVersion="oscilla/v1",
        kind="Location",
        metadata=Metadata(name="test-loc-adjust-internal"),
        spec=LocationSpec(
            displayName="Adjust Internal Loc",
            region="test-region-root",
            adventures=[AdventurePoolEntry(ref="test-adjust-internal", weight=1)],
        ),
    )
    registry.adventures.register(adv)
    registry.locations.register(loc)

    player = _make_player(registry)
    pipeline = AdventurePipeline(registry=registry, player=player, tui=mock_tui)
    await pipeline.run("test-adjust-internal")
    assert player.internal_ticks == 1  # Only the tick_cost advances internal_ticks
    assert player.game_ticks == 51  # tick_cost (1) + adjust (50)


# ---------------------------------------------------------------------------
# Tick-based cooldowns
# ---------------------------------------------------------------------------


def test_cooldown_ticks_eligible_before_elapsed(ingame_time_registry: ContentRegistry) -> None:
    """Adventure with cooldown_ticks is ineligible once played until enough ticks pass."""
    from oscilla.engine.models.adventure import AdventureSpec
    import datetime

    player = _make_player(ingame_time_registry)
    player.internal_ticks = 5
    player.adventure_last_completed_at_ticks["cave"] = 3

    spec = AdventureSpec.model_validate(
        {
            "displayName": "Cave",
            "cooldown_ticks": 5,
            "steps": [
                {"type": "narrative", "text": ".", "effects": [{"type": "end_adventure", "outcome": "completed"}]}
            ],
        }
    )
    # Only 2 ticks elapsed (5 - 3), cooldown_ticks=5 → not eligible
    assert player.is_adventure_eligible("cave", spec, datetime.date.today()) is False


def test_cooldown_ticks_eligible_after_elapsed(ingame_time_registry: ContentRegistry) -> None:
    """Adventure becomes eligible once cooldown_ticks have elapsed."""
    from oscilla.engine.models.adventure import AdventureSpec
    import datetime

    player = _make_player(ingame_time_registry)
    player.internal_ticks = 10
    player.adventure_last_completed_at_ticks["cave"] = 3

    spec = AdventureSpec.model_validate(
        {
            "displayName": "Cave",
            "cooldown_ticks": 5,
            "steps": [
                {"type": "narrative", "text": ".", "effects": [{"type": "end_adventure", "outcome": "completed"}]}
            ],
        }
    )
    # 7 ticks elapsed (10 - 3), cooldown_ticks=5 → eligible
    assert player.is_adventure_eligible("cave", spec, datetime.date.today()) is True
