# Design: MU1 — Auth & User Accounts

## Context

The existing `UserRecord` model (in `oscilla/models/user.py`) has three columns: `id`, `user_key`, and `created_at`. The `user_key` is a machine-derived string (e.g., `"alice@hostname"`) used by the TUI to associate game state with a local identity. There is no password, no email, and no concept of remote authentication.

This change extends `UserRecord` with nullable web-auth columns and introduces the full authentication stack: JWT access tokens, Argon2id password hashing, itsdangerous email tokens, an async email service, and a `get_current_user` FastAPI dependency. The TUI code path (`get_or_create_user(user_key=...)`) is untouched; new columns are nullable so all existing TUI rows remain valid without a data migration.

The authentication service and the email service are deliberately separated. `services/auth.py` handles token operations, credential verification, and account state. `services/email.py` is a general-purpose async email dispatcher — auth uses it, but so can any future feature (game event notifications, subscription alerts, etc.) without importing auth logic.

---

## Goals / Non-Goals

**Goals:**

- `UserRecord` extended with auth fields; all new columns nullable; TUI rows remain valid.
- `auth_refresh_tokens` table: opaque long-lived tokens with rotation and revocation.
- `services/auth.py`: JWT encode/decode (PyJWT), Argon2id hash/verify (argon2-cffi), itsdangerous HMAC email tokens.
- `services/email.py`: standalone async email dispatch (aiosmtplib); no auth coupling.
- Auth router: 10 endpoints covering registration, login, token refresh, logout, email verification, password reset, and account self-management.
- `get_current_user` FastAPI dependency: validates JWT, returns `UserRecord`, raises `401` for invalid/expired tokens.
- `require_email_verification` setting (default `False`): when `True`, unverified accounts receive a `403` from the `get_current_user` dependency.
- MailHog added to `compose.yaml` for local SMTP interception during development.
- All new settings defined with Pydantic `Field` descriptions and placed in `oscilla/conf/settings.py`.

**Non-Goals:**

- OAuth2 / social login — the schema does not preclude adding it later but it is not implemented here.
- Admin account management (user ban/deactivate) — deferred to a future change.
- Rate limiting — deferred to MU6 (Production Hardening).
- Account lockout — deferred to MU6.
- TUI changes of any kind — TUI identity path is untouched.

---

## Decisions

### D1: argon2-cffi for password hashing (not passlib)

**Decision:** Use `argon2-cffi` directly for Argon2id password hashing and verification.

`passlib` has been unmaintained for approximately six years. It does not support Python 3.12+ cleanly and its `argon2` backend is a thin wrapper over `argon2-cffi` anyway. Using `argon2-cffi` directly removes the indirection and eliminates the dead-library dependency.

The API is simple:

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()  # default parameters are Argon2id, memory=65536, time=3, parallelism=4

def hash_password(plaintext: str) -> str:
    return _ph.hash(plaintext)

def verify_password(hashed: str, plaintext: str) -> bool:
    try:
        return _ph.verify(hashed, plaintext)
    except VerifyMismatchError:
        return False
```

`PasswordHasher()` with default parameters uses Argon2id with the parameters recommended by the OWASP Password Storage Cheat Sheet. These can be overridden via settings if hardware constraints require it.

**Alternatives considered:**

- `passlib[bcrypt]` — rejected: unmaintained. BCrypt also has a 72-byte password truncation vulnerability; Argon2id has no such limit.
- `bcrypt` directly — rejected: Argon2id is the current OWASP recommendation and winner of the Password Hashing Competition.

---

### D2: JWT access tokens (short-lived) + opaque refresh tokens (DB-backed)

**Decision:** Access tokens are JWTs with a 15-minute expiry. Refresh tokens are opaque UUIDs stored as SHA-256 hashes in `auth_refresh_tokens`. The plaintext token is sent to the client once and never stored on the server.

This model has two properties:

1. **Revocability:** Refresh tokens can be revoked by deleting (or flagging) their row. Access tokens cannot be revoked mid-lifetime — the 15-minute window is the tradeoff for stateless validation.
2. **Rotation:** Each call to `POST /auth/refresh` issues a new refresh token and revokes the old one. If a stolen token is used, the original holder's next refresh will fail (the old token is revoked), producing a detectable conflict.

The JWT payload contains: `sub` (user UUID as string), `exp` (expiry), `iat` (issued at). No other claims. The `get_current_user` dependency validates signature, expiry, and then loads the `UserRecord` by `sub`.

```python
# Access token payload
{"sub": str(user.id), "exp": ..., "iat": ...}
```

**Alternatives considered:**

- Fully opaque access tokens (DB-backed, stateful) — increases per-request DB load for all authenticated endpoints, with no benefit that the 15-minute access token window does not already provide.
- Refresh tokens stored plaintext — rejected for security; SHA-256 hash means a DB breach does not expose tokens.

---

### D3: itsdangerous for email verification and password reset tokens

**Decision:** Email verification and password reset use `itsdangerous.URLSafeTimedSerializer` to generate and verify short-lived HMAC tokens. No extra DB table is required beyond `auth_refresh_tokens`.

The serializer signs `user.id` (as string) with `jwt_secret` and a salt differentiating the two token types:

```python
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

_s = URLSafeTimedSerializer(secret_key)

def make_verify_token(user_id: UUID) -> str:
    return _s.dumps(str(user_id), salt="email-verify")

def make_reset_token(user_id: UUID) -> str:
    return _s.dumps(str(user_id), salt="password-reset")

def verify_token(token: str, salt: str, max_age_seconds: int) -> UUID | None:
    try:
        raw = _s.loads(token, salt=salt, max_age=max_age_seconds)
        return UUID(raw)
    except (SignatureExpired, BadSignature):
        return None
```

Token expiry defaults: 24 hours for email verification, 1 hour for password reset. Both are configurable via settings.

**Alternatives considered:**

- DB-backed one-time tokens — unnecessary complexity when itsdangerous already provides time-limited, tamper-evident tokens that do not require cleanup jobs.

---

### D4: `services/email.py` is standalone — not part of `services/auth.py`

**Decision:** Email sending lives in `oscilla/services/email.py` as an independent service. `services/auth.py` imports and calls it for verification and reset emails.

Auth service responsibilities: credential management, token operations, account state.
Email service responsibilities: compose and send transactional email via SMTP.

This means any future feature can send email without importing auth logic or creating a coupling between unrelated services. `services/email.py` exposes:

```python
async def send_email(to: str, subject: str, body_html: str, body_text: str) -> None: ...
```

The service raises `EmailDeliveryError` (a custom exception) when the SMTP operation fails. Callers log and handle this; a failed verification email is not a hard registration failure — the user can request a resend.

**Alternatives considered:**

- Inline email sending within auth service functions — rejected. Couples SMTP configuration and sending logic into the auth module, making both harder to test and evolve independently.

---

### D5: `get_current_user` dependency with optional email verification gate

**Decision:** `get_current_user` is a FastAPI dependency that:

1. Extracts the `Authorization: Bearer <token>` header.
2. Decodes and validates the JWT.
3. Loads `UserRecord` by `sub`.
4. If `settings.require_email_verification` is `True` and `user.is_email_verified` is `False`, raises `HTTP 403 Forbidden`.
5. Returns the `UserRecord`.

A second dependency, `get_verified_user`, is a thin alias that always enforces the email-verified check regardless of the settings flag. Routes that genuinely require a verified email (e.g., reset-password flow) use `get_verified_user`. Game-content routes use `get_current_user` — behavior varies with deployment setting.

```python
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserRecord: ...

async def get_verified_user(
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> UserRecord:
    if not user.is_email_verified:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Email not verified.")
    return user
```

**Alternatives considered:**

- A single dependency with a `require_verified: bool` parameter — rejected. FastAPI dependencies with default arguments discard the parameter in most dependency injection contexts. Two explicit dependencies is cleaner and more discoverable.

---

## Data Model Changes

### `oscilla/models/user.py`

Extended `UserRecord`:

```python
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from oscilla.models.base import Base


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # TUI identity — remains the only identity for terminal users
    user_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)

    # Web auth identity — null for TUI-only users
    email: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
        onupdate=lambda: datetime.now(tz=timezone.utc),
    )
```

**Migration note:** `user_key` changes from `nullable=False` to `nullable=True`. This requires the Alembic migration to `ALTER COLUMN user_key DROP NOT NULL`. Both SQLite and PostgreSQL support this operation.

### `oscilla/models/auth.py` (new)

```python
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from oscilla.models.base import Base


class AuthRefreshTokenRecord(Base):
    """Stores SHA-256 hashes of opaque refresh tokens.

    The plaintext token is sent to the client exactly once. Only the hash
    is persisted so a DB breach does not expose valid refresh tokens.
    """

    __tablename__ = "auth_refresh_tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    # SHA-256 hex digest of the plaintext token
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

---

## Settings Changes

New settings in `oscilla/conf/settings.py`:

```python
from pydantic import Field, SecretStr

# --- Auth settings ---
jwt_secret: SecretStr = Field(
    description="Secret key for JWT signing and itsdangerous HMAC tokens. Must be a long random string."
)
access_token_expire_minutes: int = Field(
    default=15,
    description="Lifetime of JWT access tokens in minutes.",
)
refresh_token_expire_days: int = Field(
    default=30,
    description="Lifetime of opaque refresh tokens in days.",
)
email_verify_token_expire_hours: int = Field(
    default=24,
    description="Lifetime of email verification tokens in hours.",
)
password_reset_token_expire_hours: int = Field(
    default=1,
    description="Lifetime of password reset tokens in hours.",
)
require_email_verification: bool = Field(
    default=False,
    description="When True, unverified accounts cannot access game content.",
)

# --- SMTP settings ---
smtp_host: str | None = Field(
    default=None,
    description="SMTP server hostname. Required when email features are used.",
)
smtp_port: int = Field(
    default=587,
    description="SMTP server port.",
)
smtp_user: str | None = Field(
    default=None,
    description="SMTP authentication username.",
)
smtp_password: SecretStr | None = Field(
    default=None,
    description="SMTP authentication password.",
)
smtp_from_address: str | None = Field(
    default=None,
    description="From address used on all outbound emails.",
)
smtp_use_tls: bool = Field(
    default=True,
    description="Use STARTTLS when connecting to the SMTP server.",
)
```

---

## Auth Service (`oscilla/services/auth.py`)

Key functions:

| Function                                                            | Purpose                                        |
| ------------------------------------------------------------------- | ---------------------------------------------- |
| `hash_password(plaintext: str) -> str`                              | Returns Argon2id hash                          |
| `verify_password(hashed: str, plaintext: str) -> bool`              | Constant-time verify                           |
| `create_access_token(user_id: UUID) -> str`                         | Signed JWT, expiry from settings               |
| `decode_access_token(token: str) -> UUID`                           | Validates JWT, returns user ID                 |
| `create_refresh_token(session: AsyncSession, user_id: UUID) -> str` | Generates UUID, stores hash, returns plaintext |
| `rotate_refresh_token(session: AsyncSession, token: str) -> str`    | Revokes old token, issues new one              |
| `revoke_refresh_token(session: AsyncSession, token: str) -> None`   | Marks token revoked                            |
| `make_verify_token(user_id: UUID) -> str`                           | itsdangerous email-verify token                |
| `make_reset_token(user_id: UUID) -> str`                            | itsdangerous password-reset token              |
| `verify_email_token(token: str) -> UUID \| None`                    | Validates and returns user_id                  |
| `verify_reset_token(token: str) -> UUID \| None`                    | Validates and returns user_id                  |

---

## API Endpoints

Router prefix: `/auth`. All input models use `Field` with validation.

| Method  | Path                           | Request                | Response           | Notes                                                  |
| ------- | ------------------------------ | ---------------------- | ------------------ | ------------------------------------------------------ |
| `POST`  | `/auth/register`               | `RegisterRequest`      | `UserRead`         | Creates account; sends verify email if `smtp_host` set |
| `POST`  | `/auth/login`                  | `LoginRequest`         | `TokenPairRead`    | Issues access + refresh tokens                         |
| `POST`  | `/auth/refresh`                | `RefreshRequest`       | `TokenPairRead`    | Rotates refresh token                                  |
| `POST`  | `/auth/logout`                 | `RefreshRequest`       | `204`              | Revokes refresh token                                  |
| `POST`  | `/auth/request-verify`         | `—` (auth required)    | `204`              | Resends verification email                             |
| `GET`   | `/auth/verify/{token}`         | `—`                    | `204` or HTML page | Sets `is_email_verified=True`                          |
| `POST`  | `/auth/request-password-reset` | `PasswordResetRequest` | `204`              | Sends reset email (always 204, no user enumeration)    |
| `POST`  | `/auth/password-reset/{token}` | `NewPasswordRequest`   | `204`              | Validates token, updates hash                          |
| `GET`   | `/auth/me`                     | `—` (auth required)    | `UserRead`         | Returns authenticated user                             |
| `PATCH` | `/auth/me`                     | `UserUpdateRequest`    | `UserRead`         | Updates display_name and/or password                   |

**Pydantic models:**

```python
class RegisterRequest(BaseModel):
    email: EmailStr = Field(description="Email address for the new account.")
    password: str = Field(min_length=8, description="Account password.")
    display_name: str | None = Field(default=None, max_length=60, description="Optional display name.")

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenPairRead(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserRead(BaseModel):
    id: UUID
    email: str | None
    display_name: str | None
    is_email_verified: bool
    is_active: bool
    created_at: datetime

class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=60)
    password: str | None = Field(default=None, min_length=8)

class PasswordResetRequest(BaseModel):
    email: EmailStr

class NewPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)
```

---

## Email Templates

The email service renders two transactional email templates via Jinja2 (using the existing `services/jinja.py` infrastructure):

- `oscilla/templates/email/verification.html` + `verification.txt` — contains the verification link
- `oscilla/templates/email/password_reset.html` + `password_reset.txt` — contains the reset link

Both templates receive `{display_name, action_url, expiry_description}`. Dual format (HTML + plain text) for maximum email client compatibility.

---

## Migrations

Two Alembic migrations:

1. **`UserRecord` extension** — `ALTER TABLE users ALTER COLUMN user_key DROP NOT NULL`; add `email`, `hashed_password`, `display_name`, `is_email_verified`, `is_active`, `updated_at` columns.
2. **`auth_refresh_tokens`** — create the table with appropriate foreign key and index on `token_hash`.

Both migrations must be compatible with SQLite (dev/test) and PostgreSQL (production). `DROP NOT NULL` on a column is handled by Alembic's `op.alter_column(nullable=True)` which generates dialect-appropriate SQL.

---

## Development Setup

`compose.yaml` gains a `mailhog` service:

```yaml
mailhog:
  image: mailhog/mailhog
  ports:
    - "8025:8025" # Web UI
    - "1025:1025" # SMTP
```

`.env.example` gains:

```
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USE_TLS=false
SMTP_FROM_ADDRESS=oscilla@localhost
JWT_SECRET=change-me-in-production-this-must-be-long-and-random
REQUIRE_EMAIL_VERIFICATION=false
```

---

## Testing Philosophy

- **Unit tests** for `services/auth.py`: hash/verify round-trip, `create_access_token` / `decode_access_token`, expired token rejection, itsdangerous token generation and expiry.
- **Unit tests** for `services/email.py`: SMTP call invoked with correct arguments; `smtp_host=None` skips sending without error (graceful no-op for dev environments with no SMTP).
- **Integration tests** for each auth endpoint using the FastAPI `TestClient` with an in-memory SQLite test database (via the existing `conftest.py` fixture pattern).
- Registration happy path, duplicate email, login with wrong password, token refresh and rotation, logout (token revoked), email verification flow, password reset flow.
- `get_current_user` dependency tests: valid token, expired token, revoked refresh token.
- No mocks for `UserRecord` or `AuthRefreshTokenRecord` — construct real rows against the test DB.
- `services/email.py` is monkeypatched in all auth integration tests to capture outbound email without a live SMTP server.

---

## Documentation Plan

| Document                           | Audience   | Content                                                                                                                                                                           |
| ---------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/dev/authentication.md` (new) | Developers | JWT lifecycle, refresh token rotation, itsdangerous token usage, `get_current_user` dependency, `get_verified_user` dependency, settings reference, local SMTP setup with MailHog |
| `docs/dev/api.md` (update)         | Developers | Auth endpoint reference: request/response schemas, error codes, token lifetimes                                                                                                   |
| `.env.example` (update)            | Developers | All new auth and SMTP settings with descriptions                                                                                                                                  |

---

## Risks / Trade-offs

| Risk                                                                                  | Mitigation                                                                                                                  |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `jwt_secret` missing from environment — app starts but token signing fails at runtime | Pydantic `Field` without a default means settings validation fails at startup with a clear error if the variable is not set |
| `user_key NOT NULL → NULL` migration breaks existing TUI rows                         | Migration only relaxes the constraint; existing non-null values are untouched                                               |
| `POST /auth/request-password-reset` timing oracle (email vs. no email)                | Always returns `204` regardless of whether the email exists; email is sent only if found                                    |
| Access token cannot be revoked mid-life if account is deactivated                     | `get_current_user` checks `user.is_active`; deactivated accounts get `403` even on valid tokens                             |
| aiosmtplib connection failures blocking web requests                                  | Email calls are wrapped in `try/except`; failures are logged and do not propagate to the caller                             |
