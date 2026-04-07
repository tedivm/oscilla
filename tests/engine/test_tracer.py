"""Tests for tracer.py — headless adventure path tracer."""

from __future__ import annotations

from oscilla.engine.models.adventure import (
    AdventureManifest,
    AdventureSpec,
    ChoiceOption,
    ChoiceStep,
    CombatStep,
    EndAdventureEffect,
    NarrativeStep,
    OutcomeBranch,
)
from oscilla.engine.models.base import Metadata
from oscilla.engine.tracer import trace_adventure


def _two_option_adventure() -> AdventureManifest:
    """Adventure with one ChoiceStep offering two options, each ending the adventure."""
    return AdventureManifest(
        apiVersion="oscilla/v1",
        kind="Adventure",
        metadata=Metadata(name="two-roads"),
        spec=AdventureSpec(
            displayName="Two Roads",
            steps=[
                NarrativeStep(type="narrative", text="You arrive at a fork in the road."),
                ChoiceStep(
                    type="choice",
                    prompt="Which path do you take?",
                    options=[
                        ChoiceOption(
                            label="Left Path",
                            steps=[
                                NarrativeStep(
                                    type="narrative",
                                    text="Left path taken.",
                                    effects=[EndAdventureEffect(type="end_adventure", outcome="completed")],
                                )
                            ],
                        ),
                        ChoiceOption(
                            label="Right Path",
                            steps=[
                                NarrativeStep(
                                    type="narrative",
                                    text="Right path taken.",
                                    effects=[EndAdventureEffect(type="end_adventure", outcome="fled")],
                                )
                            ],
                        ),
                    ],
                ),
            ],
        ),
    )


def _linear_adventure() -> AdventureManifest:
    """Adventure with a single narrative then end."""
    return AdventureManifest(
        apiVersion="oscilla/v1",
        kind="Adventure",
        metadata=Metadata(name="simple-quest"),
        spec=AdventureSpec(
            displayName="Simple Quest",
            steps=[
                NarrativeStep(
                    type="narrative",
                    text="Done!",
                    effects=[EndAdventureEffect(type="end_adventure", outcome="completed")],
                ),
            ],
        ),
    )


def _combat_adventure() -> AdventureManifest:
    """Adventure with a CombatStep — should fork into 3 branches."""
    return AdventureManifest(
        apiVersion="oscilla/v1",
        kind="Adventure",
        metadata=Metadata(name="combat-quest"),
        spec=AdventureSpec(
            displayName="Combat Quest",
            steps=[
                CombatStep(
                    type="combat",
                    enemy="goblin",
                    on_win=OutcomeBranch(
                        steps=[
                            NarrativeStep(
                                type="narrative",
                                text="You win!",
                                effects=[EndAdventureEffect(type="end_adventure", outcome="completed")],
                            )
                        ]
                    ),
                    on_defeat=OutcomeBranch(
                        steps=[
                            NarrativeStep(
                                type="narrative",
                                text="You lose.",
                                effects=[EndAdventureEffect(type="end_adventure", outcome="defeated")],
                            )
                        ]
                    ),
                    on_flee=OutcomeBranch(
                        steps=[
                            NarrativeStep(
                                type="narrative",
                                text="You flee.",
                                effects=[EndAdventureEffect(type="end_adventure", outcome="fled")],
                            )
                        ]
                    ),
                )
            ],
        ),
    )


def test_trace_finds_two_paths_for_two_choice_options() -> None:
    result = trace_adventure(_two_option_adventure())
    assert len(result.paths) == 2


def test_trace_sets_adventure_name() -> None:
    result = trace_adventure(_two_option_adventure())
    assert result.adventure_name == "two-roads"


def test_trace_captures_both_outcomes() -> None:
    result = trace_adventure(_two_option_adventure())
    outcomes = result.all_path_outcomes
    assert "completed" in outcomes
    assert "fled" in outcomes


def test_trace_linear_adventure_has_one_path() -> None:
    result = trace_adventure(_linear_adventure())
    assert len(result.paths) == 1


def test_trace_linear_adventure_outcome_is_completed() -> None:
    result = trace_adventure(_linear_adventure())
    assert result.paths[0].outcome == "completed"


def test_trace_combat_produces_three_paths() -> None:
    result = trace_adventure(_combat_adventure())
    assert len(result.paths) == 3


def test_trace_combat_covers_all_outcomes() -> None:
    result = trace_adventure(_combat_adventure())
    outcomes = result.all_path_outcomes
    assert "completed" in outcomes
    assert "defeated" in outcomes
    assert "fled" in outcomes


def test_trace_no_character_state_mutation() -> None:
    """Tracing the same adventure twice always produces identical results."""
    manifest = _two_option_adventure()
    result_a = trace_adventure(manifest)
    result_b = trace_adventure(manifest)
    assert result_a.adventure_name == result_b.adventure_name
    assert len(result_a.paths) == len(result_b.paths)


def test_trace_result_step_kinds_covered_includes_choice() -> None:
    result = trace_adventure(_two_option_adventure())
    assert "choice" in result.step_kinds_covered


def test_trace_result_step_kinds_covered_includes_narrative() -> None:
    result = trace_adventure(_two_option_adventure())
    assert "narrative" in result.step_kinds_covered


def test_traced_path_has_nodes() -> None:
    result = trace_adventure(_linear_adventure())
    assert len(result.paths[0].nodes) > 0


def test_traced_node_has_step_type() -> None:
    result = trace_adventure(_linear_adventure())
    node = result.paths[0].nodes[0]
    assert node.step_type == "narrative"


def test_trace_total_steps_count() -> None:
    result = trace_adventure(_linear_adventure())
    # 1 NarrativeStep in _linear_adventure
    assert result.total_steps == 1
