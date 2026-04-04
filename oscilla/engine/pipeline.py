"""Adventure pipeline — executes an ordered list of adventure steps.

The pipeline is the only engine component that calls TUICallbacks — it
orchestrates navigation between steps and delegates to per-type handler
functions in oscilla/engine/steps/.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Protocol

from oscilla.engine.character import AdventurePosition, CharacterState
from oscilla.engine.models.adventure import Effect, OutcomeBranch, Step
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.signals import _EndSignal, _GotoSignal
from oscilla.engine.templates import ExpressionContext, PlayerContext

if TYPE_CHECKING:
    from oscilla.engine.templates import CombatContextView


class TUICallbacks(Protocol):
    """Interface that step handlers use to produce player-facing output.

    The concrete implementation is TextualTUI (oscilla/engine/tui.py).
    Tests inject MockTUI (tests/engine/conftest.py).
    Step handlers never import TextualTUI directly — they receive TUICallbacks.
    """

    async def show_text(self, text: str) -> None:
        """Display a narrative passage or informational message."""
        ...

    async def show_menu(self, prompt: str, options: List[str]) -> int:
        """Display a list of options and return the 1-based index chosen.

        Suspends the caller until the player makes a selection.
        """
        ...

    async def show_combat_round(
        self,
        player_hp: int,
        enemy_hp: int,
        player_name: str,
        enemy_name: str,
    ) -> None:
        """Display combat state before each player action in the turn loop."""
        ...

    async def wait_for_ack(self) -> None:
        """Pause for the player to acknowledge before advancing to the next step."""
        ...

    async def input_text(self, prompt: str) -> str:
        """Display a prompt and wait for the player to type and submit a string.

        The concrete implementation determines how input is collected
        (e.g. a Textual Input widget in the TUI, a readline prompt in tests).
        Must return a non-empty string.
        """
        ...

    async def show_skill_menu(self, skills: List[Dict[str, Any]]) -> int | None:
        """Display a list of skills (overworld/out-of-combat) and return a 1-based index.

        Each dict must contain at least ``"name"`` and ``"description"`` keys.
        Returns ``None`` if the player cancels without selecting a skill.
        """
        ...


class PersistCallback(Protocol):
    """Called by AdventurePipeline at key checkpoints to persist character state.

    event values:
      "step_start"    — fired before each step is dispatched.
      "combat_round"  — fired after each combat round resolves.
      "adventure_end" — fired after all outcome effects are applied and
                        active_adventure is set to None, before run() returns.
    """

    async def __call__(
        self,
        state: CharacterState,
        event: Literal["step_start", "combat_round", "adventure_end"],
    ) -> None: ...


class AdventureOutcome(str, Enum):
    COMPLETED = "completed"
    DEFEATED = "defeated"
    FLED = "fled"


class AdventurePipeline:
    """Executes a single adventure from start to finish.

    A new instance should be created per adventure run — the pipeline is
    stateless between runs because active_adventure is cleared on the
    player at the end of every run() call.

    The ConditionEvaluator is used internally by step handlers (via the
    evaluate import) and is not exposed in this class's public interface.
    """

    def __init__(
        self,
        registry: ContentRegistry,
        player: CharacterState,
        tui: TUICallbacks,
        on_state_change: PersistCallback | None = None,
    ) -> None:
        self._registry = registry
        self._player = player
        self._tui = tui
        self._on_state_change = on_state_change
        self._root_steps: List[Step] = []
        self._label_index: Dict[str, int] = {}

    async def _checkpoint(self, event: Literal["step_start", "combat_round", "adventure_end"]) -> None:
        """Fire the persist callback if one is registered."""
        if self._on_state_change is not None:
            await self._on_state_change(self._player, event)

    def _build_context(self, combat_view: "CombatContextView | None" = None) -> ExpressionContext:
        """Build a read-only render context from current player state."""
        return ExpressionContext(
            player=PlayerContext.from_character(self._player),
            combat=combat_view,
        )

    async def run(self, adventure_ref: str) -> AdventureOutcome:
        """Execute the adventure from step 0.

        Handles _GotoSignal by restarting _run_from() at the target step.
        Handles _EndSignal by returning the requested outcome immediately.
        Clears active_adventure on the player when done.

        Increments adventures_completed statistics only on COMPLETED outcome.
        """
        from oscilla.engine.steps.effects import run_effect

        adventure = self._registry.adventures.require(adventure_ref, "Adventure")
        self._root_steps = list(adventure.spec.steps)
        # Build label → index map for O(1) goto resolution
        self._label_index = {
            step.label: i
            for i, step in enumerate(self._root_steps)
            if hasattr(step, "label") and step.label is not None
        }
        self._player.active_adventure = AdventurePosition(
            adventure_ref=adventure_ref,
            step_index=0,
        )
        # Store run_effect locally so _run_effects doesn't re-import each call
        self._run_effect = run_effect

        start = 0
        outcome: AdventureOutcome = AdventureOutcome.COMPLETED
        while True:
            try:
                outcome = await self._run_from(start)
                break
            except _GotoSignal as sig:
                # Jump to the labeled top-level step
                start = self._label_index[sig.label]
            except _EndSignal as sig:
                outcome = AdventureOutcome(sig.outcome)
                break

        self._player.active_adventure = None
        if outcome == AdventureOutcome.COMPLETED:
            self._player.statistics.record_adventure_completed(adventure_ref)
        await self._checkpoint("adventure_end")
        return outcome

    # --- Internal step execution ---

    async def _run_from(self, start_index: int) -> AdventureOutcome:
        """Run root steps from start_index through the end of the list."""
        for i in range(start_index, len(self._root_steps)):
            step = self._root_steps[i]
            if self._player.active_adventure:
                self._player.active_adventure.step_index = i
            await self._checkpoint("step_start")
            outcome = await self._dispatch(step)
            if outcome != AdventureOutcome.COMPLETED:
                return outcome
        return AdventureOutcome.COMPLETED

    async def _run_steps(self, steps: List[Step]) -> AdventureOutcome:
        """Run a nested step list (outcome branch or choice option inline steps).

        _GotoSignal propagates naturally up to run() if raised inside a sub-step.
        """
        for step in steps:
            outcome = await self._dispatch(step)
            if outcome != AdventureOutcome.COMPLETED:
                return outcome
        return AdventureOutcome.COMPLETED

    async def _dispatch(self, step: Step) -> AdventureOutcome:
        """Dispatch a step to its type-specific handler function."""
        from oscilla.engine.models.adventure import ChoiceStep, CombatStep, NarrativeStep, PassiveStep, StatCheckStep
        from oscilla.engine.steps.choice import run_choice
        from oscilla.engine.steps.combat import run_combat
        from oscilla.engine.steps.narrative import run_narrative
        from oscilla.engine.steps.passive import run_passive
        from oscilla.engine.steps.stat_check import run_stat_check

        match step:
            case NarrativeStep():
                return await run_narrative(
                    step=step,
                    player=self._player,
                    tui=self._tui,
                    run_effects=self._run_effects,
                    registry=self._registry,
                    ctx=self._build_context(),
                )
            case CombatStep():
                return await run_combat(
                    step=step,
                    player=self._player,
                    registry=self._registry,
                    tui=self._tui,
                    run_outcome_branch=self._run_outcome_branch,
                    on_round_complete=lambda: self._checkpoint("combat_round"),
                )
            case ChoiceStep():
                return await run_choice(
                    step=step,
                    player=self._player,
                    tui=self._tui,
                    run_outcome_branch=self._run_outcome_branch,
                    registry=self._registry,
                )
            case StatCheckStep():
                return await run_stat_check(
                    step=step,
                    player=self._player,
                    run_outcome_branch=self._run_outcome_branch,
                    registry=self._registry,
                )
            case PassiveStep():
                return await run_passive(
                    step=step,
                    player=self._player,
                    registry=self._registry,
                    tui=self._tui,
                )
        # Unreachable with a complete match; guards against future extension.
        raise ValueError(f"Unhandled step type: {step!r}")  # pragma: no cover

    async def _run_effects(self, effects: List[Effect], ctx: ExpressionContext | None = None) -> None:
        """Apply effects and report each outcome to the player via TUI."""
        resolved_ctx = ctx or self._build_context()
        for effect in effects:
            await self._run_effect(effect, self._player, self._registry, self._tui, ctx=resolved_ctx)

    async def _run_outcome_branch(self, branch: OutcomeBranch) -> AdventureOutcome:
        """Fire branch effects, then either run inline steps or raise a goto signal."""
        await self._run_effects(branch.effects)
        if branch.goto is not None:
            raise _GotoSignal(branch.goto)  # caught by run(); never escapes the pipeline
        return await self._run_steps(list(branch.steps))
