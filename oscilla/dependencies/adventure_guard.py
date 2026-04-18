"""FastAPI dependency — blocks state-mutating requests while a session lock is live."""

from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from oscilla.services.character import get_active_iteration_record
from oscilla.services.db import get_session_depends

logger = getLogger(__name__)


async def require_no_active_adventure(
    character_id: UUID,
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> None:
    """Raise 409 Conflict when the character has a live web session lock.

    Apply to all state-mutating character endpoints outside the play flow.
    The play router manages session locks itself and must not use this guard.

    The 409 detail body is a structured dict so the frontend can redirect the
    user directly to the play screen:
        {
            "code": "active_adventure",
            "character_id": "<uuid>"
        }
    """
    iteration = await get_active_iteration_record(session=db, character_id=character_id)
    if iteration is not None and iteration.session_token is not None:
        logger.warning(
            "State-mutation blocked for character %s — active session lock held by token %r",
            character_id,
            iteration.session_token,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "active_adventure",
                "character_id": str(character_id),
            },
        )
