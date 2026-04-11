import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import select

from oscilla.models.auth import AuthRefreshTokenRecord
from oscilla.models.user import UserRecord
from oscilla.services.auth import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    make_reset_token,
    make_verify_token,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_email_token,
    verify_password,
    verify_reset_token,
)
from oscilla.settings import settings


def test_hash_verify_password_roundtrip() -> None:
    """hash_password / verify_password round-trip returns True."""
    plaintext = "supersecret123"
    hashed = hash_password(plaintext)
    assert verify_password(hashed=hashed, plaintext=plaintext) is True


def test_verify_password_wrong_plaintext_returns_false() -> None:
    """verify_password with wrong plaintext returns False."""
    hashed = hash_password("correct-password")
    assert verify_password(hashed=hashed, plaintext="wrong-password") is False


def test_create_decode_access_token_roundtrip() -> None:
    """create_access_token / decode_access_token round-trip returns original user_id."""
    user_id = uuid4()
    token = create_access_token(user_id=user_id)
    decoded = decode_access_token(token=token)
    assert decoded == user_id


def test_decode_access_token_expired_raises_401() -> None:
    """decode_access_token with an expired token raises HTTPException(401)."""
    user_id = uuid4()
    # Build a token that expired in the past
    payload = {
        "sub": str(user_id),
        "iat": datetime(2020, 1, 1, tzinfo=UTC),
        "exp": datetime(2020, 1, 1, 0, 0, 1, tzinfo=UTC),
    }
    expired_token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token=expired_token)
    assert exc_info.value.status_code == 401


def test_decode_access_token_tampered_raises_401() -> None:
    """decode_access_token with a tampered token raises HTTPException(401)."""
    token = create_access_token(user_id=uuid4())
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token=tampered)
    assert exc_info.value.status_code == 401


def test_make_verify_email_token_roundtrip() -> None:
    """make_verify_token / verify_email_token round-trip returns original user_id."""
    user_id = uuid4()
    token = make_verify_token(user_id=user_id)
    result = verify_email_token(token=token)
    assert result == user_id


def test_verify_email_token_expired_returns_none(monkeypatch: Any) -> None:
    """verify_email_token with an expired token returns None."""
    user_id = uuid4()
    old_serializer = URLSafeTimedSerializer(settings.jwt_secret.get_secret_value())
    token = old_serializer.dumps(str(user_id), salt="email-verify")

    # Negative hours produce a negative max_age, which causes itsdangerous to
    # reject every token as expired regardless of when it was signed.
    monkeypatch.setattr("oscilla.services.auth.settings.email_verify_token_expire_hours", -1)
    result = verify_email_token(token=token)
    assert result is None


def test_make_reset_token_roundtrip() -> None:
    """make_reset_token / verify_reset_token round-trip returns original user_id."""
    user_id = uuid4()
    token = make_reset_token(user_id=user_id)
    result = verify_reset_token(token=token)
    assert result == user_id


@pytest.mark.asyncio
async def test_create_refresh_token_inserts_row(async_session: Any) -> None:
    """create_refresh_token inserts a row and returns a non-empty string."""
    user = UserRecord(user_key=None, email="rt@example.com")
    async_session.add(user)
    await async_session.flush()

    token = await create_refresh_token(session=async_session, user_id=user.id)
    assert isinstance(token, str)
    assert len(token) > 0


@pytest.mark.asyncio
async def test_rotate_refresh_token_revokes_old_and_returns_new(async_session: Any) -> None:
    """rotate_refresh_token revokes the old row and returns a new token."""
    user = UserRecord(user_key=None, email="rotate@example.com")
    async_session.add(user)
    await async_session.flush()

    original_token = await create_refresh_token(session=async_session, user_id=user.id)
    new_token, user_id = await rotate_refresh_token(session=async_session, token=original_token)

    assert new_token != original_token
    assert user_id == user.id

    # The old token hash should now be revoked
    old_hash = hashlib.sha256(original_token.encode()).hexdigest()
    stmt = select(AuthRefreshTokenRecord).where(AuthRefreshTokenRecord.token_hash == old_hash)
    result = await async_session.execute(stmt)
    old_record = result.scalar_one_or_none()
    assert old_record is not None
    assert old_record.revoked is True


@pytest.mark.asyncio
async def test_rotate_refresh_token_revoked_raises_401(async_session: Any) -> None:
    """rotate_refresh_token with a revoked token raises HTTPException(401)."""
    user = UserRecord(user_key=None, email="revoked@example.com")
    async_session.add(user)
    await async_session.flush()

    token = await create_refresh_token(session=async_session, user_id=user.id)
    # Rotate once to revoke it
    await rotate_refresh_token(session=async_session, token=token)

    # Second rotation on original token must fail
    with pytest.raises(HTTPException) as exc_info:
        await rotate_refresh_token(session=async_session, token=token)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_revoke_refresh_token_is_idempotent(async_session: Any) -> None:
    """revoke_refresh_token is idempotent when called twice."""
    user = UserRecord(user_key=None, email="idempotent@example.com")
    async_session.add(user)
    await async_session.flush()

    token = await create_refresh_token(session=async_session, user_id=user.id)
    # Revoking twice should not raise
    await revoke_refresh_token(session=async_session, token=token)
    await revoke_refresh_token(session=async_session, token=token)


@pytest.mark.asyncio
async def test_rotate_expired_refresh_token_raises_401(async_session: Any) -> None:
    """rotate_refresh_token raises HTTPException(401) when the token is expired."""
    user = UserRecord(user_key=None, email="expired-rotate@example.com")
    async_session.add(user)
    await async_session.flush()

    token = await create_refresh_token(session=async_session, user_id=user.id)

    # Force the token to be expired by backdating expires_at
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stmt = select(AuthRefreshTokenRecord).where(AuthRefreshTokenRecord.token_hash == token_hash)
    result = await async_session.execute(stmt)
    record = result.scalar_one()
    record.expires_at = datetime.now(UTC) - timedelta(days=1)
    await async_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await rotate_refresh_token(session=async_session, token=token)
    assert exc_info.value.status_code == 401


def test_password_reset_token_rejected_by_verify_email_token() -> None:
    """A password-reset token must be rejected by verify_email_token (cross-salt rejection)."""
    # make_reset_token uses a different salt than make_verify_token, so the token
    # must not be accepted by the email-verification endpoint.
    user_id = uuid4()
    reset_token = make_reset_token(user_id=user_id)
    assert verify_email_token(token=reset_token) is None
