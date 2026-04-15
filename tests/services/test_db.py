"""Unit tests for the db service layer, including test_data seed function."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oscilla.models.user import UserRecord
from oscilla.services.auth import verify_password
from oscilla.services.db import test_data as seed_data

_DEV_EMAIL = "dev@example.com"
_DEV_PASSWORD = "devpassword"
_DEV_DISPLAY_NAME = "Dev User"


@pytest.mark.asyncio
async def test_test_data_creates_dev_user(async_session: AsyncSession) -> None:
    """test_data creates the dev@example.com account on first call."""
    await seed_data(async_session)

    stmt = select(UserRecord).where(UserRecord.email == _DEV_EMAIL)
    result = await async_session.execute(stmt)
    user = result.scalar_one_or_none()

    assert user is not None
    assert user.email == _DEV_EMAIL
    assert user.display_name == _DEV_DISPLAY_NAME


@pytest.mark.asyncio
async def test_test_data_dev_user_is_active_and_verified(async_session: AsyncSession) -> None:
    """Dev user is active and has email verification pre-confirmed."""
    await seed_data(async_session)

    stmt = select(UserRecord).where(UserRecord.email == _DEV_EMAIL)
    result = await async_session.execute(stmt)
    user = result.scalar_one_or_none()

    assert user is not None
    assert user.is_active is True
    assert user.is_email_verified is True


@pytest.mark.asyncio
async def test_test_data_dev_user_password_is_correct(async_session: AsyncSession) -> None:
    """Dev user password hash verifies correctly against the known plaintext."""
    await seed_data(async_session)

    stmt = select(UserRecord).where(UserRecord.email == _DEV_EMAIL)
    result = await async_session.execute(stmt)
    user = result.scalar_one_or_none()

    assert user is not None
    assert user.hashed_password is not None
    assert verify_password(user.hashed_password, _DEV_PASSWORD) is True


@pytest.mark.asyncio
async def test_test_data_is_idempotent(async_session: AsyncSession) -> None:
    """Calling test_data twice does not raise and does not create duplicate users."""
    await seed_data(async_session)
    await seed_data(async_session)

    stmt = select(UserRecord).where(UserRecord.email == _DEV_EMAIL)
    result = await async_session.execute(stmt)
    users = result.scalars().all()

    assert len(users) == 1
