"""Characters router — CRUD for user-owned characters."""

from logging import getLogger
from typing import Annotated, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from oscilla.dependencies.auth import get_current_user
from oscilla.engine.character import DEFAULT_CHARACTER_NAME, CharacterState
from oscilla.engine.registry import ContentRegistry
from oscilla.models.api.characters import (
    CharacterCreate,
    CharacterStateRead,
    CharacterSummaryRead,
    CharacterUpdate,
    build_character_state_read,
    build_character_summary,
)
from oscilla.models.user import UserRecord
from oscilla.services.character import (
    delete_character_by_owner,
    get_character_record,
    get_prestige_count,
    list_all_characters_for_user,
    load_character,
    rename_character,
    save_character,
)
from oscilla.services.db import get_session_depends

logger = getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[CharacterSummaryRead])
async def list_characters(
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
    game: str | None = None,
) -> List[CharacterSummaryRead]:
    """Return all characters belonging to the authenticated user.

    Pass ``?game=<game_name>`` to filter to a single game.
    """
    records = await list_all_characters_for_user(session=db, user_id=user.id, game_name=game)
    results: List[CharacterSummaryRead] = []
    for record in records:
        prestige = await get_prestige_count(session=db, character_id=record.id)
        results.append(build_character_summary(record=record, prestige_count=prestige))
    return results


@router.post("", response_model=CharacterSummaryRead, status_code=HTTP_201_CREATED)
async def create_character(
    body: CharacterCreate,
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
    request: Request,
) -> CharacterSummaryRead:
    """Create a new character for the authenticated user.

    The ``game_name`` must correspond to a loaded game registry. Returns
    ``CharacterSummaryRead`` with HTTP 201 on success.
    """
    registries: Dict[str, ContentRegistry] = request.app.state.registries
    registry = registries.get(body.game_name)
    if registry is None:
        raise HTTPException(status_code=422, detail=f"Unknown game '{body.game_name}'.")

    assert registry.game is not None
    assert registry.character_config is not None

    # Resolve the character name: game-level default_name, then engine fallback.
    # User identity fields are never used as character names to avoid leaking PII.
    creation_cfg = registry.game.spec.character_creation
    if creation_cfg is not None and creation_cfg.default_name is not None:
        character_name = creation_cfg.default_name
    else:
        character_name = DEFAULT_CHARACTER_NAME

    state = CharacterState.new_character(
        name=character_name,
        game_manifest=registry.game,
        character_config=registry.character_config,
    )
    # Enqueue the on_character_create trigger before persisting — mirrors the
    # same logic in session.py._create_new_character() for the TUI flow.
    if "on_character_create" in registry.trigger_index:
        state.enqueue_trigger(
            "on_character_create",
            max_depth=registry.game.spec.triggers.max_trigger_queue_depth,
        )
    try:
        await save_character(session=db, state=state, user_id=user.id, game_name=body.game_name)
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"A character named '{character_name}' already exists for this game.",
        )

    record = await get_character_record(session=db, character_id=state.character_id)
    assert record is not None

    return build_character_summary(record=record, prestige_count=state.prestige_count)


@router.get("/{character_id}", response_model=CharacterStateRead)
async def get_character(
    character_id: UUID,
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
    request: Request,
) -> CharacterStateRead:
    """Return the full character state for an owned character.

    Returns 404 if the character does not exist or is not owned by the caller.
    """
    record = await get_character_record(session=db, character_id=character_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Character not found.")

    registries: Dict[str, ContentRegistry] = request.app.state.registries
    registry = registries.get(record.game_name)
    if registry is None:
        raise HTTPException(status_code=404, detail=f"Game '{record.game_name}' is no longer loaded.")

    assert registry.character_config is not None

    state = await load_character(
        session=db,
        character_id=character_id,
        character_config=registry.character_config,
        registry=registry,
    )
    if state is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    return build_character_state_read(
        record=record,
        state=state,
        registry=registry,
        char_config=registry.character_config,
    )


@router.delete("/{character_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_character(
    character_id: UUID,
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> None:
    """Delete an owned character and all associated data.

    Returns 404 if the character does not exist or is not owned by the caller.
    """
    deleted = await delete_character_by_owner(session=db, character_id=character_id, user_id=user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Character not found.")


@router.patch("/{character_id}", response_model=CharacterSummaryRead)
async def update_character(
    character_id: UUID,
    body: CharacterUpdate,
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> CharacterSummaryRead:
    """Rename an owned character.

    Returns 422 if the new name is blank after stripping whitespace.
    Returns 404 if the character does not exist or is not owned by the caller.
    """
    record = await get_character_record(session=db, character_id=character_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Character not found.")

    if body.name is not None:
        stripped = body.name.strip()
        if not stripped:
            raise HTTPException(status_code=422, detail="Character name must not be blank.")
        await rename_character(session=db, character_id=character_id, new_name=stripped)
        # Re-fetch to get the updated name.
        record = await get_character_record(session=db, character_id=character_id)
        assert record is not None

    prestige = await get_prestige_count(session=db, character_id=record.id)
    return build_character_summary(record=record, prestige_count=prestige)
