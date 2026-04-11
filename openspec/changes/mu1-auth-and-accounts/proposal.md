# Proposal: MU1 — Auth & User Accounts

## Why

Oscilla currently has no user authentication. Every player runs the engine locally with a machine-identity (`user_key`). Converting Oscilla into a shared web platform requires real user accounts with email-based authentication so that multiple players can securely access a single server deployment. This change lays the auth foundation that every subsequent multi-user phase depends on.

The TUI is fully untouched by this change. Existing `user_key`-based identity remains valid; web auth is an additive extension to the same `UserRecord` model.

## What Changes

- **New**: `UserRecord` extended with `email`, `hashed_password`, `display_name`, `is_email_verified`, `is_active`, and `updated_at` columns — all nullable so existing TUI rows remain valid.
- **New**: `auth_refresh_tokens` table for long-lived opaque refresh tokens with rotation and revocation support.
- **New**: `services/auth.py` — JWT access token encode/decode (PyJWT), Argon2id password hash/verify (argon2-cffi), itsdangerous HMAC tokens for email verification and password reset.
- **New**: `services/email.py` — standalone async email service (aiosmtplib) for composing and dispatching transactional email. Designed as a general-purpose service, not auth-specific, so future features (notifications, game event alerts, etc.) can send email without going through the auth service.
- **New**: Auth API router with endpoints: `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/request-verify`, `GET /auth/verify/{token}`, `POST /auth/request-password-reset`, `POST /auth/password-reset/{token}`, `GET /auth/me`, `PATCH /auth/me`.
- **New**: `get_current_user` FastAPI dependency — validates JWT access token and returns the authenticated `UserRecord`.
- **New**: Settings fields: `jwt_secret` (SecretStr), `access_token_expire_minutes`, `refresh_token_expire_days`, `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password` (SecretStr), `smtp_from_address`, `require_email_verification` (bool, default `False`).
- **New**: MailHog service added to `compose.yaml` for local SMTP interception in development.
- **New**: Alembic migrations for the `UserRecord` extension and `auth_refresh_tokens` table.
- **Updated**: `.env.example` with all new settings.

## Capabilities

### New Capabilities

- `web-auth`: Email + password registration, login, JWT access/refresh token issuance, token rotation, and token revocation for web users.
- `email-verification`: Optional email verification gate controlled by `require_email_verification` setting (default `False`). When enabled, unverified accounts cannot access game content. When disabled, accounts are active immediately on registration.
- `password-reset`: Time-limited HMAC token password reset flow via itsdangerous — no extra DB table required.

## Impact

- `oscilla/models/user.py` — `UserRecord` extended with auth fields
- `oscilla/services/auth.py` — new file: auth service (JWT, Argon2id, itsdangerous)
- `oscilla/services/email.py` — new file: standalone email service (aiosmtplib); auth uses it for verification and reset emails
- `oscilla/www.py` — auth router mounted
- `oscilla/settings.py` — new auth and SMTP settings fields
- `db/versions/` — two new Alembic migrations (UserRecord extension, auth_refresh_tokens)
- `compose.yaml` — MailHog service added for development SMTP
- `.env.example` — new settings documented
- `docs/dev/` — new authentication developer document

## Context

- **Overall architecture:** [frontend-roadmap.md](../../../frontend-roadmap.md) — all technology decisions, the full API surface, database schema changes, and the complete implementation phase breakdown for the Multi-User Platform.
- **Depends on:** nothing — this is the first phase.
- **Next:** [MU2 — Game Discovery & Character Management API](../mu2-game-and-character-api/proposal.md)
