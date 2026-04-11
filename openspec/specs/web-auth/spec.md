# Web Auth

## Purpose

Specifies the password hashing, JWT access token, and itsdangerous email-token operations that make up the core of `oscilla/services/auth.py`. Also specifies the `get_current_user` and `get_verified_user` FastAPI dependencies and the 10-endpoint auth router.

---

## Requirements

### Requirement: Password hashing uses Argon2id

`hash_password(plaintext: str) -> str` SHALL return an Argon2id hash using `argon2.PasswordHasher()` with default parameters (memory=65536, time=3, parallelism=4 — the OWASP Password Storage Cheat Sheet recommendation).

`verify_password(hashed: str, plaintext: str) -> bool` SHALL return `True` when the plaintext matches the stored hash and `False` when it does not. It MUST catch `argon2.exceptions.VerifyMismatchError` and convert it to `False`. It MUST NOT raise any exception for a mismatch — only for unexpected errors such as corrupted hash format.

#### Scenario: Hash and verify round-trip succeeds

- **WHEN** `hash_password("correct-horse-battery-staple")` is called
- **THEN** the returned hash is a non-empty string beginning with `$argon2id$`
- **AND** `verify_password(hash, "correct-horse-battery-staple")` returns `True`

#### Scenario: verify_password returns False for wrong plaintext

- **WHEN** `verify_password(hash_password("hunter2"), "wrong")` is called
- **THEN** the result is `False` and no exception is raised

---

### Requirement: JWT access tokens encode only sub, iat, exp

`create_access_token(user_id: UUID) -> str` SHALL produce a JWT signed with HS256 using `settings.jwt_secret`. The payload MUST contain exactly three claims: `sub` (string form of the UUID), `iat` (current UTC timestamp), `exp` (UTC timestamp equal to `iat + settings.access_token_expire_minutes`).

`decode_access_token(token: str) -> UUID` SHALL decode and verify the JWT, returning the `sub` claim as a `UUID`. It MUST raise `fastapi.HTTPException(status_code=401)` on `jwt.exceptions.ExpiredSignatureError` or `jwt.exceptions.InvalidTokenError`. It MUST NOT return a user ID for an expired or tampered token.

#### Scenario: Access token round-trip returns original user id

- **GIVEN** a known `user_id = uuid4()`
- **WHEN** `token = create_access_token(user_id)` and `result = decode_access_token(token)`
- **THEN** `result == user_id`

#### Scenario: Expired access token raises HTTP 401

- **GIVEN** `settings.access_token_expire_minutes = -1` (or a token created with a past `exp`)
- **WHEN** `decode_access_token(token)` is called
- **THEN** `HTTPException` with `status_code=401` is raised

#### Scenario: Tampered access token raises HTTP 401

- **WHEN** `decode_access_token(token + "X")` is called with a structurally invalid token
- **THEN** `HTTPException` with `status_code=401` is raised

---

### Requirement: itsdangerous tokens carry user id with salt and expiry

`make_verify_token(user_id: UUID) -> str` SHALL produce a URL-safe signed token encoding `str(user_id)` with salt `"email-verify"`.

`make_reset_token(user_id: UUID) -> str` SHALL produce a URL-safe signed token encoding `str(user_id)` with salt `"password-reset"`.

`verify_email_token(token: str) -> UUID | None` SHALL verify the token against salt `"email-verify"` and `max_age = settings.email_verify_token_expire_hours * 3600`. It MUST return `None` on `itsdangerous.SignatureExpired` or `itsdangerous.BadSignature`. It MUST NOT confuse an email-verify token with a password-reset token (different salts prevent cross-use).

`verify_reset_token(token: str) -> UUID | None` SHALL verify the token against salt `"password-reset"` and `max_age = settings.password_reset_token_expire_hours * 3600`. Same `None`-on-error contract as `verify_email_token`.

#### Scenario: Email verification token round-trip returns original user id

- **GIVEN** a known `user_id = uuid4()`
- **WHEN** `token = make_verify_token(user_id)` and `result = verify_email_token(token)`
- **THEN** `result == user_id`

#### Scenario: Expired email verification token returns None

- **GIVEN** a token created with an expiry that has elapsed (monkeypatch `max_age=0`)
- **WHEN** `verify_email_token(token)` is called
- **THEN** the result is `None` and no exception is raised

#### Scenario: Password-reset token is rejected by verify_email_token

- **GIVEN** `token = make_reset_token(user_id)`
- **WHEN** `verify_email_token(token)` is called
- **THEN** the result is `None` (salt mismatch)

---

### Requirement: get_current_user dependency validates JWT and user state

`get_current_user` is an async FastAPI dependency that:

1. Extracts the Bearer token from the `Authorization` header via `OAuth2PasswordBearer`.
2. Calls `decode_access_token(token)` to obtain a `user_id`; propagates `HTTPException(401)` on failure.
3. Loads `UserRecord` from the database by `id`; raises `HTTPException(401)` if no row is found.
4. Raises `HTTPException(403)` if `user.is_active` is `False`.
5. Raises `HTTPException(status_code=403, detail="Email not verified.")` if `settings.require_email_verification` is `True` and `user.is_email_verified` is `False`.
6. Returns the `UserRecord`.

`get_verified_user` is an async FastAPI dependency that:

1. Calls `get_current_user` via `Depends`.
2. Raises `HTTPException(status_code=403, detail="Email not verified.")` if `user.is_email_verified` is `False`, regardless of the `require_email_verification` setting.
3. Returns the `UserRecord`.

#### Scenario: Valid token for active verified user returns UserRecord

- **GIVEN** a `UserRecord` with `is_active=True` and `is_email_verified=True`
- **AND** a valid JWT for that user
- **WHEN** `get_current_user` is invoked via the test client
- **THEN** the user is returned without error

#### Scenario: Valid token for inactive user raises HTTP 403

- **GIVEN** a `UserRecord` with `is_active=False`
- **AND** a valid JWT for that user
- **WHEN** `get_current_user` is invoked
- **THEN** `HTTPException(403)` is raised

#### Scenario: Missing or invalid token raises HTTP 401

- **WHEN** `get_current_user` is invoked with no `Authorization` header or with a malformed token
- **THEN** `HTTPException(401)` is raised

#### Scenario: require_email_verification=True blocks unverified user from get_current_user

- **GIVEN** `settings.require_email_verification = True`
- **AND** a `UserRecord` with `is_email_verified=False`
- **AND** a valid JWT for that user
- **WHEN** `get_current_user` is invoked
- **THEN** `HTTPException(403, detail="Email not verified.")` is raised

#### Scenario: require_email_verification=False allows unverified user through get_current_user

- **GIVEN** `settings.require_email_verification = False`
- **AND** a `UserRecord` with `is_email_verified=False`
- **AND** a valid JWT for that user
- **WHEN** `get_current_user` is invoked
- **THEN** the user is returned without error

#### Scenario: get_verified_user always blocks unverified user regardless of setting

- **GIVEN** `settings.require_email_verification = False`
- **AND** a `UserRecord` with `is_email_verified=False`
- **AND** a valid JWT for that user
- **WHEN** `get_verified_user` is invoked
- **THEN** `HTTPException(403, detail="Email not verified.")` is raised

---

### Requirement: Auth endpoints follow no-user-enumeration contract

`POST /auth/login` and `POST /auth/request-password-reset` MUST NOT reveal whether a given email address exists in the database.

- `POST /auth/login` SHALL return `HTTP 401` for both "email not found" and "wrong password" scenarios with the same generic error detail (e.g., `"Invalid credentials."`).
- `POST /auth/request-password-reset` SHALL always return `HTTP 204` regardless of whether the email exists. The email is sent only when a matching user is found, but from the caller's perspective the response is always `204`.

#### Scenario: Login with nonexistent email returns 401

- **WHEN** `POST /auth/login` is called with an email that has no matching UserRecord
- **THEN** `HTTP 401` is returned with a generic error message
- **AND** the response is indistinguishable from a wrong-password response

#### Scenario: Login with wrong password returns 401

- **GIVEN** a registered user with email `"user@example.com"` and password `"correct"`
- **WHEN** `POST /auth/login` is called with `email="user@example.com"` and `password="wrong"`
- **THEN** `HTTP 401` is returned with the same generic message as the nonexistent-email case

#### Scenario: Password reset request for nonexistent email returns 204

- **WHEN** `POST /auth/request-password-reset` is called with `email="nobody@example.com"`
- **THEN** `HTTP 204` is returned
- **AND** no email is sent

#### Scenario: Password reset request for existing email returns 204 and sends email

- **GIVEN** a registered user with `email="user@example.com"` and `is_email_verified=True`
- **WHEN** `POST /auth/request-password-reset` is called with `email="user@example.com"`
- **THEN** `HTTP 204` is returned
- **AND** `send_email` is called exactly once with the reset link

---

### Requirement: Registration rejects duplicate email

`POST /auth/register` SHALL return `HTTP 409 Conflict` when the submitted email already exists in the database. The response MUST NOT reveal the hashed password or any other sensitive field of the existing account.

#### Scenario: Duplicate email registration returns 409

- **GIVEN** a `UserRecord` already exists with `email="taken@example.com"`
- **WHEN** `POST /auth/register` is called with `email="taken@example.com"`
- **THEN** `HTTP 409` is returned
- **AND** no new row is inserted

---

### Requirement: PATCH /auth/me only updates provided fields

`PATCH /auth/me` MUST update only the fields present in the request body that are non-`None`. Fields omitted from the request body (defaulting to `None` for optional `UserUpdateRequest` fields) MUST NOT overwrite existing values.

#### Scenario: Updating display_name does not change password

- **GIVEN** a user with display_name `"Alice"` and a known password hash
- **WHEN** `PATCH /auth/me` is called with `{"display_name": "Bob"}`
- **THEN** `user.display_name == "Bob"`
- **AND** `user.hashed_password` is unchanged
