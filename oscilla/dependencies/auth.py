from logging import getLogger
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from oscilla.models.user import UserRecord
from oscilla.services.auth import decode_access_token
from oscilla.services.db import get_session_depends
from oscilla.settings import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
logger = getLogger(__name__)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
    request: Request,
) -> UserRecord:
    """Validate a JWT access token and return the authenticated UserRecord.

    Sets ``request.state.user_id`` to the authenticated user's UUID so that
    ``RequestLoggingMiddleware`` can associate log records with the user.

    Raises HTTP 401 if the token is invalid or the user is not found.
    Raises HTTP 403 if the user is inactive.
    Raises HTTP 403 if email verification is required and the user is unverified.
    """
    user_id = decode_access_token(token=token)

    stmt = select(UserRecord).where(UserRecord.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="User not found.")

    if not user.is_active:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Account is inactive.")

    if settings.require_email_verification and not user.is_email_verified:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Email not verified.")

    # Make the authenticated user's ID available to RequestLoggingMiddleware.
    request.state.user_id = user.id

    return user


async def get_verified_user(
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> UserRecord:
    """Require the current user to have a verified email address.

    Always enforces email verification regardless of the ``require_email_verification``
    setting. Use on routes that genuinely require a verified identity.
    """
    if not user.is_email_verified:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Email not verified.")
    return user
