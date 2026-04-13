# Auth Audit Log

## Purpose

Specifies the `auth_audit_log` database table and the `record_auth_event` service function. Every significant authentication event — successful and failed login, logout, password reset, and email verification — SHALL be written as a timestamped, immutable row in this table. The log is write-only from the application in MU6; reading requires direct database access.

---

## Requirements

### Requirement: AuthAuditLogRecord model and table schema

`oscilla/models/auth_audit_log.py` SHALL define `AuthAuditLogRecord` as a SQLAlchemy declarative model with:

- `id: UUID` — primary key, default `uuid4`
- `user_id: UUID | None` — nullable foreign key to `users.id` with `ondelete="SET NULL"` so audit records survive user deletion
- `event_type: str` — not null; one of `"login_success"`, `"login_failure"`, `"logout"`, `"password_reset"`, `"email_verify"`
- `ip_address: str | None`
- `user_agent: str | None`
- `created_at: datetime` — default `datetime.now(UTC)`, indexed

The migration SHALL be compatible with both SQLite and PostgreSQL. No existing table is modified.

#### Scenario: audit record is created with required fields

- **GIVEN** a database session
- **WHEN** a `AuthAuditLogRecord(event_type="login_success", user_id=user.id)` is committed
- **THEN** querying by `id` returns the record with `event_type="login_success"` and a non-null `created_at`

#### Scenario: user deletion does not cascade-delete audit records

- **GIVEN** an `AuthAuditLogRecord` row with `user_id` set to a user's UUID
- **WHEN** the user row is deleted
- **THEN** the audit log row still exists and its `user_id` is `NULL`

---

### Requirement: `record_auth_event` is a session-bound service function

`oscilla/services/auth.py` SHALL export `async def record_auth_event(session: AsyncSession, event_type: str, user_id: UUID | None = None, ip_address: str | None = None, user_agent: str | None = None) -> None`. It SHALL construct an `AuthAuditLogRecord` and add it to the session without committing — the calling router controls the transaction boundary.

#### Scenario: record_auth_event adds a row without committing

- **GIVEN** an open async session with no pending changes
- **WHEN** `await record_auth_event(session, "login_success", user_id=some_uuid)` is called
- **THEN** the session has one pending new object (`session.new` contains an `AuthAuditLogRecord`)
- **AND** the `session.commit()` has NOT been called automatically

---

### Requirement: login endpoint writes login_success and login_failure events

The `POST /auth/login` endpoint SHALL call `record_auth_event` with:

- `event_type="login_success"` after successful authentication and `clear_lockout`, before returning the token pair
- `event_type="login_failure"` after a failed password check (user found but wrong password), before raising `HTTP 401`

Both writes SHALL include `ip_address` from `request.client.host` (or `None`) and `user_agent` from `request.headers.get("user-agent")`.

#### Scenario: successful login creates login_success row

- **GIVEN** a registered user
- **WHEN** the user submits correct credentials to `POST /auth/login`
- **THEN** one `AuthAuditLogRecord` with `event_type="login_success"` exists in the DB with the correct `user_id`

#### Scenario: failed login creates login_failure row

- **GIVEN** a registered user
- **WHEN** the user submits an incorrect password to `POST /auth/login`
- **THEN** one `AuthAuditLogRecord` with `event_type="login_failure"` exists in the DB

---

### Requirement: logout endpoint writes logout event

The `POST /auth/logout` endpoint SHALL call `record_auth_event` with `event_type="logout"` after revoking the refresh token.

The `user_id` for logout events SHALL be extracted by decoding the refresh token's associated user. If the token is invalid and `revoke_refresh_token` raises an exception, no audit record is written (the exception propagates normally).

#### Scenario: logout creates logout row

- **GIVEN** an authenticated user with a valid refresh token
- **WHEN** the user calls `POST /auth/logout` with the refresh token
- **THEN** one `AuthAuditLogRecord` with `event_type="logout"` exists in the DB

---

### Requirement: password reset endpoint writes password_reset event

The `POST /auth/password-reset/{token}` endpoint SHALL call `record_auth_event` with `event_type="password_reset"` and the resolved `user_id` after successfully updating `user.hashed_password`.

#### Scenario: password reset creates password_reset row

- **GIVEN** a valid password reset token for a user
- **WHEN** `POST /auth/password-reset/{token}` is called with a new password
- **THEN** one `AuthAuditLogRecord` with `event_type="password_reset"` and the correct `user_id` exists in the DB

---

### Requirement: email verification endpoint writes email_verify event

The `GET /auth/verify/{token}` endpoint SHALL call `record_auth_event` with `event_type="email_verify"` and the resolved `user_id` after setting `user.is_email_verified = True`.

#### Scenario: email verification creates email_verify row

- **GIVEN** a valid email verification token for an unverified user
- **WHEN** `GET /auth/verify/{token}` is called
- **THEN** one `AuthAuditLogRecord` with `event_type="email_verify"` and the correct `user_id` exists in the DB
