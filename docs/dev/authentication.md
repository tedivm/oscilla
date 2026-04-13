# Authentication

Oscilla ships a full web authentication system mounted at `/auth`. It uses
JWT access tokens for stateless request authorization and opaque refresh tokens
stored in the database for long-lived sessions.

## Overview

| Concern             | Technology                          |
| ------------------- | ----------------------------------- |
| Password hashing    | Argon2id via `argon2-cffi`          |
| Access tokens       | HS256 JWT via `PyJWT`               |
| Refresh tokens      | SHA-256-hashed opaque tokens in DB  |
| Email/reset tokens  | HMAC via `itsdangerous`             |
| Email delivery      | Async SMTP via `aiosmtplib`         |
| Email preview (dev) | MailHog (see [Docker](./docker.md)) |

---

## Token Lifecycle

### Access Token

- Short-lived JWT (default 15 minutes), signed with `JWT_SECRET` using HS256.
- Carry the user's `sub` claim (UUID) and `exp`.
- Decoded on every authenticated request by the `get_current_user` dependency.
- Never stored in the database — stateless.

### Refresh Token

- Long-lived opaque random string (default 30 days).
- Only the SHA-256 hash is stored in `auth_refresh_tokens`; the plaintext token
  is returned to the client once and never stored.
- Each use **rotates** the token: the old hash is marked revoked and a new token
  is issued atomically. Re-use of a revoked token returns HTTP 401.
- Explicitly revoked at logout.

### Email / Password-Reset Tokens

- Signed with `itsdangerous.URLSafeTimedSerializer` using `JWT_SECRET`.
- Use distinct `salt` values (`"email-verify"` and `"password-reset"`) so tokens
  from one flow cannot be replayed in the other.
- Short-lived: email verification tokens expire in 24 hours (configurable),
  password-reset tokens in 1 hour (configurable).

---

## FastAPI Dependencies

Two reusable dependencies live in `oscilla/dependencies/auth.py`:

| Dependency          | Behavior                                                                                                      |
| ------------------- | ------------------------------------------------------------------------------------------------------------- |
| `get_current_user`  | Decodes the Bearer JWT, loads the `UserRecord`, checks `is_active`. Raises 401/403 on failure.                |
| `get_verified_user` | Same as above, plus enforces `is_email_verified=True` regardless of the `REQUIRE_EMAIL_VERIFICATION` setting. |

Usage in a router:

```python
from typing import Annotated
from fastapi import Depends
from oscilla.dependencies.auth import get_current_user, get_verified_user
from oscilla.models.user import UserRecord

@router.get("/protected")
async def protected(user: Annotated[UserRecord, Depends(get_current_user)]) -> ...:
    ...

@router.get("/verified-only")
async def verified_only(user: Annotated[UserRecord, Depends(get_verified_user)]) -> ...:
    ...
```

---

## Settings Reference

All settings live in `oscilla/conf/settings.py` and are read from environment
variables (or `.env`).

| Variable                            | Default                 | Description                                                            |
| ----------------------------------- | ----------------------- | ---------------------------------------------------------------------- |
| `JWT_SECRET`                        | required                | Secret for JWT signing and HMAC email tokens.                          |
| `ACCESS_TOKEN_EXPIRE_MINUTES`       | `15`                    | JWT access token lifetime in minutes.                                  |
| `REFRESH_TOKEN_EXPIRE_DAYS`         | `30`                    | Refresh token lifetime in days.                                        |
| `EMAIL_VERIFY_TOKEN_EXPIRE_HOURS`   | `24`                    | Email verification token lifetime in hours.                            |
| `PASSWORD_RESET_TOKEN_EXPIRE_HOURS` | `1`                     | Password reset token lifetime in hours.                                |
| `REQUIRE_EMAIL_VERIFICATION`        | `False`                 | When `True`, unverified accounts cannot access game content.           |
| `BASE_URL`                          | `http://localhost:8000` | Base URL prepended to links in verification and password-reset emails. |
| `SMTP_HOST`                         | `None`                  | SMTP hostname. Leave unset to disable email sending.                   |
| `SMTP_PORT`                         | `587`                   | SMTP port.                                                             |
| `SMTP_USER`                         | `None`                  | SMTP login username.                                                   |
| `SMTP_PASSWORD`                     | `None`                  | SMTP login password (stored as `SecretStr`).                           |
| `SMTP_FROM_ADDRESS`                 | `None`                  | Sender address in outgoing email.                                      |
| `SMTP_USE_TLS`                      | `True`                  | Whether to use STARTTLS.                                               |

`JWT_SECRET` has no default and is required at startup. The application will
refuse to start if it is not set.

### Generating a secure secret

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Email Templates

HTML and plain-text email templates live in `oscilla/templates/email/`:

| Template                       | Purpose                    |
| ------------------------------ | -------------------------- |
| `verification.html` / `.txt`   | Email address verification |
| `password_reset.html` / `.txt` | Password reset link        |

Templates receive three Jinja2 variables: `display_name`, `action_url`, and
`expiry_description`.

When `SMTP_HOST` is not set, email sending is skipped silently (a DEBUG log
message is emitted). This allows the system to work without email configuration
in test and minimal deployment scenarios.

---

## Development: MailHog

The Docker Compose stack runs [MailHog](https://github.com/mailhog/MailHog)
for local email inspection. See [Docker](./docker.md) for details. The relevant
`.env` settings:

```dotenv
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USE_TLS=False
SMTP_FROM_ADDRESS=oscilla@localhost
```

MailHog's web UI is available at `http://localhost:8025`.

---

## Testing

Router integration tests live in `tests/routers/test_auth.py` and use the
`auth_client` pytest fixture defined in `tests/conftest.py`.

The `auth_client` fixture:

- Provides a `TestClient` backed by an isolated test database.
- Patches `oscilla.services.email.send_email` to a no-op async function so no
  real email is sent. Sent-email metadata accumulates in `client.sent_emails`
  for assertion in tests.

Service-level tests for token generation, password hashing, and refresh token
rotation live in `tests/services/test_auth.py`.

Dependency tests (`tests/dependencies/test_auth.py`) verify that
`get_current_user` and `get_verified_user` raise the correct HTTP errors for
missing, invalid, or inactive-account tokens.

---

## Security Controls

### Rate Limiting

Login and registration attempts are rate-limited using the persistent cache
(Redis in production, `NoOpCache` in development).

| Endpoint         | Cache key pattern  | Setting                             | Window |
| ---------------- | ------------------ | ----------------------------------- | ------ |
| `POST /login`    | `rl:login:{email}` | `MAX_LOGIN_ATTEMPTS_PER_HOUR`       | 1 hour |
| `POST /register` | `rl:register:{ip}` | `MAX_REGISTRATIONS_PER_HOUR_PER_IP` | 1 hour |

When the count exceeds the limit, the endpoint returns `HTTP 429 Too Many Requests`.

**Development behavior**: When `CACHE_ENABLED=False` (the default in development),
`NoOpCache._increment` returns `delta=1` on every call regardless of how many
times it is called — the counter never accumulates. Rate limiting is therefore
transparently disabled in development without any configuration change.

### Account Lockout

After too many consecutive failed login attempts, the account is locked for a
configurable duration.

| Cache key               | Purpose                                                               |
| ----------------------- | --------------------------------------------------------------------- |
| `lockout_count:{email}` | Consecutive failure counter (expires after `LOCKOUT_WINDOW_SECONDS`)  |
| `lockout:{email}`       | Lock sentinel (expires after `LOCKOUT_DURATION_MINUTES × 60` seconds) |

- `MAX_LOGIN_ATTEMPTS_BEFORE_LOCKOUT` (default: 5) — failures before lockout.
- `LOCKOUT_DURATION_MINUTES` (default: 15) — duration of lockout.
- `LOCKOUT_WINDOW_SECONDS` (default: 300) — sliding window for failure counting.

A successful login automatically clears both cache keys via `clear_lockout()`.
Locked accounts receive `HTTP 423 Locked`.

Like rate limiting, lockout is transparently disabled when `CACHE_ENABLED=False`.

### Auth Audit Log

Every significant auth event is written to the `auth_audit_log` table with IP
address, user agent, and timestamp.

| Event type       | Trigger                                          |
| ---------------- | ------------------------------------------------ |
| `login_success`  | Successful password verification and token issue |
| `login_failure`  | Failed password verification                     |
| `logout`         | Refresh token revoked                            |
| `password_reset` | Password successfully changed via reset token    |
| `email_verify`   | Email address verified via verify token          |

**Table structure** (`auth_audit_log`):

| Column       | Type                            | Notes                                                                             |
| ------------ | ------------------------------- | --------------------------------------------------------------------------------- |
| `id`         | UUID (PK)                       | Random UUID, generated at insert.                                                 |
| `user_id`    | UUID (nullable FK → `users.id`) | `SET NULL` on user deletion — audit records are preserved when a user is deleted. |
| `event_type` | str                             | One of the event types above.                                                     |
| `ip_address` | str (nullable)                  | Client IP from the request.                                                       |
| `user_agent` | str (nullable)                  | `User-Agent` header from the request.                                             |
| `created_at` | datetime                        | UTC timestamp; indexed for efficient time-range queries.                          |

Reading audit logs requires direct database access (e.g., `make db` or `psql`).
No read API is exposed in MU6.

### Password Strength

All new passwords are evaluated with [zxcvbn](https://github.com/dwolfhub/zxcvbn-python)
before being accepted. The score ranges from 0 (very weak) to 4 (very strong).
Passwords scoring below `MIN_PASSWORD_STRENGTH` (default: 2) are rejected with
`HTTP 422 Unprocessable Content` and the zxcvbn suggestion string is surfaced in
the error detail.

Score 2 is the minimum because it is OWASP-aligned and avoids over-rejecting
reasonable passwords — short random strings or memorable passphrases score 2
while common dictionary words score 0 or 1.
