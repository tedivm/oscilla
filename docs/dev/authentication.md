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
