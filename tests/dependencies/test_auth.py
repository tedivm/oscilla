from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from starlette.datastructures import State

from oscilla.dependencies.auth import get_current_user, get_verified_user
from oscilla.models.user import UserRecord
from oscilla.services.auth import create_access_token


def _mock_request() -> MagicMock:
    """Return a minimal mock Request with a mutable state object."""
    request = MagicMock()
    request.state = State()
    return request


@pytest.mark.asyncio
async def test_get_current_user_valid_token_returns_user(async_session: Any) -> None:
    """Valid token for an active, verified user returns the UserRecord."""
    user = UserRecord(user_key=None, email="valid@example.com", is_active=True, is_email_verified=True)
    async_session.add(user)
    await async_session.flush()

    token = create_access_token(user_id=user.id)
    result = await get_current_user(token=token, db=async_session, request=_mock_request())
    assert result.id == user.id


@pytest.mark.asyncio
async def test_get_current_user_sets_user_id_on_request_state(async_session: Any) -> None:
    """Successful authentication sets request.state.user_id to the user's UUID."""
    user = UserRecord(user_key=None, email="state@example.com", is_active=True, is_email_verified=True)
    async_session.add(user)
    await async_session.flush()

    token = create_access_token(user_id=user.id)
    mock_request = _mock_request()
    await get_current_user(token=token, db=async_session, request=mock_request)
    assert mock_request.state.user_id == user.id


@pytest.mark.asyncio
async def test_get_current_user_inactive_user_raises_403(async_session: Any) -> None:
    """Valid token for an inactive user raises HTTP 403."""
    user = UserRecord(user_key=None, email="inactive@example.com", is_active=False, is_email_verified=True)
    async_session.add(user)
    await async_session.flush()

    token = create_access_token(user_id=user.id)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=async_session, request=_mock_request())
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_user_user_id_not_set_on_exception(async_session: Any) -> None:
    """request.state.user_id is not set when authentication raises an exception."""
    user = UserRecord(user_key=None, email="nostate@example.com", is_active=False, is_email_verified=True)
    async_session.add(user)
    await async_session.flush()

    token = create_access_token(user_id=user.id)
    mock_request = _mock_request()
    with pytest.raises(HTTPException):
        await get_current_user(token=token, db=async_session, request=mock_request)
    assert not hasattr(mock_request.state, "user_id")


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_raises_401(async_session: Any) -> None:
    """Invalid (tampered) token raises HTTP 401."""
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token="this.is.not.a.valid.token", db=async_session, request=_mock_request())
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_require_verification_unverified_raises_403(
    async_session: Any, monkeypatch: Any
) -> None:
    """With require_email_verification=True, an unverified user raises HTTP 403."""
    user = UserRecord(user_key=None, email="unverified@example.com", is_active=True, is_email_verified=False)
    async_session.add(user)
    await async_session.flush()

    token = create_access_token(user_id=user.id)
    monkeypatch.setattr("oscilla.dependencies.auth.settings.require_email_verification", True)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=async_session, request=_mock_request())
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_user_no_verification_required_returns_unverified(
    async_session: Any, monkeypatch: Any
) -> None:
    """With require_email_verification=False, an unverified but active user is returned."""
    user = UserRecord(user_key=None, email="notverified@example.com", is_active=True, is_email_verified=False)
    async_session.add(user)
    await async_session.flush()

    token = create_access_token(user_id=user.id)
    monkeypatch.setattr("oscilla.dependencies.auth.settings.require_email_verification", False)
    result = await get_current_user(token=token, db=async_session, request=_mock_request())
    assert result.id == user.id


@pytest.mark.asyncio
async def test_get_verified_user_unverified_always_raises_403(async_session: Any, monkeypatch: Any) -> None:
    """get_verified_user raises HTTP 403 for unverified users regardless of settings."""
    user = UserRecord(user_key=None, email="neverver@example.com", is_active=True, is_email_verified=False)
    async_session.add(user)
    await async_session.flush()

    # Even when verification is NOT required by settings, get_verified_user enforces it
    monkeypatch.setattr("oscilla.dependencies.auth.settings.require_email_verification", False)
    with pytest.raises(HTTPException) as exc_info:
        await get_verified_user(user=user)
    assert exc_info.value.status_code == 403
