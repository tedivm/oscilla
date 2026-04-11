# Design: MU6 — Production Hardening

## Context

MU1–MU5 deliver a fully functional multi-user web platform. This change hardens it for production deployment by addressing the security controls, operational tooling, and deployment concerns that were deferred until a working system could be tested end-to-end.

This change has no new game features and no new API surface visible to players (except `/health` and `/ready`). Every item is a security control, an operational necessity, or a production deployment practice.

The guiding principle: no new external services. Every security control reuses infrastructure already in place. Rate limiting uses the existing `aiocache` Redis backend. Account lockout uses the same counter pattern. CORS and security headers are FastAPI middleware at zero infrastructure cost.

---

## Goals / Non-Goals

**Goals:**

- Rate limiting on auth endpoints via `aiocache` Redis `increment` + TTL.
- Account lockout after N configurable failed login attempts.
- CORS middleware with allowlist origins from settings.
- Security headers middleware: HSTS, `X-Content-Type-Options`, `X-Frame-Options`, Content-Security-Policy.
- Password strength validation at registration (entropy-based, not length-only).
- Structured request logging: request ID, user ID (if authenticated), endpoint, status code, duration.
- Auth audit log: login, logout, password reset, email verification events.
- `GET /health` — liveness probe.
- `GET /ready` — readiness probe (DB + Redis connectivity).
- Production Docker hardening: non-root user, proper Uvicorn worker configuration, no hot-reload.
- MailHog removed from production compose profile; SMTP documented in `.env.example`.
- Settings additions for all new controls.

**Non-Goals:**

- Admin user management UI or API — deferred.
- Distributed rate limiting across multiple server instances — the Redis-backed counter is already distributed; this is in scope. What is out of scope is IP-based rate limiting (requires `X-Forwarded-For` handling and proxy trust configuration).
- Web Application Firewall (WAF) — infrastructure concern, not application code.
- Mutual TLS or client certificate authentication.

---

## Decisions

### D1: Rate limiting via `aiocache` Redis `increment` — no new dependency

**Decision:** The existing `get_cache("persistent")` aiocache alias is used for rate limiting counters. The `RedisCache` backend maps `increment(key, delta)` to a Redis `INCR` command, which is atomic. TTL is set on the first increment using a separate `expire()` call.

The rate limiting pattern:

```python
from aiocache import caches

async def check_rate_limit(
    key: str,
    max_attempts: int,
    window_seconds: int,
) -> bool:
    """Return True if the request is allowed; False if it should be rate-limited."""
    cache = caches.get("persistent")
    count = await cache.increment(key, delta=1)
    if count == 1:
        # First increment — set the expiry window
        await cache.expire(key, ttl=window_seconds)
    return count <= max_attempts
```

**`NoOpCache` behavior in development:** `NoOpCache._increment` returns `delta` (the increment amount — by default `1`) on every call because there is no backing store. The counter never accumulates beyond the `delta` value. Since `max_attempts` is always ≥ 1, the condition `count <= max_attempts` (where `count == 1`) is always `True`. Rate limiting is effectively disabled when `cache_enabled=False` — no configuration change required to disable it in development.

Rate limiting is applied at two points in `oscilla/routers/auth.py`:

| Endpoint              | Key pattern        | Limit                                           | Window       |
| --------------------- | ------------------ | ----------------------------------------------- | ------------ |
| `POST /auth/login`    | `rl:login:{email}` | `max_login_attempts_per_hour` (default 10)      | 3600 seconds |
| `POST /auth/register` | `rl:register:{ip}` | `max_registrations_per_hour_per_ip` (default 5) | 3600 seconds |

IP extraction for registration throttle uses `request.client.host`. If the server is behind a reverse proxy, `X-Forwarded-For` must be considered (see risks).

---

### D2: Account lockout stored as a separate cache key from rate limiting

**Decision:** Login rate limiting (D1) and account lockout are separate mechanisms with different keys and reset conditions:

- **Rate limiting** (`rl:login:{email}`) — sliding window; resets automatically after the TTL window. Does not require an explicit admin unlock.
- **Account lockout** (`lockout:{email}`) — set when a user's **total consecutive failed logins** exceeds `max_login_attempts_before_lockout` (default 5). Expires after `lockout_duration_minutes` (default 15). Cleared on any successful login.

```python
async def record_failed_login(email: str) -> bool:
    """Record a failed login. Returns True if the account is now locked."""
    cache = caches.get("persistent")
    key = f"lockout_count:{email}"
    count = await cache.increment(key, delta=1)
    if count == 1:
        await cache.expire(key, ttl=settings.lockout_window_seconds)
    if count >= settings.max_login_attempts_before_lockout:
        await cache.set(f"lockout:{email}", 1, ttl=settings.lockout_duration_minutes * 60)
        return True
    return False

async def is_account_locked(email: str) -> bool:
    cache = caches.get("persistent")
    return await cache.exists(f"lockout:{email}")

async def clear_lockout(email: str) -> None:
    """Called on successful login to reset the consecutive failure counter."""
    cache = caches.get("persistent")
    await cache.delete(f"lockout:{email}")
    await cache.delete(f"lockout_count:{email}")
```

With `NoOpCache`: `exists()` always returns `False`; all lockout checks pass as if no lockout exists. Lockout is effectively disabled in development.

**Why not use the DB for lockout?** DB-backed lockout requires a new column on `UserRecord` (or a new table) and a migration. A cache-backed lockout is ephemeral — unlocked on Redis restart or TTL expiry — which is acceptable behavior. DB-backed lockout would be stronger for long-duration (multi-day) lockouts; the current configurable TTL handles the threat model (brute-force protection).

---

### D3: Security headers as a FastAPI middleware

**Decision:** A `SecurityHeadersMiddleware` class added to `oscilla/www.py` injects the following response headers on every response:

| Header                      | Value                                                                                                                                       |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains`                                                                                                       |
| `X-Content-Type-Options`    | `nosniff`                                                                                                                                   |
| `X-Frame-Options`           | `DENY`                                                                                                                                      |
| `Content-Security-Policy`   | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'` |
| `Referrer-Policy`           | `strict-origin-when-cross-origin`                                                                                                           |

The Content-Security-Policy `unsafe-inline` for `style-src` is required because SvelteKit injects inline `<style>` blocks in the generated HTML. This is the minimum viable CSP. A stricter policy with nonces is a future improvement.

`X-Frame-Options: DENY` and `frame-ancestors 'none'` are both set for maximum clickjacking protection (belt and suspenders for older browser support).

HTTPS-only deployment is assumed. The HSTS header is included in the middleware rather than at the reverse proxy level so that it is applied consistently regardless of deployment topology.

---

### D4: CORS configured via settings

**Decision:** FastAPI's `CORSMiddleware` is added with origins sourced from settings:

```python
cors_origins: List[str] = Field(
    default=["http://localhost:5173"],  # SvelteKit dev server
    description="Allowed CORS origins. Include the frontend domain in production.",
)
```

In production, operators set `CORS_ORIGINS='["https://play.example.com"]'` in their `.env` file. The default allows the SvelteKit dev server for local development.

`allow_credentials=True` is required for cookie-based auth (if adopted in the future). `allow_methods=["*"]` and `allow_headers=["*"]` are acceptable given the origin allowlist gates access.

---

### D5: Password strength via `zxcvbn`

**Decision:** Registration password validation uses the `zxcvbn` library (a port of Dropbox's password strength estimator). `zxcvbn` estimates entropy based on pattern matching (dictionary words, keyboard walks, repeated characters, etc.) rather than requiring arbitrary complexity rules that users game with `Password1!`.

```python
import zxcvbn

def validate_password_strength(password: str) -> None:
    """Raise ValueError if the password is too weak.

    zxcvbn score: 0=very guessable, 1=easily, 2=somewhat guessable, 3=safely unguessable, 4=very unguessable.
    Minimum score of 2 is the OWASP-aligned recommendation for user-facing products.
    """
    result = zxcvbn.zxcvbn(password)
    if result["score"] < 2:
        suggestions = result.get("feedback", {}).get("suggestions", [])
        detail = suggestions[0] if suggestions else "Password is too weak."
        raise ValueError(detail)
```

The `422 Unprocessable Entity` response from the registration endpoint includes the `zxcvbn` suggestion string directly in the error detail so the frontend can display actionable feedback (e.g., "Add another word or two. Uncommon words are better.").

`zxcvbn` is a pure-Python library with no external dependencies. It does not require a network call or a Redis lookup.

**New dependency:** `zxcvbn` added to `pyproject.toml` dependencies.

---

### D6: Structured request logging with request IDs

**Decision:** A `RequestLoggingMiddleware` is added to `oscilla/www.py`. For every request it:

1. Generates a `request_id` UUID.
2. Sets `request.state.request_id` for downstream use.
3. Logs at the start: `{request_id, method, path, user_agent}`.
4. After response: `{request_id, method, path, status_code, duration_ms, user_id}`.

`user_id` is read from `request.state.user_id`, which `get_current_user` sets on the request state whenever it successfully authenticates a token. This means unauthenticated requests log `user_id: null`.

```python
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id
        start = time.monotonic()
        logger.info(
            "request_start",
            extra={"request_id": request_id, "method": request.method, "path": request.url.path},
        )
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)
        user_id = getattr(request.state, "user_id", None)
        logger.info(
            "request_end",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user_id": str(user_id) if user_id else None,
            },
        )
        return response
```

The `extra` dict fields are preserved in structured log output when using `python-json-logger` or similar. In development with the default `logging` formatter, they appear inline.

---

### D7: Auth audit log — DB-backed table

**Decision:** Unlike rate limiting and lockout (ephemeral cache entries), the auth audit log is persisted to the database. Security events must survive Redis restarts and rolling deployments.

```
auth_audit_log
├── id          UUID PK
├── user_id     UUID FK → users (nullable — pre-authentication events may involve unknown users)
├── event_type  str NOT NULL  (login_success, login_failure, logout, password_reset, email_verify)
├── ip_address  str | None
├── user_agent  str | None
└── created_at  datetime
```

A new Alembic migration creates this table. A new helper in `services/auth.py`:

```python
async def record_auth_event(
    session: AsyncSession,
    event_type: str,
    user_id: UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None: ...
```

Called at specific points in `routers/auth.py`:

- After successful login: `login_success`
- After failed login (user found, wrong password): `login_failure`
- After successful password reset: `password_reset`
- After email verification confirmed: `email_verify`
- After logout (token revoked): `logout`

The audit log is write-only from the application. There is no read API in MU6; viewing the log requires direct DB access. An admin API for log review is deferred.

---

### D8: `/health` and `/ready` probes

**Decision:** A new `oscilla/routers/health.py` router provides two endpoints:

- `GET /health` — always returns `{"status": "ok"}` with HTTP 200. If the process is alive, this succeeds. No DB, no cache.
- `GET /ready` — performs a lightweight DB query (`SELECT 1`) and a cache ping. Returns `{"status": "ok", "db": true, "cache": true}` with HTTP 200 if both pass, or HTTP 503 with false entries for failing components.

The readiness probe is designed for orchestrators (Kubernetes, Docker Swarm, Compose health checks). Routing traffic to a pod before the DB connection is established would produce 500 errors; the readiness check prevents this.

---

### D9: Production Docker hardening

**Decision:**

1. **Non-root user:** `dockerfile.www` adds a `USER oscilla` directive after dependency installation. The `oscilla` user and group are created with a fixed UID/GID (999/999) for volume mount compatibility.

2. **Uvicorn worker configuration:** In production, Uvicorn is started with `--workers $(nproc)` (or a fixed worker count via `UVICORN_WORKERS` env var). The dev compose file uses `--reload`; the production image does not.

3. **No dev dependencies in production image:** The production Docker target uses `uv sync --no-dev` to exclude development tools (`pytest`, `ruff`, `mypy`, etc.) from the runtime image.

4. **MailHog removal from production:** `compose.yaml` gains a `dev` profile for development-only services (MailHog). The production compose target excludes the `dev` profile. `.env.example` documents the real SMTP settings required for production.

---

## New Settings

```python
# Rate limiting
max_login_attempts_per_hour: int = Field(default=10, description="Login attempts per email per hour before rate limiting.")
max_registrations_per_hour_per_ip: int = Field(default=5, description="Registration attempts per IP per hour.")

# Account lockout
max_login_attempts_before_lockout: int = Field(default=5, description="Consecutive failed logins before lockout.")
lockout_duration_minutes: int = Field(default=15, description="Duration of account lockout in minutes.")
lockout_window_seconds: int = Field(default=300, description="Window for counting consecutive failures (seconds).")

# CORS
cors_origins: List[str] = Field(default=["http://localhost:5173"], description="Allowed CORS origins.")

# Logging
log_level: str = Field(default="INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR.")

# Production Uvicorn
uvicorn_workers: int = Field(default=1, description="Number of Uvicorn worker processes.")
```

---

## Middleware Application Order

Middleware is applied to `app` in `oscilla/www.py` in this order (outermost first):

```python
app.add_middleware(RequestLoggingMiddleware)   # outermost: logs all requests
app.add_middleware(SecurityHeadersMiddleware)  # injects security headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

FastAPI applies middleware in reverse registration order (last-added is outermost). The ordering above ensures: CORS preflight is handled before security headers are checked, and logging wraps the entire request lifecycle.

---

## Alembic Migration

One new migration: `auth_audit_log` table creation. Fully additive; no existing tables modified.

---

## Testing Philosophy

- **Unit tests** for `check_rate_limit`: mock `get_cache("persistent")` to return a `NoOpCache`; verify rate limiting is disabled (always returns `True`); mock a `RedisCache` stub where increment exceeds threshold; verify returns `False`.
- **Unit tests** for `validate_password_strength`: weak passwords (dictionary words, keyboard walks) rejected; strong passwords accepted; `zxcvbn` suggestion string included in `ValueError` message.
- **Unit tests** for `SecurityHeadersMiddleware`: FastAPI `TestClient` response includes all required headers.
- **Unit tests** for `RequestLoggingMiddleware`: log output captured with `caplog`; `request_id` present in log records; `status_code` and `duration_ms` logged.
- **Integration tests** for rate-limiting behavior in login endpoint: using a real `NoOpCache` backend (default test config), verify that 100 rapid login attempts do not trigger rate limiting.
- **Integration tests** for account lockout: N failed logins followed by a lockout check; verify subsequent login returns `423 Locked`.
- **Integration tests** for `/health` and `/ready`: health always returns 200; ready returns 200 with live DB in test, 503 with disconnected DB (using a fixture that closes the DB connection).
- **Integration tests** for auth audit log: successful login creates `login_success` row; failed login creates `login_failure` row; logout creates `logout` row.
- All tests use in-memory SQLite; no Redis required in test config (`cache_enabled=False`).

---

## Documentation Plan

| Document                              | Audience               | Content                                                                                                                                                            |
| ------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docs/dev/docker.md` (update)         | Developers             | Production Docker hardening: non-root user, worker configuration, MailHog dev profile, production SMTP settings, multi-stage build with `--no-dev`                 |
| `docs/dev/api.md` (update)            | Developers             | `/health` and `/ready` endpoint documentation; response schemas; recommended orchestrator configuration                                                            |
| `docs/dev/authentication.md` (update) | Developers             | Rate limiting keys and window configuration; account lockout mechanics; auth audit log events; how to disable rate limiting in development (`cache_enabled=False`) |
| `.env.example` (update)               | Developers / Operators | All new security settings with descriptions and suggested production values                                                                                        |

---

## Risks / Trade-offs

| Risk                                                                                                    | Mitigation                                                                                                                                                                                                                                |
| ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `X-Forwarded-For` spoofing on registration IP rate limiting                                             | Document that the server must be deployed behind a trusted reverse proxy that sets `X-Real-IP`; use `request.client.host` by default; add a `trusted_proxy_ips` setting in a future change for multi-hop proxy environments               |
| `zxcvbn` library adds ~1ms to registration — acceptable but measurable                                  | Validation is only called once per registration request; not on login; not on token refresh. The cost is negligible                                                                                                                       |
| HSTS header served to developers on localhost                                                           | Browsers ignore HSTS for `localhost` and `127.0.0.1`; the header is harmless in development                                                                                                                                               |
| Audit log table grows unboundedly                                                                       | Add a `created_at` index; a future maintenance job can archive or delete rows older than 90 days. Note: deleting auth audit logs may conflict with compliance requirements in regulated deployments — this is called out in documentation |
| Account lockout via Redis is bypassed if Redis goes down (falls back to no lockout via `NoOpCache`)     | Acceptable tradeoff: a Redis outage is a partial security degradation, not a data loss event. Full lockout durability requires a DB-backed implementation, which is a future option                                                       |
| `CORSMiddleware` with `allow_credentials=True` and `allow_origins=["*"]` is a security misconfiguration | Default cors_origins is `["http://localhost:5173"]` (not `["*"]`). Settings documentation explicitly warns against wildcard origins with credentials                                                                                      |
