import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from aiocache import caches  # type: ignore[import-untyped]
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_401_UNAUTHORIZED

from oscilla.models.auth import AuthRefreshTokenRecord
from oscilla.models.auth_audit_log import AuthAuditLogRecord
from oscilla.services.email import send_email
from oscilla.services.jinja import env
from oscilla.settings import settings

_ph = PasswordHasher()
_s = URLSafeTimedSerializer(settings.jwt_secret.get_secret_value())


def hash_password(plaintext: str) -> str:
    """Return an Argon2id hash of the given plaintext password."""
    return _ph.hash(plaintext)


def verify_password(hashed: str, plaintext: str) -> bool:
    """Return True if plaintext matches the Argon2id hash; False on mismatch."""
    try:
        return _ph.verify(hashed, plaintext)
    except VerifyMismatchError:
        return False


def create_access_token(user_id: UUID) -> str:
    """Encode a short-lived JWT access token for the given user."""
    utcnow = datetime.now(tz=UTC)
    payload = {
        "sub": str(user_id),
        "iat": utcnow,
        "exp": utcnow + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")


def decode_access_token(token: str) -> UUID:
    """Decode and validate a JWT access token; returns the user ID on success.

    Raises ``HTTPException(401)`` for expired or invalid tokens.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
        )
        return UUID(payload["sub"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc


async def create_refresh_token(session: AsyncSession, user_id: UUID) -> str:
    """Generate an opaque refresh token, persist its SHA-256 hash, and return the plaintext token."""
    plaintext = str(uuid4())
    token_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    expires_at = datetime.now(tz=UTC) + timedelta(days=settings.refresh_token_expire_days)
    record = AuthRefreshTokenRecord(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(record)
    await session.flush()
    return plaintext


async def rotate_refresh_token(session: AsyncSession, token: str) -> tuple[str, UUID]:
    """Revoke the given refresh token and issue a new one.

    Raises ``HTTPException(401)`` if the token is not found, is revoked, or is expired.
    Returns a tuple of (new_plaintext_token, user_id).
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    utcnow = datetime.now(tz=UTC)
    stmt = select(AuthRefreshTokenRecord).where(
        and_(
            AuthRefreshTokenRecord.token_hash == token_hash,
            AuthRefreshTokenRecord.revoked == False,  # noqa: E712
            AuthRefreshTokenRecord.expires_at > utcnow,
        )
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token.")
    user_id = record.user_id
    record.revoked = True
    new_token = await create_refresh_token(session=session, user_id=user_id)
    return new_token, user_id


async def revoke_refresh_token(session: AsyncSession, token: str) -> None:
    """Mark the given refresh token as revoked (idempotent — no error if not found)."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stmt = select(AuthRefreshTokenRecord).where(AuthRefreshTokenRecord.token_hash == token_hash)
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if record is not None:
        record.revoked = True


def make_verify_token(user_id: UUID) -> str:
    """Create a time-limited HMAC token for email verification."""
    return _s.dumps(str(user_id), salt="email-verify")


def make_reset_token(user_id: UUID) -> str:
    """Create a time-limited HMAC token for password reset."""
    return _s.dumps(str(user_id), salt="password-reset")


def verify_email_token(token: str) -> UUID | None:
    """Validate an email verification token; returns the user ID or None on failure."""
    max_age = settings.email_verify_token_expire_hours * 3600
    try:
        raw = _s.loads(token, salt="email-verify", max_age=max_age)
        return UUID(raw)
    except (SignatureExpired, BadSignature):
        return None


def verify_reset_token(token: str) -> UUID | None:
    """Validate a password reset token; returns the user ID or None on failure."""
    max_age = settings.password_reset_token_expire_hours * 3600
    try:
        raw = _s.loads(token, salt="password-reset", max_age=max_age)
        return UUID(raw)
    except (SignatureExpired, BadSignature):
        return None


async def send_verification_email(email: str, user_id: UUID, display_name: str | None) -> None:
    """Render the verification email templates and dispatch via the email service."""
    token = make_verify_token(user_id=user_id)
    action_url = f"{settings.base_url}/auth/verify/{token}"
    expiry_description = f"{settings.email_verify_token_expire_hours} hours"
    name = display_name or "there"

    body_html = env.get_template("email/verification.html").render(
        display_name=name,
        action_url=action_url,
        expiry_description=expiry_description,
    )
    body_text = env.get_template("email/verification.txt").render(
        display_name=name,
        action_url=action_url,
        expiry_description=expiry_description,
    )
    await send_email(
        to=email,
        subject="Verify your Oscilla account",
        body_html=body_html,
        body_text=body_text,
    )


async def send_reset_email(email: str, user_id: UUID, display_name: str | None) -> None:
    """Render the password-reset email templates and dispatch via the email service."""
    token = make_reset_token(user_id=user_id)
    action_url = f"{settings.base_url}/auth/password-reset/{token}"
    expiry_description = f"{settings.password_reset_token_expire_hours} hour(s)"
    name = display_name or "there"

    body_html = env.get_template("email/password_reset.html").render(
        display_name=name,
        action_url=action_url,
        expiry_description=expiry_description,
    )
    body_text = env.get_template("email/password_reset.txt").render(
        display_name=name,
        action_url=action_url,
        expiry_description=expiry_description,
    )
    await send_email(
        to=email,
        subject="Reset your Oscilla password",
        body_html=body_html,
        body_text=body_text,
    )


# ---------------------------------------------------------------------------
# Account lockout
# ---------------------------------------------------------------------------


async def record_failed_login(email: str) -> bool:
    """Record a failed login attempt and lock the account if the threshold is reached.

    Increments the consecutive failure counter for the email. Sets a TTL on
    the first increment so the counter auto-expires after the lockout window.
    If the count reaches ``settings.max_login_attempts_before_lockout``, a
    separate lockout key is set to prevent further logins.

    Returns:
        ``True`` if the account is now locked, ``False`` otherwise.
    """
    cache = caches.get("persistent")
    count_key = f"lockout_count:{email}"
    count: int = await cache.increment(count_key, delta=1)

    if count == 1:
        await cache.expire(count_key, ttl=settings.lockout_window_seconds)

    if count >= settings.max_login_attempts_before_lockout:
        lockout_key = f"lockout:{email}"
        lockout_ttl = settings.lockout_duration_minutes * 60
        await cache.set(lockout_key, True, ttl=lockout_ttl)
        return True

    return False


async def is_account_locked(email: str) -> bool:
    """Return ``True`` if the account is currently locked out."""
    cache = caches.get("persistent")
    result: bool = await cache.exists(f"lockout:{email}")
    return result


async def clear_lockout(email: str) -> None:
    """Clear lockout and failure counter keys for the given email (call on successful login)."""
    cache = caches.get("persistent")
    await cache.delete(f"lockout:{email}")
    await cache.delete(f"lockout_count:{email}")


# ---------------------------------------------------------------------------
# Auth audit log
# ---------------------------------------------------------------------------


async def record_auth_event(
    session: AsyncSession,
    event_type: str,
    user_id: UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Append an audit log record for an authentication event.

    Does NOT commit the session — the caller controls transaction boundaries.

    Args:
        session: Active SQLAlchemy async session.
        event_type: One of ``login_success``, ``login_failure``, ``logout``,
            ``password_reset``, or ``email_verify``.
        user_id: UUID of the user associated with the event, or ``None`` for
            failed attempts where the user was not found.
        ip_address: Remote IP extracted from the HTTP request, or ``None``.
        user_agent: ``User-Agent`` header value, or ``None``.
    """
    record = AuthAuditLogRecord(
        user_id=user_id,
        event_type=event_type,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(record)
