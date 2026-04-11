## 1. Dependencies

- [ ] 1.1 Add `PyJWT`, `argon2-cffi`, `itsdangerous`, `aiosmtplib`, and `email-validator` to the project dependencies in `pyproject.toml` via `uv add`; verify `uv lock` succeeds and `make pytest` still passes after the lockfile update

## 2. Settings

- [ ] 2.1 Add the following fields to the `Settings` class in `oscilla/conf/settings.py` under a `# Auth` comment block: `jwt_secret: SecretStr` (required, no default — missing variable causes startup failure), `access_token_expire_minutes: int = Field(default=15, ...)`, `refresh_token_expire_days: int = Field(default=30, ...)`, `email_verify_token_expire_hours: int = Field(default=24, ...)`, `password_reset_token_expire_hours: int = Field(default=1, ...)`; all with `description=` values as specified in `design.md`
- [ ] 2.2 Add `require_email_verification: bool = Field(default=False, ...)` to `Settings` under the same auth block
- [ ] 2.3 Add the following fields to `Settings` under a `# SMTP` comment block: `smtp_host: str | None = Field(default=None, ...)`, `smtp_port: int = Field(default=587, ...)`, `smtp_user: str | None = Field(default=None, ...)`, `smtp_password: SecretStr | None = Field(default=None, ...)`, `smtp_from_address: str | None = Field(default=None, ...)`, `smtp_use_tls: bool = Field(default=True, ...)`; all with `description=` values as specified in `design.md`
- [ ] 2.4 Add `JWT_SECRET=change-me-in-production-this-must-be-long-and-random`, `REQUIRE_EMAIL_VERIFICATION=false`, `SMTP_HOST=localhost`, `SMTP_PORT=1025`, `SMTP_USE_TLS=false`, and `SMTP_FROM_ADDRESS=oscilla@localhost` to `.env.example` in a new `# Auth & SMTP` section with inline comments explaining each variable; verify `make tomlsort_check` and `make dapperdata_check` still pass

## 3. UserRecord Migration

- [ ] 3.1 Run `make create_migration MESSAGE="extend userrecord with web auth columns"` to scaffold an Alembic migration; in the generated file under `db/versions/`, implement `upgrade()` to: (a) `op.alter_column("users", "user_key", nullable=True)`, (b) `op.add_column("users", sa.Column("email", sa.String(), unique=True, nullable=True))`, (c) `op.add_column("users", sa.Column("hashed_password", sa.String(), nullable=True))`, (d) `op.add_column("users", sa.Column("display_name", sa.String(), nullable=True))`, (e) `op.add_column("users", sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default="0"))`, (f) `op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"))`, (g) `op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))`; implement `downgrade()` to reverse each step in reverse order
- [ ] 3.2 Update `UserRecord` in `oscilla/models/user.py` to match the extended schema exactly as shown in `design.md`: change `user_key` to `Mapped[str | None]` with `nullable=True`; add `email`, `hashed_password`, `display_name`, `is_email_verified` (default `False`), `is_active` (default `True`), and `updated_at` columns; add the `onupdate` lambda to `updated_at`
- [ ] 3.3 Run `make check_ungenerated_migrations` and confirm zero ungenerated migrations; run `make document_schema` to update the schema documentation

## 4. AuthRefreshTokenRecord

- [ ] 4.1 Create `oscilla/models/auth.py` with the `AuthRefreshTokenRecord` class exactly as specified in `design.md`: table `auth_refresh_tokens`, columns `id` (UUID PK), `user_id` (UUID FK → `users.id`), `token_hash` (String, unique, not null), `issued_at` (DateTime TZ, not null), `expires_at` (DateTime TZ, not null), `revoked` (Boolean, not null, default `False`); include the docstring explaining that only the SHA-256 hash is stored
- [ ] 4.2 Import `AuthRefreshTokenRecord` in `oscilla/models/__init__.py` (or whichever aggregation module exists) so Alembic's autogenerate picks it up
- [ ] 4.3 Run `make create_migration MESSAGE="add auth refresh tokens table"` and confirm the generated migration creates `auth_refresh_tokens` with a unique index on `token_hash` and a foreign key to `users`; run `make check_ungenerated_migrations` to confirm clean state

## 5. Email Service

- [ ] 5.1 Create `oscilla/services/email.py` with: (a) an `EmailDeliveryError` exception class at module scope, (b) an `async def send_email(to: str, subject: str, body_html: str, body_text: str) -> None` function that reads `smtp_host` from settings — if `smtp_host` is `None`, logs a DEBUG message and returns immediately (graceful no-op); otherwise opens an `aiosmtplib.SMTP` connection with `hostname`, `port`, `start_tls`, and optional `username`/`password` (from `smtp_user`/`smtp_password.get_secret_value()`) and sends a `MIME Multipart` message with both HTML and plain-text parts; wraps the SMTP call in `try/except` and re-raises as `EmailDeliveryError` on failure; uses `module logger` at the top of the file
- [ ] 5.2 Add unit tests in `tests/services/test_email.py`: (a) when `smtp_host` is `None`, `send_email` completes without error and no SMTP call is made (use monkeypatch to confirm `aiosmtplib.SMTP` is never instantiated); (b) when `smtp_host` is set, `send_email` invokes the SMTP client with the correct arguments (monkeypatch `aiosmtplib.SMTP`); (c) when the SMTP client raises an exception, `send_email` raises `EmailDeliveryError`

## 6. Auth Service

- [ ] 6.1 Create `oscilla/services/auth.py` with module-level `_ph = PasswordHasher()` (from `argon2`), module-level `_s = URLSafeTimedSerializer(settings.jwt_secret.get_secret_value())` (from `itsdangerous`), and implement the following functions exactly as the spec describes:
  - `hash_password(plaintext: str) -> str` — returns `_ph.hash(plaintext)`
  - `verify_password(hashed: str, plaintext: str) -> bool` — calls `_ph.verify(hashed, plaintext)`, catches `VerifyMismatchError`, returns `False` on mismatch
- [ ] 6.2 Implement `create_access_token(user_id: UUID) -> str` in `oscilla/services/auth.py`: builds payload `{"sub": str(user_id), "iat": utcnow, "exp": utcnow + timedelta(minutes=settings.access_token_expire_minutes)}` and returns `jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")`
- [ ] 6.3 Implement `decode_access_token(token: str) -> UUID` in `oscilla/services/auth.py`: calls `jwt.decode(token, secret, algorithms=["HS256"])`; raises `HTTPException(status_code=401)` on `ExpiredSignatureError` or `InvalidTokenError`; returns `UUID(payload["sub"])`
- [ ] 6.4 Implement `async def create_refresh_token(session: AsyncSession, user_id: UUID) -> str` in `oscilla/services/auth.py`: generates a `uuid4()` plaintext token, computes its SHA-256 hex digest, creates an `AuthRefreshTokenRecord` with `user_id`, `token_hash`, and `expires_at = utcnow + timedelta(days=settings.refresh_token_expire_days)`, adds and flushes to the session, returns the plaintext UUID as a string
- [ ] 6.5 Implement `async def rotate_refresh_token(session: AsyncSession, token: str) -> str` in `oscilla/services/auth.py`: computes SHA-256 digest of `token`, queries `auth_refresh_tokens` for a row with matching `token_hash` where `revoked=False` and `expires_at > utcnow`; raises `HTTPException(status_code=401)` if not found; sets `record.revoked = True`; calls and returns `create_refresh_token(session, record.user_id)`
- [ ] 6.6 Implement `async def revoke_refresh_token(session: AsyncSession, token: str) -> None` in `oscilla/services/auth.py`: computes SHA-256 digest, queries for the row, sets `revoked = True` if found; no error if not found (idempotent logout)
- [ ] 6.7 Implement `make_verify_token(user_id: UUID) -> str`, `make_reset_token(user_id: UUID) -> str`, `verify_email_token(token: str) -> UUID | None`, and `verify_reset_token(token: str) -> UUID | None` in `oscilla/services/auth.py` using `_s.dumps`/`_s.loads` with salts `"email-verify"` and `"password-reset"` and `max_age` derived from `settings.email_verify_token_expire_hours` and `settings.password_reset_token_expire_hours` respectively; catch `SignatureExpired` and `BadSignature` and return `None`
- [ ] 6.8 Add unit tests in `tests/services/test_auth.py`: (a) `hash_password` / `verify_password` round-trip returns `True`; (b) `verify_password` with wrong plaintext returns `False`; (c) `create_access_token` / `decode_access_token` round-trip returns original `user_id`; (d) `decode_access_token` with expired token raises `HTTPException(401)`; (e) `decode_access_token` with tampered token raises `HTTPException(401)`; (f) `make_verify_token` / `verify_email_token` round-trip returns original `user_id`; (g) `verify_email_token` with expired token returns `None`; (h) `make_reset_token` / `verify_reset_token` round-trip returns original `user_id`; (i) `create_refresh_token` inserts a row and returns a non-empty string; (j) `rotate_refresh_token` revokes the old row and returns a new token; (k) `rotate_refresh_token` with a revoked token raises `HTTPException(401)`; (l) `revoke_refresh_token` is idempotent when called twice

## 7. FastAPI Dependencies

- [ ] 7.1 Create `oscilla/dependencies/__init__.py` (empty) and `oscilla/dependencies/auth.py` with: an `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")` instance; `async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[AsyncSession, Depends(get_db)]) -> UserRecord` that calls `decode_access_token(token)`, loads the user by `id`, raises `HTTP 401` if not found, raises `HTTP 403` if `not user.is_active`, raises `HTTP 403` (detail: `"Email not verified."`) if `settings.require_email_verification and not user.is_email_verified`, and returns the user; `async def get_verified_user(user: Annotated[UserRecord, Depends(get_current_user)]) -> UserRecord` that always enforces `is_email_verified` check (raises `HTTP 403` if not verified), regardless of settings
- [ ] 7.2 Add unit tests in `tests/dependencies/test_auth.py` (create `tests/dependencies/__init__.py` too): (a) valid token for active verified user returns `UserRecord`; (b) valid token for inactive user raises `HTTP 403`; (c) invalid token raises `HTTP 401`; (d) `get_current_user` with `require_email_verification=True` and unverified user raises `HTTP 403`; (e) `get_current_user` with `require_email_verification=False` and unverified user returns the user; (f) `get_verified_user` with unverified user always raises `HTTP 403`

## 8. Auth Router

- [ ] 8.1 Create `oscilla/routers/__init__.py` (empty, if it does not already exist) and `oscilla/routers/auth.py` with all Pydantic request/response models specified in `design.md`: `RegisterRequest` (email: `EmailStr`, password: `str` min_length=8, display_name: `str | None` max_length=60); `LoginRequest`; `RefreshRequest`; `TokenPairRead`; `UserRead` (id, email, display_name, is_email_verified, is_active, created_at); `UserUpdateRequest`; `PasswordResetRequest`; `NewPasswordRequest`; each `Field` with validation constraints and a `description=` value
- [ ] 8.2 Implement `POST /auth/register` in `oscilla/routers/auth.py`: queries the DB for an existing user with the same email; if found, raises `HTTP 409 Conflict`; creates `UserRecord` with hashed password; adds and flushes; if `smtp_host` is set, sends a verification email using `make_verify_token` and `send_email` (fire-and-forget in a background task to avoid blocking the response); returns `201 Created` with `UserRead`
- [ ] 8.3 Implement `POST /auth/login`: loads user by email; if not found or `verify_password` fails, raises `HTTP 401` with a generic message (no user enumeration); if `not user.is_active`, raises `HTTP 403`; calls `create_access_token` and `create_refresh_token`; returns `TokenPairRead`
- [ ] 8.4 Implement `POST /auth/refresh`: calls `rotate_refresh_token`; if that raises `HTTP 401`, propagates; returns new `TokenPairRead` with a new access token for the same user (load user by `user_id` from the rotated token record)
- [ ] 8.5 Implement `POST /auth/logout`: calls `revoke_refresh_token`; returns `204 No Content`
- [ ] 8.6 Implement `POST /auth/request-verify` (requires `get_current_user`): if `user.is_email_verified` already, returns `204` immediately; otherwise sends a verification email via background task; always returns `204`
- [ ] 8.7 Implement `GET /auth/verify/{token}`: calls `verify_email_token(token)`; if `None`, raises `HTTP 400`; loads the user, sets `is_email_verified = True`, commits; returns `204`
- [ ] 8.8 Implement `POST /auth/request-password-reset`: looks up user by email; if found, sends reset email via background task; always returns `204` (no user enumeration)
- [ ] 8.9 Implement `POST /auth/password-reset/{token}`: calls `verify_reset_token(token)`; if `None`, raises `HTTP 400`; loads user, calls `hash_password(request.new_password)`, sets `user.hashed_password`, commits; returns `204`
- [ ] 8.10 Implement `GET /auth/me` (requires `get_current_user`): returns `UserRead` for the authenticated user
- [ ] 8.11 Implement `PATCH /auth/me` (requires `get_current_user`): if `request.display_name` is set, update `user.display_name`; if `request.password` is set, update `user.hashed_password = hash_password(request.password)`; commits; returns `UserRead`

## 9. App Integration

- [ ] 9.1 Import the auth router in `oscilla/www.py` and call `app.include_router(auth_router, prefix="/auth", tags=["auth"])` after the existing static mount; verify that `GET /auth/me` (unauthenticated) returns `401` when the app is run

## 10. Email Templates

- [ ] 10.1 Create `oscilla/templates/email/verification.html` — a minimal HTML email template (no external CSS frameworks, inline styles only) with subject "Verify your Oscilla account", a greeting using `{{ display_name }}`, an `<a href="{{ action_url }}">Verify email</a>` link, and "This link expires in {{ expiry_description }}." footer text
- [ ] 10.2 Create `oscilla/templates/email/verification.txt` — plain-text counterpart to `verification.html` with the same content and `{{ action_url }}` on its own line
- [ ] 10.3 Create `oscilla/templates/email/password_reset.html` — same structure as `verification.html` but with subject "Reset your Oscilla password" and `<a href="{{ action_url }}">Reset password</a>` link
- [ ] 10.4 Create `oscilla/templates/email/password_reset.txt` — plain-text counterpart to `password_reset.html`
- [ ] 10.5 Update `services/auth.py` to render both templates using the existing `services/jinja.py` infrastructure before calling `send_email`; pass `display_name` (or `"there"` as fallback when `None`), `action_url` (constructed from the token), and `expiry_description` (e.g., `"24 hours"`)

## 11. Development Setup

- [ ] 11.1 Add the following service to `compose.yaml` so developers can intercept outbound email locally:

  ```yaml
  mailhog:
    image: mailhog/mailhog
    ports:
      - "8025:8025"
      - "1025:1025"
  ```

  Verify `docker compose up -d` succeeds and the MailHog UI is accessible at `http://localhost:8025`

- [ ] 11.2 Update `docs/dev/docker.md` to document the MailHog service: port mappings, how to access the web UI, and how to point the application at MailHog using the `.env.example` SMTP settings

## 12. Tests

- [ ] 12.1 Add an `auth_client` fixture to `tests/conftest.py` that creates an `AsyncClient` (or `TestClient`) backed by the test FastAPI app with the test database session override injected; monkeypatches `oscilla.services.email.send_email` to a no-op async coroutine that records calls in a list for assertions
- [ ] 12.2 Create `tests/routers/__init__.py` and `tests/routers/test_auth.py` with integration tests using the `auth_client` fixture: (a) `POST /auth/register` happy path — creates user, returns `201` with `UserRead`; (b) duplicate email registration returns `409`; (c) `POST /auth/login` with correct credentials returns `TokenPairRead`; (d) `POST /auth/login` with wrong password returns `401`; (e) `POST /auth/refresh` with valid refresh token returns new `TokenPairRead`; (f) `POST /auth/refresh` with revoked token returns `401`; (g) `POST /auth/logout` revokes refresh token; subsequent refresh attempt returns `401`; (h) `GET /auth/verify/{token}` with valid token sets `is_email_verified=True`; (i) `GET /auth/verify/{token}` with invalid token returns `400`; (j) `POST /auth/request-password-reset` always returns `204` regardless of whether email exists; (k) `POST /auth/password-reset/{token}` updates password; (l) `GET /auth/me` with valid token returns user; (m) `GET /auth/me` with no token returns `401`; (n) `PATCH /auth/me` updates display_name and password correctly
- [ ] 12.3 Run `make tests` and ensure all checks (pytest, ruff, black, mypy, dapperdata, tomlsort) pass with zero errors

## 13. Documentation

- [ ] 13.1 Create `docs/dev/authentication.md` covering: JWT access token lifecycle (15-minute expiry, payload fields), opaque refresh token rotation and revocation model, itsdangerous token usage for email verify and password reset, `get_current_user` and `get_verified_user` dependency usage guide, `require_email_verification` setting behavior, all new settings with types and defaults, local SMTP setup with MailHog (start command, `.env` snippet, MailHog UI URL)
- [ ] 13.2 Update `docs/dev/api.md` to add an "Authentication" section documenting all 10 `/auth` endpoints: request/response schemas, relevant error codes (`400`, `401`, `403`, `409`), and token lifetime notes
- [ ] 13.3 Add `authentication.md` to the table of contents in `docs/dev/README.md`
