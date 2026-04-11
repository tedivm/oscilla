# Refresh Token Store

## Purpose

Specifies the opaque refresh token lifecycle: creation, rotation, and revocation. Refresh tokens are stored in the `auth_refresh_tokens` table as SHA-256 hashes. The plaintext token is issued to the client exactly once and never stored on the server.

---

## Requirements

### Requirement: create_refresh_token stores only the SHA-256 hash

`create_refresh_token(session: AsyncSession, user_id: UUID) -> str` SHALL:

1. Generate a `uuid4()` and stringify it as the plaintext token.
2. Compute `hashlib.sha256(plaintext.encode()).hexdigest()` as `token_hash`.
3. Insert a new `AuthRefreshTokenRecord` row with `user_id`, `token_hash`, `issued_at = utcnow`, `expires_at = utcnow + timedelta(days=settings.refresh_token_expire_days)`, and `revoked = False`.
4. Flush the session.
5. Return the plaintext UUID string.

The plaintext token MUST NOT be stored in the database at any point. A DB breach MUST NOT expose valid plaintext tokens.

#### Scenario: create_refresh_token inserts exactly one row and returns a non-empty string

- **GIVEN** a valid `user_id` and an open database session
- **WHEN** `token = await create_refresh_token(session, user_id)`
- **THEN** exactly one `AuthRefreshTokenRecord` row exists for `user_id`
- **AND** `token` is a non-empty string
- **AND** the stored `token_hash != token` (plaintext is not stored)
- **AND** `hashlib.sha256(token.encode()).hexdigest() == record.token_hash`

#### Scenario: refresh token expires at configured offset

- **GIVEN** `settings.refresh_token_expire_days = 30`
- **WHEN** `await create_refresh_token(session, user_id)` is called
- **THEN** `record.expires_at` is within one second of `utcnow + timedelta(days=30)`

---

### Requirement: rotate_refresh_token revokes the old token and issues a new one

`rotate_refresh_token(session: AsyncSession, token: str) -> str` SHALL:

1. Compute `token_hash = sha256(token)`.
2. Query `auth_refresh_tokens` for a row where `token_hash == token_hash AND revoked == False AND expires_at > utcnow`.
3. If no such row exists, raise `HTTPException(status_code=401)`.
4. Set `record.revoked = True` on the found row.
5. Call and return `create_refresh_token(session, record.user_id)`.

Token rotation means that each refresh token can only be used once. If a stolen token is replayed after the legitimate holder has already rotated it, the stolen token's row will already be revoked and the replay will receive `HTTP 401`.

#### Scenario: Rotating a valid token issues a new token and revokes the old one

- **GIVEN** a token returned by `create_refresh_token`
- **WHEN** `new_token = await rotate_refresh_token(session, token)`
- **THEN** `new_token != token`
- **AND** the original `AuthRefreshTokenRecord` has `revoked == True`
- **AND** a new `AuthRefreshTokenRecord` exists for the same `user_id` with `revoked == False`

#### Scenario: Rotating a revoked token raises HTTP 401

- **GIVEN** a token that has already been rotated (its row has `revoked == True`)
- **WHEN** `await rotate_refresh_token(session, token)` is called
- **THEN** `HTTPException(status_code=401)` is raised
- **AND** no new token row is inserted

#### Scenario: Rotating an expired token raises HTTP 401

- **GIVEN** a token whose `AuthRefreshTokenRecord.expires_at` is in the past
- **WHEN** `await rotate_refresh_token(session, token)` is called
- **THEN** `HTTPException(status_code=401)` is raised

#### Scenario: Rotating a non-existent token raises HTTP 401

- **WHEN** `await rotate_refresh_token(session, "completely-made-up")` is called
- **THEN** `HTTPException(status_code=401)` is raised

---

### Requirement: revoke_refresh_token is idempotent

`revoke_refresh_token(session: AsyncSession, token: str) -> None` SHALL:

1. Compute `token_hash = sha256(token)`.
2. Query for the row; if found, set `revoked = True`.
3. If no row is found, return silently without error.

This function MUST NOT raise an exception for an unknown or already-revoked token. Logout MUST be idempotent: calling it twice with the same token is safe.

#### Scenario: Revoking a valid token marks it revoked

- **GIVEN** a token returned by `create_refresh_token`
- **WHEN** `await revoke_refresh_token(session, token)`
- **THEN** `record.revoked == True`

#### Scenario: Revoking an already-revoked token completes without error

- **GIVEN** a token whose `AuthRefreshTokenRecord.revoked == True`
- **WHEN** `await revoke_refresh_token(session, token)` is called
- **THEN** no exception is raised
- **AND** the row remains `revoked == True`

#### Scenario: Revoking a non-existent token completes without error

- **WHEN** `await revoke_refresh_token(session, "unknown-token")` is called
- **THEN** no exception is raised

---

### Requirement: AuthRefreshTokenRecord schema safety

The `auth_refresh_tokens` table SHALL have:

- A unique index on `token_hash` — duplicate hashes must be rejected at the database level, not just the application level.
- A foreign key from `user_id` to `users.id` — orphaned token rows must be prevented by the schema.
- `revoked` column defaulting to `False` at the database level (`server_default`) so rows created outside SQLAlchemy ORM (e.g., test fixtures, manual SQL) are also safe.

#### Scenario: Duplicate token_hash is rejected at the DB level

- **WHEN** two `AuthRefreshTokenRecord` rows are inserted with the same `token_hash`
- **THEN** the database raises an integrity error before the second row is committed
