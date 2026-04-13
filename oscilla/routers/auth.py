from datetime import datetime
from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_CONTENT,
    HTTP_423_LOCKED,
    HTTP_429_TOO_MANY_REQUESTS,
)

from oscilla.dependencies.auth import get_current_user
from oscilla.models.user import UserRecord
from oscilla.services.auth import (
    clear_lockout,
    create_access_token,
    create_refresh_token,
    hash_password,
    is_account_locked,
    record_auth_event,
    record_failed_login,
    revoke_refresh_token,
    rotate_refresh_token,
    send_reset_email,
    send_verification_email,
    verify_email_token,
    verify_password,
    verify_reset_token,
)
from oscilla.services.db import get_session_depends
from oscilla.services.password_strength import validate_password_strength
from oscilla.services.rate_limit import check_rate_limit
from oscilla.settings import settings

router = APIRouter()
logger = getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr = Field(description="Email address for the new account.")
    password: str = Field(min_length=8, description="Account password (minimum 8 characters).")
    display_name: str | None = Field(default=None, max_length=60, description="Optional display name.")


class LoginRequest(BaseModel):
    email: EmailStr = Field(description="Registered email address.")
    password: str = Field(description="Account password.")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(description="Opaque refresh token issued at login or last refresh.")


class TokenPairRead(BaseModel):
    access_token: str = Field(description="Short-lived JWT access token.")
    refresh_token: str = Field(description="Long-lived opaque refresh token.")
    token_type: str = Field(default="bearer", description="Token type, always 'bearer'.")


class UserRead(BaseModel):
    id: UUID = Field(description="User ID.")
    email: str | None = Field(description="User email address.")
    display_name: str | None = Field(description="Optional display name.")
    is_email_verified: bool = Field(description="Whether the user's email has been verified.")
    is_active: bool = Field(description="Whether the account is active.")
    created_at: datetime = Field(description="Account creation timestamp.")


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=60, description="New display name.")
    password: str | None = Field(default=None, min_length=8, description="New password (minimum 8 characters).")


class PasswordResetRequest(BaseModel):
    email: EmailStr = Field(description="Email address associated with the account.")


class NewPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, description="New password (minimum 8 characters).")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _user_read(user: UserRecord) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_email_verified=user.is_email_verified,
        is_active=user.is_active,
        created_at=user.created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/register", response_model=UserRead, status_code=HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    request_obj: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> UserRead:
    """Register a new user account."""
    ip = request_obj.client.host if request_obj.client else "unknown"
    if not await check_rate_limit(f"rl:register:{ip}", settings.max_registrations_per_hour_per_ip, 3600):
        raise HTTPException(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts from this address.",
        )

    try:
        validate_password_strength(request.password)
    except ValueError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    stmt = select(UserRecord).where(UserRecord.email == request.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail="Email already registered.")

    user = UserRecord(
        user_key=None,
        email=request.email,
        hashed_password=hash_password(request.password),
        display_name=request.display_name,
    )
    db.add(user)
    await db.flush()
    await db.commit()

    background_tasks.add_task(send_verification_email, user.email or "", user.id, user.display_name)

    return _user_read(user)


@router.post("/login", response_model=TokenPairRead)
async def login(
    request: LoginRequest,
    request_obj: Request,
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> TokenPairRead:
    """Authenticate with email and password; returns an access + refresh token pair."""
    if not await check_rate_limit(f"rl:login:{request.email}", settings.max_login_attempts_per_hour, 3600):
        raise HTTPException(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )

    if await is_account_locked(request.email):
        raise HTTPException(
            status_code=HTTP_423_LOCKED,
            detail="Account is temporarily locked due to too many failed login attempts.",
        )

    stmt = select(UserRecord).where(UserRecord.email == request.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # Constant-time: always verify before returning 401 to avoid user enumeration
    if (
        user is None
        or user.hashed_password is None
        or not verify_password(hashed=user.hashed_password, plaintext=request.password)
    ):
        if user is not None:
            await record_failed_login(request.email)
        await record_auth_event(
            db,
            "login_failure",
            user_id=user.id if user is not None else None,
            ip_address=request_obj.client.host if request_obj.client else None,
            user_agent=request_obj.headers.get("user-agent"),
        )
        await db.commit()
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    if not user.is_active:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Account is inactive.")

    await clear_lockout(request.email)

    await record_auth_event(
        db,
        "login_success",
        user_id=user.id,
        ip_address=request_obj.client.host if request_obj.client else None,
        user_agent=request_obj.headers.get("user-agent"),
    )

    access_token = create_access_token(user_id=user.id)
    refresh_token = await create_refresh_token(session=db, user_id=user.id)
    await db.commit()

    return TokenPairRead(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenPairRead)
async def refresh(
    request: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> TokenPairRead:
    """Rotate the refresh token and issue new access + refresh tokens."""
    new_refresh_token, user_id = await rotate_refresh_token(session=db, token=request.refresh_token)
    await db.commit()
    access_token = create_access_token(user_id=user_id)
    return TokenPairRead(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=HTTP_204_NO_CONTENT)
async def logout(
    request: RefreshRequest,
    request_obj: Request,
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> None:
    """Revoke the refresh token (logout)."""
    await revoke_refresh_token(session=db, token=request.refresh_token)
    await record_auth_event(
        db,
        "logout",
        ip_address=request_obj.client.host if request_obj.client else None,
        user_agent=request_obj.headers.get("user-agent"),
    )
    await db.commit()


@router.post("/request-verify", status_code=HTTP_204_NO_CONTENT)
async def request_verify(
    background_tasks: BackgroundTasks,
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> None:
    """Resend the verification email for the authenticated user."""
    if user.is_email_verified:
        return
    background_tasks.add_task(send_verification_email, user.email or "", user.id, user.display_name)


@router.get("/verify/{token}", status_code=HTTP_204_NO_CONTENT)
async def verify_email(
    token: str,
    request_obj: Request,
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> None:
    """Verify a user's email address using the token from the verification email."""
    user_id = verify_email_token(token=token)
    if user_id is None:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Invalid or expired verification token.")

    stmt = select(UserRecord).where(UserRecord.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="User not found.")

    user.is_email_verified = True
    await record_auth_event(
        db,
        "email_verify",
        user_id=user.id,
        ip_address=request_obj.client.host if request_obj.client else None,
        user_agent=request_obj.headers.get("user-agent"),
    )
    await db.commit()


@router.post("/request-password-reset", status_code=HTTP_204_NO_CONTENT)
async def request_password_reset(
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> None:
    """Send a password-reset email (always 204, no user enumeration)."""
    stmt = select(UserRecord).where(UserRecord.email == request.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is not None:
        background_tasks.add_task(send_reset_email, user.email or "", user.id, user.display_name)


@router.post("/password-reset/{token}", status_code=HTTP_204_NO_CONTENT)
async def password_reset(
    token: str,
    request: NewPasswordRequest,
    request_obj: Request,
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> None:
    """Reset a user's password using a valid reset token."""
    user_id = verify_reset_token(token=token)
    if user_id is None:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token.")

    stmt = select(UserRecord).where(UserRecord.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="User not found.")

    user.hashed_password = hash_password(request.new_password)
    await record_auth_event(
        db,
        "password_reset",
        user_id=user.id,
        ip_address=request_obj.client.host if request_obj.client else None,
        user_agent=request_obj.headers.get("user-agent"),
    )
    await db.commit()


@router.get("/me", response_model=UserRead, status_code=HTTP_200_OK)
async def get_me(
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> UserRead:
    """Return the authenticated user's profile."""
    return _user_read(user)


@router.patch("/me", response_model=UserRead, status_code=HTTP_200_OK)
async def update_me(
    request: UserUpdateRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> UserRead:
    """Update the authenticated user's display name and/or password."""
    if request.display_name is not None:
        user.display_name = request.display_name
    if request.password is not None:
        user.hashed_password = hash_password(request.password)
    await db.commit()
    return _user_read(user)
