"""Integration tests for the /auth router.

These tests exercise the full HTTP request/response cycle using a TestClient
backed by an in-memory (file SQLite) test database with the email service
patched to a no-op via the ``auth_client`` fixture.
"""

from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from oscilla.services.auth import make_reset_token, make_verify_token

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_register_success(auth_client: TestClient) -> None:
    """POST /auth/register with valid data returns 201 and a UserRead body."""
    response = auth_client.post(
        "/auth/register",
        json={"email": "newuser@example.com", "password": "securepass123", "display_name": "New User"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newuser@example.com"
    assert body["display_name"] == "New User"
    assert body["is_email_verified"] is False
    assert body["is_active"] is True
    assert UUID(body["id"])


def test_register_duplicate_email(auth_client: TestClient) -> None:
    """POST /auth/register with an already-registered email returns 409."""
    payload = {"email": "dup@example.com", "password": "securepass123"}
    auth_client.post("/auth/register", json=payload)
    response = auth_client.post("/auth/register", json=payload)
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def test_login_success(auth_client: TestClient) -> None:
    """POST /auth/login with valid credentials returns access + refresh tokens."""
    auth_client.post(
        "/auth/register",
        json={"email": "login@example.com", "password": "mypassword1"},
    )
    response = auth_client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "mypassword1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password(auth_client: TestClient) -> None:
    """POST /auth/login with incorrect password returns 401."""
    auth_client.post(
        "/auth/register",
        json={"email": "wrong@example.com", "password": "correctpass1"},
    )
    response = auth_client.post(
        "/auth/login",
        json={"email": "wrong@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_login_unknown_email(auth_client: TestClient) -> None:
    """POST /auth/login with an email that does not exist returns 401."""
    response = auth_client.post(
        "/auth/login",
        json={"email": "noone@example.com", "password": "somepassword"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Refresh & logout
# ---------------------------------------------------------------------------


def _register_and_login(client: TestClient, email: str, password: str = "password123") -> dict[str, Any]:
    client.post("/auth/register", json={"email": email, "password": password})
    resp = client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()


def test_refresh_success(auth_client: TestClient) -> None:
    """POST /auth/refresh returns a new token pair and invalidates the old refresh token."""
    tokens = _register_and_login(auth_client, "refresh@example.com")
    response = auth_client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    # Old token must now be invalid
    second = auth_client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert second.status_code == 401


def test_refresh_invalid_token(auth_client: TestClient) -> None:
    """POST /auth/refresh with a bogus token returns 401."""
    response = auth_client.post("/auth/refresh", json={"refresh_token": "notavalidtoken"})
    assert response.status_code == 401


def test_logout(auth_client: TestClient) -> None:
    """POST /auth/logout revokes the refresh token and returns 204."""
    tokens = _register_and_login(auth_client, "logout@example.com")
    response = auth_client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 204
    # Revoked token can no longer be refreshed
    second = auth_client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert second.status_code == 401


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


def test_verify_email_success(auth_client: TestClient) -> None:
    """GET /auth/verify/{token} marks the user's email as verified."""
    auth_client.post(
        "/auth/register",
        json={"email": "verify@example.com", "password": "password123"},
    )
    # Retrieve user_id from /me using an access token
    tokens = _register_and_login(auth_client, "verify@example.com")
    me_resp = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me_resp.status_code == 200
    user_id = UUID(me_resp.json()["id"])

    token = make_verify_token(user_id=user_id)
    response = auth_client.get(f"/auth/verify/{token}")
    assert response.status_code == 204

    # Confirm is_email_verified is now True
    me_after = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me_after.json()["is_email_verified"] is True


def test_verify_email_bad_token(auth_client: TestClient) -> None:
    """GET /auth/verify/{token} with an invalid token returns 400."""
    response = auth_client.get("/auth/verify/notavalidtoken")
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


def test_request_password_reset_no_enumeration(auth_client: TestClient) -> None:
    """POST /auth/request-password-reset always returns 204 (no user enumeration)."""
    response = auth_client.post("/auth/request-password-reset", json={"email": "ghost@example.com"})
    assert response.status_code == 204


def test_password_reset_success(auth_client: TestClient) -> None:
    """POST /auth/password-reset/{token} updates the password."""
    email = "resetme@example.com"
    old_pw = "oldpassword1"
    new_pw = "newpassword1"
    auth_client.post("/auth/register", json={"email": email, "password": old_pw})
    tokens = _register_and_login(auth_client, email, old_pw)
    user_id = UUID(
        auth_client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}).json()["id"]
    )

    token = make_reset_token(user_id=user_id)
    response = auth_client.post(f"/auth/password-reset/{token}", json={"new_password": new_pw})
    assert response.status_code == 204

    # Should now be able to log in with the new password
    login_resp = auth_client.post("/auth/login", json={"email": email, "password": new_pw})
    assert login_resp.status_code == 200


def test_password_reset_bad_token(auth_client: TestClient) -> None:
    """POST /auth/password-reset/{token} with an invalid token returns 400."""
    response = auth_client.post("/auth/password-reset/notavalidtoken", json={"new_password": "newpassword1"})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# /me endpoints
# ---------------------------------------------------------------------------


def test_get_me(auth_client: TestClient) -> None:
    """GET /auth/me returns the authenticated user's profile."""
    auth_client.post("/auth/register", json={"email": "me@example.com", "password": "password123"})
    tokens = _register_and_login(auth_client, "me@example.com")
    response = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


def test_get_me_unauthenticated(auth_client: TestClient) -> None:
    """GET /auth/me without a token returns 401."""
    response = auth_client.get("/auth/me")
    assert response.status_code == 401


def test_update_me(auth_client: TestClient) -> None:
    """PATCH /auth/me updates display name and optionally password."""
    auth_client.post(
        "/auth/register",
        json={"email": "patchme@example.com", "password": "password123", "display_name": "Old Name"},
    )
    tokens = _register_and_login(auth_client, "patchme@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = auth_client.patch("/auth/me", headers=headers, json={"display_name": "New Name"})
    assert response.status_code == 200
    assert response.json()["display_name"] == "New Name"


def test_request_password_reset_existing_email_sends_email(auth_client: TestClient) -> None:
    """POST /auth/request-password-reset for an existing user returns 204 and sends an email."""
    email = "resetexist@example.com"
    auth_client.post("/auth/register", json={"email": email, "password": "password123"})

    auth_client.sent_emails.clear()  # type: ignore[attr-defined]
    response = auth_client.post("/auth/request-password-reset", json={"email": email})

    assert response.status_code == 204
    assert len(auth_client.sent_emails) == 1  # type: ignore[attr-defined]
    assert auth_client.sent_emails[0]["to"] == email  # type: ignore[attr-defined]
