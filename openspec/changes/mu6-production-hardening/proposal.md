# Proposal: MU6 — Production Hardening

## Why

Phases MU1–MU5 deliver a fully functional web platform, but several security controls, operational necessities, and deployment concerns are deferred until a working game loop exists to test against. This change hardens the platform for production deployment: rate limiting, security headers, CORS, account lockout, structured logging, audit trail, and health endpoints.

Rate limiting uses the existing `aiocache` Redis backend (`get_cache("persistent")`) rather than a separate Redis client. The `RedisCache.increment()` method maps directly to the Redis `INCR` command and supports TTL expiry, making it a natural fit for sliding-window counters. No new Redis dependency or connection pool is introduced — the same connection aiocache already manages is reused.

## What Changes

- **New**: Rate limiting on auth endpoints — failed login lockout and registration throttle implemented via atomic increments on the `"persistent"` aiocache alias (`RedisCache.increment()` + TTL). Falls back gracefully to no-op when `cache_enabled=False` (the `NoOpCache` increment always returns 0, so rate limiting is effectively disabled in development without code changes).
- **New**: Account lockout after N failed login attempts (configurable via settings); lockout duration configurable.
- **New**: CORS middleware with allowlist origins (configured via settings).
- **New**: Security headers middleware: HSTS, `X-Content-Type-Options`, `X-Frame-Options`, Content Security Policy.
- **New**: Password strength validation at registration — minimum entropy check, not just minimum length.
- **New**: Structured request logging — each request logged with request ID, authenticated user ID (if any), endpoint, and outcome.
- **New**: Auth audit log — login, logout, password reset, email verification events recorded with timestamp, user ID, and IP address.
- **New**: `GET /health` — liveness probe (returns 200 if process is alive).
- **New**: `GET /ready` — readiness probe (returns 200 only when DB and Redis connections are healthy).
- **New**: Production Docker image hardened: no hot-reload, proper Uvicorn worker configuration, non-root user.
- **New**: MailHog removed from production `compose.yaml`; production SMTP settings documented in `.env.example`.
- **Updated**: Settings additions: `cors_origins` (list), `max_login_attempts`, `lockout_duration_minutes`, `log_level`.

## Capabilities

### New Capabilities

- `auth-rate-limiting`: Brute-force protection on login and registration endpoints via Redis-backed counters.
- `account-lockout`: Temporary account lockout after configurable failed login threshold.
- `security-headers`: Standard OWASP-recommended response headers applied to all API responses.
- `auth-audit-log`: Tamper-evident record of authentication events for security review.
- `health-probes`: Standard liveness and readiness endpoints for orchestration (Kubernetes, Docker Swarm, load balancers).

## Impact

- `oscilla/www.py` — CORS middleware, security headers middleware, rate limiting middleware mounted
- `oscilla/services/auth.py` — account lockout logic; audit log writes
- `oscilla/routers/health.py` — new file: `/health` and `/ready` endpoints
- `oscilla/settings.py` — new production security settings
- `dockerfile.www` — production hardening (non-root user, Uvicorn workers, no dev-only dependencies)
- `compose.yaml` — production compose profile without MailHog
- `.env.example` — all new settings documented
- `docs/dev/docker.md` — production deployment configuration documented

## Context

- **Overall architecture:** [frontend-roadmap.md](../../../frontend-roadmap.md) — all technology decisions, the full API surface, database schema changes, and the complete implementation phase breakdown for the Multi-User Platform.
- **Depends on:** [MU5 — Web Frontend — Game Loop](../mu5-web-frontend-game-loop/proposal.md) (and all prior MU phases)
- **Next:** nothing — this is the final phase of the Multi-User Platform series.
