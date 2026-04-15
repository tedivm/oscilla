"""Play router — SSE-based adventure execution and session management."""

from __future__ import annotations

import asyncio
import json
import random
import time as _time
from collections.abc import AsyncIterator
from datetime import datetime
from logging import getLogger
from typing import Annotated, Any, Dict, List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_204_NO_CONTENT

from oscilla.dependencies.auth import get_current_user
from oscilla.engine.conditions import evaluate
from oscilla.engine.pipeline import AdventurePipeline
from oscilla.engine.session import WebPersistCallback
from oscilla.engine.web_callbacks import DecisionPauseException, WebCallbacks
from oscilla.models.character_iteration import CharacterIterationRecord
from oscilla.models.user import UserRecord
from oscilla.services.character import (
    acquire_web_session_lock,
    clear_session_output,
    force_acquire_web_session_lock,
    get_active_iteration_record,
    get_character_record,
    get_session_output,
    load_character,
    release_web_session_lock,
    save_adventure_progress,
    save_session_output,
)
from oscilla.services.db import get_session_depends
from oscilla.settings import settings as _settings

logger = getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class GoAdventureRequest(BaseModel):
    location_ref: str = Field(description="Location ref to begin an adventure from.")


class AdvanceRequest(BaseModel):
    choice: int | None = Field(default=None, ge=1, description="1-based choice index.")
    ack: bool | None = Field(default=None, description="Acknowledgement for ack_required events.")
    text_input: str | None = Field(default=None, description="Text response for text_input events.")
    skill_choice: int | None = Field(default=None, ge=1, description="1-based skill menu choice.")


class PendingStateRead(BaseModel):
    character_id: UUID
    # The last SSE decision event (choice/ack_required/text_input/skill_menu), if any.
    pending_event: Dict[str, Any] | None
    # All SSE events produced during the current session, in emission order.
    session_output: List[Dict[str, Any]]


class SessionConflictRead(BaseModel):
    detail: str
    acquired_at: datetime
    character_id: UUID


# ---------------------------------------------------------------------------
# SSE streaming helper
# ---------------------------------------------------------------------------

_DECISION_EVENT_TYPES = {"choice", "ack_required", "text_input", "skill_menu"}


async def _persist_session_output(
    db: AsyncSession,
    iteration_id: UUID,
    events: List[Dict[str, Any]],
) -> None:
    """Persist the accumulated SSE events to character_session_output."""
    try:
        await save_session_output(session=db, iteration_id=iteration_id, events=events)
    except Exception:
        logger.exception("Failed to persist session output for iteration %s.", iteration_id)


async def _run_pipeline(
    pipeline: AdventurePipeline,
    web_cb: WebCallbacks,
    adventure_ref: str,
    start_step: int,
) -> None:
    """Run the adventure pipeline and always put a None sentinel when done.

    DecisionPauseException and CancelledError both put their own sentinel before
    raising so we must not add a second one. All other termination paths
    (normal completion or unexpected exception) need to add the sentinel so the
    SSE consumer can exit its receive loop.
    """
    sentinel_needed = True
    try:
        await pipeline.run(adventure_ref=adventure_ref, start_step=start_step)
    except (DecisionPauseException, asyncio.CancelledError):
        # Sentinel was already placed on the queue before the exception was raised.
        sentinel_needed = False
        raise
    finally:
        if sentinel_needed:
            await web_cb.queue.put(None)


async def _run_pipeline_and_stream(
    pipeline: AdventurePipeline,
    web_cb: WebCallbacks,
    db: AsyncSession,
    iteration_id: UUID,
    adventure_ref: str,
    session_token: str,
    start_step: int = 0,
) -> AsyncIterator[str]:
    """Async generator: run the pipeline as a task and yield SSE-formatted strings.

    The pipeline runs concurrently via asyncio.create_task. Events are drained
    from web_cb.queue. A None sentinel signals end-of-stream. After the stream
    closes (normally or on client disconnect), session output is persisted and
    the session lock is released so the next advance can acquire it.
    """
    pipeline_task = asyncio.create_task(
        _run_pipeline(pipeline=pipeline, web_cb=web_cb, adventure_ref=adventure_ref, start_step=start_step)
    )
    pipeline_decision_paused = False
    try:
        while True:
            event = await web_cb.queue.get()
            if event is None:
                break
            yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
    finally:
        if not pipeline_task.done():
            pipeline_task.cancel()
        try:
            await pipeline_task
        except DecisionPauseException:
            # Normal pause at a player decision point.
            pipeline_decision_paused = True
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Pipeline task raised an unexpected exception.")

    # Persist session output after the stream closes so frontend can replay events.
    await _persist_session_output(db=db, iteration_id=iteration_id, events=web_cb.session_output)
    # When a choice was consumed in replay mode and the pipeline paused again,
    # persist the choice index in step_state so the next advance can re-enter
    # the same branch without re-presenting the choice to the player.
    if pipeline_decision_paused and web_cb.last_consumed_choice is not None:
        await save_adventure_progress(
            session=db,
            iteration_id=iteration_id,
            adventure_ref=adventure_ref,
            step_index=start_step,
            step_state={"pending_choice": web_cb.last_consumed_choice},
        )
    # Release the session lock so the next advance/begin request can proceed.
    await release_web_session_lock(session=db, iteration_id=iteration_id, token=session_token)


# ---------------------------------------------------------------------------
# Ownership + registry resolution helpers
# ---------------------------------------------------------------------------


async def _require_character_and_registry(
    character_id: UUID,
    user: UserRecord,
    db: AsyncSession,
    request: Request,
) -> tuple[CharacterIterationRecord, Any]:
    """Resolve character ownership and game registry.

    Returns (iteration_record, registry). Raises HTTPException on failure.
    """
    record = await get_character_record(session=db, character_id=character_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Character not found.")

    registries = request.app.state.registries
    registry = registries.get(record.game_name)
    if registry is None:
        raise HTTPException(status_code=404, detail=f"Game '{record.game_name}' is no longer loaded.")

    iteration = await get_active_iteration_record(session=db, character_id=character_id)
    if iteration is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    return iteration, registry


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/characters/{character_id}/play/current", response_model=PendingStateRead)
async def get_play_current(
    character_id: UUID,
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> PendingStateRead:
    """Return the persisted session output for crash recovery.

    Returns an empty ``session_output`` list for a fresh character.
    """
    record = await get_character_record(session=db, character_id=character_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Character not found.")

    iteration = await get_active_iteration_record(session=db, character_id=character_id)
    if iteration is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    events = await get_session_output(session=db, iteration_id=iteration.id)
    pending: Dict[str, Any] | None = None
    if events and events[-1].get("type") in _DECISION_EVENT_TYPES:
        pending = events[-1]

    return PendingStateRead(character_id=character_id, pending_event=pending, session_output=events)


@router.post("/characters/{character_id}/play/go")
async def go_adventure(
    character_id: UUID,
    body: GoAdventureRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
    request: Request,
) -> StreamingResponse:
    """Select and begin an adventure via weighted random from the location's eligible pool.

    Steps:
    1. Validate location exists in the registry (422 if not).
    2. Load character state (404 if not found).
    3. Validate location is accessible to this character via unlock conditions (422 if not).
    4. Build eligible pool: adventures whose `requires` conditions pass and repeat controls allow.
    5. Return 422 if pool is empty.
    6. Select one adventure via weighted random — result is never revealed to the client.
    7. Acquire session lock (409 if already held).
    8. Stream the adventure as SSE.
    """
    iteration, registry = await _require_character_and_registry(
        character_id=character_id, user=user, db=db, request=request
    )

    # 1. Validate location exists in the registry.
    loc = registry.locations.get(body.location_ref)
    if loc is None:
        raise HTTPException(status_code=422, detail=f"Unknown location '{body.location_ref}'.")

    if registry.character_config is None:
        raise HTTPException(status_code=500, detail="Game not configured.")

    # 2. Load character state (required to evaluate unlock conditions and adventure eligibility).
    state = await load_character(
        session=db,
        character_id=character_id,
        character_config=registry.character_config,
        registry=registry,
    )
    if state is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    # 3. Validate the location is accessible to this character.
    #    Unlock conditions may reference character stats, so the full state is required.
    if not evaluate(loc.spec.effective_unlock, state, registry):
        raise HTTPException(status_code=422, detail=f"Location '{body.location_ref}' is not accessible.")

    # 4. Build the eligible pool: same filter as the TUI (conditions + repeat controls).
    now_ts = int(_time.time())
    eligible = [
        entry
        for entry in loc.spec.adventures
        if evaluate(entry.requires, state, registry)
        and state.is_adventure_eligible(
            adventure_ref=entry.ref,
            spec=registry.adventures.require(entry.ref, "Adventure").spec,
            now_ts=now_ts,
        )
    ]

    if not eligible:
        raise HTTPException(status_code=422, detail="No adventures are available at this location right now.")

    # 5. Weighted random selection — never exposed to the client.
    weights = [entry.weight for entry in eligible]
    (chosen_entry,) = random.choices(population=eligible, weights=weights, k=1)
    adventure_ref = chosen_entry.ref

    # 6. Acquire session lock.
    token = str(uuid4())
    conflict_dt = await acquire_web_session_lock(
        session=db,
        iteration_id=iteration.id,
        token=token,
        stale_threshold_minutes=_settings.stale_session_threshold_minutes,
    )
    if conflict_dt is not None:
        raise HTTPException(
            status_code=409,
            detail=SessionConflictRead(
                detail="A live session is already in progress.",
                acquired_at=conflict_dt,
                character_id=character_id,
            ).model_dump(mode="json"),
        )

    await clear_session_output(session=db, iteration_id=iteration.id)

    # 7. Resolve location context for SSE event metadata.
    region = registry.regions.get(loc.spec.region)
    web_cb = WebCallbacks(
        location_ref=body.location_ref,
        location_name=loc.spec.displayName,
        region_name=region.spec.displayName if region is not None else None,
    )
    persist_cb = WebPersistCallback(
        db_session=db,
        iteration_id=iteration.id,
        initial_state=state,
        character_config=registry.character_config,
        registry=registry,
    )
    pipeline = AdventurePipeline(
        registry=registry,
        player=state,
        tui=web_cb,
        on_state_change=persist_cb,
    )

    # 8. Stream the adventure.
    return StreamingResponse(
        _run_pipeline_and_stream(
            pipeline=pipeline,
            web_cb=web_cb,
            db=db,
            iteration_id=iteration.id,
            adventure_ref=adventure_ref,
            session_token=token,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/characters/{character_id}/play/advance")
async def advance_adventure(
    character_id: UUID,
    body: AdvanceRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
    request: Request,
) -> StreamingResponse:
    """Submit a player decision and resume the adventure from the persisted step.

    Returns 422 if the character has no active adventure.
    Returns 409 if a live session lock exists.
    """
    iteration, registry = await _require_character_and_registry(
        character_id=character_id, user=user, db=db, request=request
    )

    if iteration.adventure_ref is None or iteration.adventure_step_index is None:
        raise HTTPException(status_code=422, detail="No active adventure on this character.")

    token = str(uuid4())
    conflict_dt = await acquire_web_session_lock(
        session=db,
        iteration_id=iteration.id,
        token=token,
        stale_threshold_minutes=_settings.stale_session_threshold_minutes,
    )
    if conflict_dt is not None:
        raise HTTPException(
            status_code=409,
            detail=SessionConflictRead(
                detail="A live session is already in progress.",
                acquired_at=conflict_dt,
                character_id=character_id,
            ).model_dump(mode="json"),
        )

    assert registry.character_config is not None

    state = await load_character(
        session=db,
        character_id=character_id,
        character_config=registry.character_config,
        registry=registry,
    )
    if state is None:
        await release_web_session_lock(session=db, iteration_id=iteration.id, token=token)
        raise HTTPException(status_code=404, detail="Character not found.")

    # When the request is not a fresh choice submission, restore any pending
    # choice index previously stored in step_state. This allows the pipeline
    # to replay the choice step silently and re-enter the correct option branch
    # so subsequent decisions (ack/text/skill) are consumed in the right context.
    step_state = iteration.adventure_step_state or {}
    pending_choice: int | None = None
    if body.choice is None:
        raw = step_state.get("pending_choice")
        if isinstance(raw, int):
            pending_choice = raw

    web_cb = WebCallbacks(
        location_ref=None,
        location_name=None,
        region_name=None,
        player_choice=body.choice if body.choice is not None else pending_choice,
        player_ack=body.ack,
        player_text_input=body.text_input,
        player_skill_choice=body.skill_choice,
    )
    persist_cb = WebPersistCallback(
        db_session=db,
        iteration_id=iteration.id,
        initial_state=state,
        character_config=registry.character_config,
        registry=registry,
    )
    pipeline = AdventurePipeline(
        registry=registry,
        player=state,
        tui=web_cb,
        on_state_change=persist_cb,
    )

    return StreamingResponse(
        _run_pipeline_and_stream(
            pipeline=pipeline,
            web_cb=web_cb,
            db=db,
            iteration_id=iteration.id,
            adventure_ref=iteration.adventure_ref,
            session_token=token,
            start_step=iteration.adventure_step_index,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/characters/{character_id}/play/abandon", status_code=HTTP_204_NO_CONTENT)
async def abandon_adventure(
    character_id: UUID,
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> None:
    """Exit the current adventure without completing it.

    Clears adventure state, session output, and the session lock.
    """
    record = await get_character_record(session=db, character_id=character_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Character not found.")

    iteration = await get_active_iteration_record(session=db, character_id=character_id)
    if iteration is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    await save_adventure_progress(
        session=db,
        iteration_id=iteration.id,
        adventure_ref=None,
        step_index=None,
        step_state=None,
    )
    await clear_session_output(session=db, iteration_id=iteration.id)
    if iteration.session_token is not None:
        await release_web_session_lock(session=db, iteration_id=iteration.id, token=iteration.session_token)


@router.post("/characters/{character_id}/play/takeover", response_model=PendingStateRead)
async def takeover_session(
    character_id: UUID,
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> PendingStateRead:
    """Force-acquire the session lock, displacing any existing holder.

    Returns the current ``PendingStateRead`` so the frontend can resume
    without a second round-trip.
    """
    record = await get_character_record(session=db, character_id=character_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Character not found.")

    iteration = await get_active_iteration_record(session=db, character_id=character_id)
    if iteration is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    token = str(uuid4())
    await force_acquire_web_session_lock(session=db, iteration_id=iteration.id, token=token)

    events = await get_session_output(session=db, iteration_id=iteration.id)
    pending: Dict[str, Any] | None = None
    if events and events[-1].get("type") in _DECISION_EVENT_TYPES:
        pending = events[-1]

    return PendingStateRead(character_id=character_id, pending_event=pending, session_output=events)
