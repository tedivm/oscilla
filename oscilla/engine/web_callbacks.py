"""WebCallbacks — UICallbacks implementation for the web execution path.

Emits SSE events via an asyncio.Queue and accumulates session output records
for crash recovery. The pipeline runs until it reaches a decision point
(show_menu, wait_for_ack, input_text, show_skill_menu), at which point
DecisionPauseException is raised to unwind the coroutine call stack cleanly.

On an advance request the pipeline is reconstructed from adventure_step_index
and the pre-loaded player decision is passed via the optional resume parameters.
When a resume parameter is set the corresponding callback method returns
immediately without queuing an event or raising DecisionPauseException.
"""

from __future__ import annotations

from asyncio import Queue, sleep
from typing import Any, Dict, List

from oscilla.engine.pipeline import UICallbacks  # noqa: F401 — satisfies Protocol


class DecisionPauseException(Exception):
    """Raised by WebCallbacks to unwind the pipeline at a decision point.

    This is not an error — it is the normal shutdown mechanism for a web
    session after narrative output has been streamed and the next player
    decision has been emitted as an SSE event.
    """

    pass


class WebCallbacks:
    """UICallbacks implementation for the web execution path.

    Emits SSE events via an asyncio Queue and accumulates session output
    records for crash recovery.

    Usage (pause / begin request)::

        cb = WebCallbacks(location_ref="...", location_name="...", region_name="...")
        pipeline = AdventurePipeline(adventure=..., state=..., tui=cb, ...)
        task = asyncio.create_task(pipeline.run())
        async for event in drain_queue(cb.queue):
            yield sse_format(event)
        await save_session_output(session, iteration_id, cb.session_output)

    Usage (resume / advance request)::

        cb = WebCallbacks(
            location_ref="...", location_name="...", region_name="...",
            player_choice=1,  # or player_ack=True, player_text_input="...", etc.
        )
    """

    def __init__(
        self,
        location_ref: str | None,
        location_name: str | None,
        region_name: str | None,
        # Pre-loaded player decisions for resume requests. On an advance request the
        # pipeline re-runs from adventure_step_index, reaching the same decision point
        # that paused the previous run. Providing the input here causes the callback to
        # return the value immediately rather than pausing again.
        player_choice: int | None = None,
        player_ack: bool | None = None,
        player_text_input: str | None = None,
        player_skill_choice: int | None = None,
    ) -> None:
        self._queue: Queue[Dict[str, Any] | None] = Queue()
        self._session_output: List[Dict[str, Any]] = []
        self._context: Dict[str, Any] = {
            "location_ref": location_ref,
            "location_name": location_name,
            "region_name": region_name,
        }
        self._player_choice = player_choice
        self._player_ack = player_ack
        self._player_text_input = player_text_input
        self._player_skill_choice = player_skill_choice
        # Count how many pre-loaded decisions remain. When this is non-zero the
        # pipeline is replaying already-seen steps to reach the decision point;
        # show_text and show_combat_round are suppressed during replay so the
        # client does not receive duplicate narrative events.
        self._decisions_remaining: int = sum(
            1 for v in [player_choice, player_ack, player_text_input, player_skill_choice] if v is not None
        )
        # Tracks the choice index consumed from player_choice during this request
        # so the router can persist it in step_state after a pause.
        self._last_consumed_choice: int | None = None

    @property
    def queue(self) -> Queue[Dict[str, Any] | None]:
        """The asyncio Queue consumed by the SSE generator."""
        return self._queue

    @property
    def session_output(self) -> List[Dict[str, Any]]:
        """All non-sentinel events accumulated during this session."""
        return self._session_output

    @property
    def last_consumed_choice(self) -> int | None:
        """The choice index consumed from player_choice during this request, or None."""
        return self._last_consumed_choice

    async def show_text(self, text: str) -> None:
        """Emit a narrative SSE event and yield to the SSE consumer."""
        if self._decisions_remaining > 0:
            # Suppress replay emissions — the client has already seen this event
            # from a prior advance response and will see fresh events once past
            # the pre-loaded decision point.
            return
        event: Dict[str, Any] = {"type": "narrative", "data": {"text": text, "context": self._context}}
        await self._queue.put(event)
        self._session_output.append(event)
        await sleep(0)  # yield to SSE consumer so events are sent incrementally

    async def show_menu(self, prompt: str, options: List[str]) -> int:
        """Emit a choice SSE event, put the sentinel, and raise DecisionPauseException.

        In resume mode (player_choice is set) returns the pre-loaded choice
        immediately without queuing an event or raising.
        """
        if self._player_choice is not None:
            # Resume request — return the pre-loaded choice and do not pause.
            choice = self._player_choice
            self._player_choice = None
            self._last_consumed_choice = choice
            self._decisions_remaining -= 1
            return choice
        event: Dict[str, Any] = {
            "type": "choice",
            "data": {"prompt": prompt, "options": options, "context": self._context},
        }
        await self._queue.put(event)
        self._session_output.append(event)
        await self._queue.put(None)  # sentinel — signals end-of-stream to SSE consumer
        raise DecisionPauseException

    async def show_combat_round(
        self,
        player_hp: int,
        enemy_hp: int,
        player_name: str,
        enemy_name: str,
    ) -> None:
        """Emit a combat_state SSE event and yield to the SSE consumer."""
        if self._decisions_remaining > 0:
            return  # suppress replay emission
        event: Dict[str, Any] = {
            "type": "combat_state",
            "data": {
                "player_hp": player_hp,
                "enemy_hp": enemy_hp,
                "player_name": player_name,
                "enemy_name": enemy_name,
                "context": self._context,
            },
        }
        await self._queue.put(event)
        self._session_output.append(event)
        await sleep(0)

    async def wait_for_ack(self) -> None:
        """Emit an ack_required SSE event, put the sentinel, and raise DecisionPauseException.

        In resume mode (player_ack is set) returns immediately without pausing.
        """
        if self._player_ack is not None:
            # Resume request — consume the ack and do not pause.
            self._player_ack = None
            self._decisions_remaining -= 1
            return
        event: Dict[str, Any] = {"type": "ack_required", "data": {"context": self._context}}
        await self._queue.put(event)
        self._session_output.append(event)
        await self._queue.put(None)  # sentinel
        raise DecisionPauseException

    async def input_text(self, prompt: str) -> str:
        """Emit a text_input SSE event, put the sentinel, and raise DecisionPauseException.

        In resume mode (player_text_input is set) returns the pre-loaded string
        immediately without pausing.
        """
        if self._player_text_input is not None:
            # Resume request — return the pre-loaded text and do not pause.
            value = self._player_text_input
            self._player_text_input = None
            self._decisions_remaining -= 1
            return value
        event: Dict[str, Any] = {"type": "text_input", "data": {"prompt": prompt, "context": self._context}}
        await self._queue.put(event)
        self._session_output.append(event)
        await self._queue.put(None)  # sentinel
        raise DecisionPauseException

    async def show_skill_menu(self, skills: List[Dict[str, Any]]) -> int | None:
        """Emit a skill_menu SSE event, put the sentinel, and raise DecisionPauseException.

        In resume mode (player_skill_choice is set) returns the pre-loaded
        choice immediately without pausing.
        """
        if self._player_skill_choice is not None:
            # Resume request — return the pre-loaded skill choice and do not pause.
            choice = self._player_skill_choice
            self._player_skill_choice = None
            self._decisions_remaining -= 1
            return choice
        event: Dict[str, Any] = {"type": "skill_menu", "data": {"skills": skills, "context": self._context}}
        await self._queue.put(event)
        self._session_output.append(event)
        await self._queue.put(None)  # sentinel
        raise DecisionPauseException
