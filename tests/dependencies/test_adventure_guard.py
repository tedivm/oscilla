"""Tests for the require_no_active_adventure dependency."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException

from oscilla.dependencies.adventure_guard import require_no_active_adventure
from oscilla.models.character import CharacterRecord
from oscilla.models.character_iteration import CharacterIterationRecord


@pytest.mark.asyncio
async def test_allows_request_when_no_iteration_exists(async_session: Any) -> None:
    """No active iteration → dependency passes through without raising."""
    character_id = uuid4()
    # No CharacterRecord or iteration inserted — get_active_iteration_record returns None.
    await require_no_active_adventure(character_id=character_id, db=async_session)


@pytest.mark.asyncio
async def test_allows_request_when_iteration_has_no_lock(async_session: Any) -> None:
    """Active iteration with session_token=None → dependency passes through."""
    user_id = uuid4()
    character = CharacterRecord(user_id=user_id, name="Hero", game_name="test-game")
    async_session.add(character)
    await async_session.flush()

    iteration = CharacterIterationRecord(
        character_id=character.id,
        iteration=0,
        is_active=True,
        session_token=None,
    )
    async_session.add(iteration)
    await async_session.flush()

    # Should not raise
    await require_no_active_adventure(character_id=character.id, db=async_session)


@pytest.mark.asyncio
async def test_raises_409_when_session_lock_is_held(async_session: Any) -> None:
    """Active iteration with a live session_token → dependency raises HTTP 409."""
    user_id = uuid4()
    character = CharacterRecord(user_id=user_id, name="Hero", game_name="test-game")
    async_session.add(character)
    await async_session.flush()

    iteration = CharacterIterationRecord(
        character_id=character.id,
        iteration=0,
        is_active=True,
        session_token="some-live-token",
    )
    async_session.add(iteration)
    await async_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await require_no_active_adventure(character_id=character.id, db=async_session)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "active_adventure"
    assert exc_info.value.detail["character_id"] == str(character.id)
