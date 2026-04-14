"""Tests verifying that auth events are written to the auth_audit_log table.

These tests use both `auth_client` (HTTP requests) and `db_session` (direct DB
queries) from the shared `db_session_maker` fixture so that router-written rows
are visible in the query session.
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oscilla.models.auth_audit_log import AuthAuditLogRecord
from oscilla.services.auth import make_verify_token


@pytest.mark.asyncio
async def test_successful_login_creates_login_success(auth_client: TestClient, db_session: AsyncSession) -> None:
    """Successful login writes a login_success row with the correct user_id."""
    email = "audit_login@example.com"
    auth_client.post("/api/auth/register", json={"email": email, "password": "securepass123"})
    resp = auth_client.post("/api/auth/login", json={"email": email, "password": "securepass123"})
    assert resp.status_code == 200
    me_resp = auth_client.get("/api/auth/me", headers={"Authorization": f"Bearer {resp.json()['access_token']}"})
    user_id = UUID(me_resp.json()["id"])

    rows = (
        (
            await db_session.execute(
                select(AuthAuditLogRecord).where(
                    AuthAuditLogRecord.event_type == "login_success",
                    AuthAuditLogRecord.user_id == user_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_failed_login_creates_login_failure(auth_client: TestClient, db_session: AsyncSession) -> None:
    """A failed login attempt writes a login_failure row."""
    email = "audit_fail@example.com"
    auth_client.post("/api/auth/register", json={"email": email, "password": "securepass123"})
    resp = auth_client.post("/api/auth/login", json={"email": email, "password": "wrongpassword"})
    assert resp.status_code == 401

    rows = (
        (
            await db_session.execute(
                select(AuthAuditLogRecord).where(
                    AuthAuditLogRecord.event_type == "login_failure",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) >= 1


@pytest.mark.asyncio
async def test_logout_creates_logout_event(auth_client: TestClient, db_session: AsyncSession) -> None:
    """Logging out writes a logout row for the authenticated user."""
    email = "audit_logout@example.com"
    auth_client.post("/api/auth/register", json={"email": email, "password": "securepass123"})
    login_resp = auth_client.post("/api/auth/login", json={"email": email, "password": "securepass123"})
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    logout_resp = auth_client.post("/api/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 204

    rows = (
        (
            await db_session.execute(
                select(AuthAuditLogRecord).where(
                    AuthAuditLogRecord.event_type == "logout",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_email_verify_creates_verify_event(auth_client: TestClient, db_session: AsyncSession) -> None:
    """Verifying an email token writes an email_verify row."""
    email = "audit_verify@example.com"
    auth_client.post("/api/auth/register", json={"email": email, "password": "securepass123"})
    login_resp = auth_client.post("/api/auth/login", json={"email": email, "password": "securepass123"})
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]
    me_resp = auth_client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    user_id = UUID(me_resp.json()["id"])

    token = make_verify_token(user_id=user_id)
    verify_resp = auth_client.get(f"/api/auth/verify/{token}")
    assert verify_resp.status_code == 204

    rows = (
        (
            await db_session.execute(
                select(AuthAuditLogRecord).where(
                    AuthAuditLogRecord.event_type == "email_verify",
                    AuthAuditLogRecord.user_id == user_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
