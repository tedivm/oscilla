# Tasks: MU6 — Production Hardening

## 1. Settings Additions

- [x] 1.1 In `oscilla/conf/settings.py`, add the following fields to the `Settings` class after the `base_url` field: `max_login_attempts_per_hour: int = Field(default=10, description="Login attempts per email per hour before rate limiting.")`, `max_registrations_per_hour_per_ip: int = Field(default=5, description="Registration attempts per IP per hour.")`, `max_login_attempts_before_lockout: int = Field(default=5, description="Consecutive failed logins before lockout.")`, `lockout_duration_minutes: int = Field(default=15, description="Duration of account lockout in minutes.")`, `lockout_window_seconds: int = Field(default=300, description="Window for counting consecutive failures in seconds.")`, `cors_origins: List[str] = Field(default=["http://localhost:5173"], description="Allowed CORS origins. Include the frontend domain in production. Never use ['*'] with allow_credentials=True.")`, `log_level: str = Field(default="INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR.")`, `uvicorn_workers: int = Field(default=1, description="Number of Uvicorn worker processes.")`; add `from typing import List` to imports if not already present

- [x] 1.2 Add corresponding entries to `.env.example` under a new `# Production Security` section documenting all eight new settings with example production values and inline comments explaining each (e.g., `# CORS_ORIGINS='["https://play.example.com"]'  # JSON list; default allows SvelteKit dev server`)

## 2. Rate Limiting Service

- [x] 2.1 Create `oscilla/services/rate_limit.py` containing the async function `check_rate_limit(key: str, max_attempts: int, window_seconds: int) -> bool` that uses `caches.get("persistent")` to atomically increment the key, sets TTL on the first increment, and returns `True` if the count is within the limit or `False` if exceeded; import `from aiocache import caches`; add a module-level docstring explaining that with `NoOpCache` (when `cache_enabled=False`), `_increment` returns `delta=1` on every call so the check always passes and rate limiting is transparently disabled in development

- [x] 2.2 Add `tests/services/test_rate_limit.py` with: (a) `test_check_rate_limit_noop_always_allows` — verify that 100 calls in a row all return `True` using the test-environment `NoOpCache` (no mocking required, just call `check_rate_limit` repeatedly); (b) `test_check_rate_limit_redis_stub_blocks_on_threshold` — use `monkeypatch` to replace `caches.get("persistent")` with a stub cache whose `increment` returns an increasing integer and `expire` is a noop; verify that the first `max_attempts` calls return `True` and the next call returns `False`; (c) `test_check_rate_limit_sets_ttl_on_first_increment` — verify that `expire` is called with the correct `window_seconds` on the first call and not called again on subsequent calls (use the same stub as above with a call counter)

## 3. Account Lockout Service

- [x] 3.1 In `oscilla/services/auth.py` add three async functions: `record_failed_login(email: str) -> bool` (increments `lockout_count:{email}`, sets TTL on first increment, if count reaches `settings.max_login_attempts_before_lockout` also sets `lockout:{email}` for `lockout_duration_minutes * 60` seconds, returns `True` if the account is now locked); `is_account_locked(email: str) -> bool` (checks `caches.get("persistent").exists(f"lockout:{email}")`); `clear_lockout(email: str) -> None` (deletes both `lockout:{email}` and `lockout_count:{email}`)

- [x] 3.2 Add `tests/services/test_lockout.py` with: (a) `test_is_account_locked_false_by_default` — verify `is_account_locked` returns `False` for an unknown email using the test `NoOpCache`; (b) `test_record_failed_login_returns_false_below_threshold` — call `record_failed_login` `max_login_attempts_before_lockout - 1` times with the `NoOpCache` and verify all return `False` (NoOpCache never accumulates, so threshold is never reached); (c) `test_clear_lockout_no_error` — verify `clear_lockout` completes without raising an exception

## 4. Auth Router Updates — Rate Limiting and Lockout

- [x] 4.1 In `oscilla/routers/auth.py`, update the `login` endpoint to: (a) import `check_rate_limit` from `oscilla.services.rate_limit`; (b) before the password check, call `await check_rate_limit(f"rl:login:{request.email}", settings.max_login_attempts_per_hour, 3600)`; if it returns `False` raise `HTTPException(status_code=HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts. Try again later.")`; (c) import `is_account_locked`, `record_failed_login`, `clear_lockout` from `oscilla.services.auth`; (d) before the password check, call `await is_account_locked(request.email)`; if `True` raise `HTTPException(status_code=HTTP_423_LOCKED, detail="Account is temporarily locked due to too many failed login attempts.")`; (e) on failed password verification call `await record_failed_login(request.email)` before raising the 401; (f) on successful login call `await clear_lockout(request.email)`; add `HTTP_423_LOCKED` and `HTTP_429_TOO_MANY_REQUESTS` to the starlette status imports

- [x] 4.2 In `oscilla/routers/auth.py`, update the `register` endpoint to: (a) accept a `request_obj: Request` parameter (import `Request` from `fastapi`); (b) extract the client IP as `ip = request_obj.client.host if request_obj.client else "unknown"`; (c) call `await check_rate_limit(f"rl:register:{ip}", settings.max_registrations_per_hour_per_ip, 3600)`; if `False` raise `HTTPException(status_code=HTTP_429_TOO_MANY_REQUESTS, detail="Too many registration attempts from this address.")` before any DB work

- [x] 4.3 Add `tests/routers/test_auth_rate_limit.py` with integration tests using `auth_client`: (a) `test_login_rate_limit_disabled_with_noop_cache` — make 20 sequential failed login requests and verify none return 429 (NoOpCache never blocks); (b) `test_login_lockout_disabled_with_noop_cache` — make 10 sequential failed login requests and verify none return 423 (NoOpCache never accumulates); (c) `test_register_rate_limit_disabled_with_noop_cache` — make 10 sequential registration requests and verify none return 429

## 5. Password Strength Validation

- [x] 5.1 Add `zxcvbn` to `pyproject.toml` dependencies (run `uv add zxcvbn`); verify the package installs with `uv sync`

- [x] 5.2 Create `oscilla/services/password_strength.py` containing `validate_password_strength(password: str) -> None`: use `import zxcvbn as zxcvbn_lib; result = zxcvbn_lib.zxcvbn(password)`; if `result["score"] < 2`, extract `suggestions = result.get("feedback", {}).get("suggestions", [])` and raise `ValueError(suggestions[0] if suggestions else "Password is too weak.")`; add a module-level docstring explaining the scoring scale (0–4) and why score 2 is the minimum (OWASP-aligned, avoids overly rejecting reasonable passwords)

- [x] 5.3 In `oscilla/routers/auth.py`, update the `register` endpoint to call `validate_password_strength(request.password)` after input validation and before the duplicate-email check; catch `ValueError` and re-raise as `HTTPException(status_code=HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))`; import `validate_password_strength` from `oscilla.services.password_strength`

- [x] 5.4 Add `tests/services/test_password_strength.py` with: (a) `test_weak_password_raises` — verify `validate_password_strength("password")` raises `ValueError`; (b) `test_keyboard_walk_raises` — verify `validate_password_strength("qwerty123")` raises `ValueError`; (c) `test_strong_password_passes` — verify `validate_password_strength("correct-horse-battery-staple")` does not raise; (d) `test_error_message_is_string` — verify the raised `ValueError` message is a non-empty string

## 6. `get_current_user` Request State Update

- [x] 6.1 In `oscilla/dependencies/auth.py`, update `get_current_user` to accept a `request: Request` parameter (import `Request` from `fastapi`) and add `request.state.user_id = user.id` immediately after the user is confirmed active and verified; add a comment explaining that this is read by `RequestLoggingMiddleware` in `www.py` to associate log records with authenticated users

- [x] 6.2 Update `tests/dependencies/test_auth.py` to confirm `request.state.user_id` is set on the request object after a successful `get_current_user` call; verify it is not set (or remains unset) when an exception is raised

## 7. Auth Audit Log

- [x] 7.1 Create `oscilla/models/auth_audit_log.py` defining the `AuthAuditLogRecord` SQLAlchemy model with: `id: Mapped[UUID]` (primary key, default `uuid4`), `user_id: Mapped[UUID | None]` (nullable FK to `users.id`, no cascade delete — audit records must survive user deletion), `event_type: Mapped[str]` (not null), `ip_address: Mapped[str | None]`, `user_agent: Mapped[str | None]`, `created_at: Mapped[datetime]` (default `datetime.now(UTC)`, indexed)

- [x] 7.2 Create an Alembic migration with `make create_migration MESSAGE="add_auth_audit_log_table"` and verify the generated migration creates the `auth_audit_log` table with all columns, an index on `created_at`, and is compatible with both SQLite and PostgreSQL; ensure the nullable FK to `users` uses `ondelete="SET NULL"` so audit records are preserved when a user is deleted

- [x] 7.3 In `oscilla/services/auth.py`, add `record_auth_event(session: AsyncSession, event_type: str, user_id: UUID | None = None, ip_address: str | None = None, user_agent: str | None = None) -> None` that creates an `AuthAuditLogRecord` and adds it to the session (but does NOT commit — the caller controls transaction boundaries); import `AuthAuditLogRecord` from `oscilla.models.auth_audit_log`; add `AuthAuditLogRecord` to `oscilla/models/__init__.py` so Alembic autogenerate can detect it

- [x] 7.4 In `oscilla/routers/auth.py`, thread audit log calls through the `login`, `logout`, `password_reset`, and `verify_email` endpoints: (a) `login` — after successful auth AND `clear_lockout` call: `await record_auth_event(db, "login_success", user_id=user.id, ip_address=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))`; after failed password check (before raising 401): `await record_auth_event(db, "login_failure", user_id=user.id if user else None, ip_address=..., user_agent=...)`; (b) `logout` after `revoke_refresh_token`: `await record_auth_event(db, "logout", ...)`; (c) `password_reset` after `user.hashed_password =` update: `await record_auth_event(db, "password_reset", user_id=user.id, ...)`; (d) `verify_email` after `user.is_email_verified = True`: `await record_auth_event(db, "email_verify", user_id=user.id, ...)`; the `login` and `register` endpoints already accept `Request` from task 4.2, but `logout`, `password_reset`, and `verify_email` will also need `Request` added as a parameter

- [x] 7.5 Add `tests/routers/test_auth_audit.py` with tests using `auth_client` fixture and a direct DB session to query `AuthAuditLogRecord`: (a) `test_successful_login_creates_login_success` — register a user, login successfully, query DB for `event_type="login_success"` rows, assert exactly one exists with the correct `user_id`; (b) `test_failed_login_creates_login_failure` — register a user, fail login with wrong password, query DB for `event_type="login_failure"`, assert one row exists; (c) `test_logout_creates_logout_event` — login, then logout, assert a `"logout"` row exists; (d) `test_email_verify_creates_verify_event` — register, call `/auth/verify/{token}` with a valid token, assert `"email_verify"` row exists

## 8. Security Headers Middleware

- [x] 8.1 Create `oscilla/middleware/security_headers.py` containing `SecurityHeadersMiddleware(BaseHTTPMiddleware)` with a `dispatch` method that calls `call_next(request)` and then sets the following headers on the response: `Strict-Transport-Security: max-age=31536000; includeSubDomains`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'`, `Referrer-Policy: strict-origin-when-cross-origin`; add a comment on `unsafe-inline` in `style-src` explaining it is required for SvelteKit's inline `<style>` injection; create `oscilla/middleware/__init__.py` as an empty file

- [x] 8.2 In `oscilla/www.py`, add `from oscilla.middleware.security_headers import SecurityHeadersMiddleware` and add `app.add_middleware(SecurityHeadersMiddleware)` before the existing router includes

- [x] 8.3 Add `tests/middleware/test_security_headers.py` and `tests/middleware/__init__.py` with: (a) `test_security_headers_present` — use the test `app` fixture, make a `GET /health` request, assert all five headers are present with correct values; (b) `test_csp_frame_ancestors` — assert `frame-ancestors 'none'` is in the `Content-Security-Policy` header; (c) `test_hsts_includes_subdomains` — assert `includeSubDomains` is in the `Strict-Transport-Security` header

## 9. CORS Middleware

- [x] 9.1 In `oscilla/www.py`, add `from fastapi.middleware.cors import CORSMiddleware` and add `app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])` before the security headers middleware (added after, since FastAPI applies middleware in reverse registration order, CORS must be registered last to execute outermost); add a comment explaining the reverse-registration order

- [x] 9.2 Add `tests/middleware/test_cors.py` with: (a) `test_cors_preflight_allowed_origin` — issue an `OPTIONS` request with `Origin: http://localhost:5173` and verify the response contains `access-control-allow-origin: http://localhost:5173`; (b) `test_cors_preflight_disallowed_origin` — issue an `OPTIONS` request with `Origin: https://evil.example.com` and verify the response does NOT contain a permissive `access-control-allow-origin: *` header (the default `cors_origins` does not include this origin)

## 10. Request Logging Middleware

- [x] 10.1 Create `oscilla/middleware/request_logging.py` containing `RequestLoggingMiddleware(BaseHTTPMiddleware)` that: (a) generates a `request_id = str(uuid4())`; (b) sets `request.state.request_id = request_id`; (c) logs `"request_start"` at `INFO` with `extra={"request_id": request_id, "method": request.method, "path": request.url.path}`; (d) calls `call_next(request)` and records start time via `time.monotonic()`; (e) after the response, reads `user_id = getattr(request.state, "user_id", None)` and logs `"request_end"` at `INFO` with `extra={"request_id": request_id, "status_code": response.status_code, "duration_ms": int((time.monotonic() - start) * 1000), "user_id": str(user_id) if user_id else None}`; import `time`, `uuid4`, `getLogger`, `BaseHTTPMiddleware`, and `Request` from appropriate modules

- [x] 10.2 In `oscilla/www.py`, add `from oscilla.middleware.request_logging import RequestLoggingMiddleware` and add `app.add_middleware(RequestLoggingMiddleware)` as the outermost middleware (registered first, since FastAPI applies in reverse order); add a comment in `www.py` explaining the three-middleware ordering: RequestLogging (outermost) → SecurityHeaders → CORSMiddleware (innermost)

- [x] 10.3 Add `tests/middleware/test_request_logging.py` with: (a) `test_request_id_in_log` — use `caplog` at `INFO` level, make a `GET /health` request, assert a log record contains `"request_start"` and the `request_id` key in its `extra` dict is a valid UUID string; (b) `test_request_end_logs_status_code` — assert a `"request_end"` log record is emitted with `status_code` set; (c) `test_duration_ms_is_non_negative` — assert `duration_ms` in the `"request_end"` log record is `>= 0`

## 11. Health and Readiness Endpoints

- [x] 11.1 Create `oscilla/routers/health.py` with two endpoints: (a) `GET /health` returning `{"status": "ok"}` with HTTP 200 — no DB, no cache, no auth; (b) `GET /ready` that runs `await db.execute(text("SELECT 1"))` and `await cache.exists("__ready_check__")` in parallel using `asyncio.gather`, returns `{"status": "ok", "db": True, "cache": True}` with HTTP 200 when both pass, or `{"status": "degraded", "db": <bool>, "cache": <bool>}` with HTTP 503 when either fails; import `text` from `sqlalchemy`, `caches` from `aiocache`, `asyncio`, and the `get_session_depends` dependency; add Pydantic `HealthRead` and `ReadyRead` response models

- [x] 11.2 In `oscilla/www.py`, include the health router: `from oscilla.routers.health import router as health_router` and `app.include_router(health_router, tags=["health"])` (no prefix — probes are at root `/health` and `/ready`)

- [x] 11.3 Add `tests/routers/test_health.py` with: (a) `test_health_always_200` — `GET /health` returns 200 with `{"status": "ok"}`; (b) `test_ready_200_with_live_db` — `GET /ready` with the test DB fixture returns 200 with `db: true`; (c) `test_ready_503_with_dead_db` — monkeypatch the DB session `execute` method to raise an exception, assert `/ready` returns 503 with `db: false`

## 12. Production Docker Hardening

- [x] 12.1 Update `dockerfile.www` to: (a) before the final `CMD`, add `RUN groupadd -g 999 oscilla && useradd -u 999 -g 999 -s /bin/bash oscilla`; (b) add `USER oscilla` as the last directive before `CMD`; (c) change the `uv sync` step to use `uv sync --no-dev` in the production stage; verify the image still builds by running `docker build -f dockerfile.www -t oscilla-test .`

- [x] 12.2 Update `compose.yaml` to assign the `dev` Docker Compose profile to MailHog (add `profiles: [dev]` under the mailhog service definition); add a comment explaining that `docker compose up` starts only production services and `docker compose --profile dev up` also starts MailHog; verify `docker compose up -d` (without `--profile dev`) no longer starts MailHog

- [x] 12.3 Update `docker/www/prestart.sh` (or the Uvicorn startup command in `dockerfile.www`) to use `--workers ${UVICORN_WORKERS:-1}` so the `uvicorn_workers` setting from `.env` is respected; verify hot reload is absent from the production CMD (it should already be absent from `dockerfile.www`, but confirm)

## 13. Documentation

- [x] 13.1 Update `docs/dev/authentication.md` to add a new "Security Controls" section after the existing token flow diagrams covering: (a) rate limiting — key patterns (`rl:login:{email}`, `rl:register:{ip}`), configurable settings, and how `NoOpCache` disables it in development; (b) account lockout — threshold, duration, `lockout:` and `lockout_count:` key patterns, automatic clear on successful login; (c) auth audit log — all five event types, the DB table structure, why the FK uses `SET NULL`, the note that log reading requires direct DB access in MU6; (d) password strength — zxcvbn score scale, minimum score of 2, and how the suggestion string surfaces in the 422 response

- [x] 13.2 Update `docs/dev/api.md` to add a "Health Probes" section documenting: `GET /health` — always 200, process liveness only, no dependencies; `GET /ready` — DB `SELECT 1` + cache ping, 200 on success, 503 on degraded; response schemas for both; recommended Docker Compose `healthcheck:` configuration snippet; note on orchestrator behavior when readiness fails

- [x] 13.3 Update `docs/dev/docker.md` (create it if it does not exist) with: (a) production hardening — non-root `oscilla` user with UID/GID 999, rationale for fixed UID; (b) worker configuration — `UVICORN_WORKERS` env var, how to set it per deployment; (c) dev vs production profiles — `docker compose --profile dev up` for MailHog; (d) production SMTP — which `.env` variables are required and example values; (e) `--no-dev` dependency sync in the production image

## 14. Testlandia Content

There is no Testlandia-specific content for MU6 — this change adds no new game features or content types. The rate limiting, lockout, security headers, and audit log are transparent to content authors. However, the Docker changes affect the Testlandia developer environment and should be verified:

- [x] 14.1 Verify that the `docker compose up -d` command (without `--profile dev`) starts all services needed for Testlandia development (db, redis) but no longer starts MailHog; run `docker compose up -d` and verify services with `docker compose ps`

- [x] 14.2 Verify that the existing Testlandia content continues to validate after all MU6 code changes by running `oscilla content test --game testlandia`; confirm the auth system changes do not affect content loading or adventure execution
