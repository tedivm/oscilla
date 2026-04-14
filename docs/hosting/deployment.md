# Deployment Guide

This guide covers deploying Oscilla using the pre-built container image from the GitHub Container Registry (GHCR).

## Prerequisites

- Docker and Docker Compose (or an equivalent container runtime)
- A PostgreSQL database
- A Redis instance
- (Optional) An SMTP server for email verification and password reset

## Container Image

The official production image is published on each tagged release:

```
ghcr.io/tedivm/oscilla:latest
```

The image bundles the Python backend (FastAPI/Uvicorn) and compiled frontend assets.
It exposes port `8000`.

## Environment Variables

All configuration is supplied via environment variables. Copy `.env.example` from the
repository as a starting point.

### Required

| Variable       | Description                                                                                                                                  |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL` | Full async-driver database connection URL. Must use the `postgresql+asyncpg` driver, e.g. `postgresql+asyncpg://user:pass@host:5432/dbname`. |
| `JWT_SECRET`   | Long random string used to sign JWT access tokens and HMAC verification tokens. Generate with `openssl rand -hex 64`.                        |

### Database

| Variable       | Default           | Description                                    |
| -------------- | ----------------- | ---------------------------------------------- |
| `DATABASE_URL` | SQLite (dev only) | PostgreSQL async URL (required in production). |

### Cache / Redis

| Variable           | Default                       | Description                                         |
| ------------------ | ----------------------------- | --------------------------------------------------- |
| `CACHE_REDIS_HOST` | _(unset — uses memory cache)_ | Redis hostname. Set to enable Redis-backed caching. |
| `CACHE_REDIS_PORT` | `6379`                        | Redis port.                                         |
| `CACHE_ENABLED`    | `true`                        | Set to `false` to disable caching entirely.         |

### Authentication

| Variable                            | Default      | Description                                                  |
| ----------------------------------- | ------------ | ------------------------------------------------------------ |
| `JWT_SECRET`                        | _(required)_ | Secret for JWT and HMAC token signing.                       |
| `ACCESS_TOKEN_EXPIRE_MINUTES`       | `15`         | JWT access token lifetime in minutes.                        |
| `REFRESH_TOKEN_EXPIRE_DAYS`         | `30`         | Refresh token lifetime in days.                              |
| `REQUIRE_EMAIL_VERIFICATION`        | `false`      | When `true`, unverified accounts cannot access game content. |
| `EMAIL_VERIFY_TOKEN_EXPIRE_HOURS`   | `24`         | Email verification link lifetime.                            |
| `PASSWORD_RESET_TOKEN_EXPIRE_HOURS` | `1`          | Password reset link lifetime.                                |

### Email (SMTP)

Required when `REQUIRE_EMAIL_VERIFICATION=true` or password reset is in use.

| Variable            | Default                 | Description                                                                                             |
| ------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------- |
| `SMTP_HOST`         | _(unset)_               | SMTP server hostname.                                                                                   |
| `SMTP_PORT`         | `587`                   | SMTP server port.                                                                                       |
| `SMTP_USER`         | _(unset)_               | SMTP authentication username.                                                                           |
| `SMTP_PASSWORD`     | _(unset)_               | SMTP authentication password.                                                                           |
| `SMTP_FROM_ADDRESS` | _(unset)_               | From address on all outbound emails.                                                                    |
| `SMTP_USE_TLS`      | `true`                  | Enable STARTTLS.                                                                                        |
| `BASE_URL`          | `http://localhost:8000` | Base URL used to build absolute links in emails. Set to your public domain, e.g. `https://example.com`. |

### Performance

| Variable          | Default | Description                                                             |
| ----------------- | ------- | ----------------------------------------------------------------------- |
| `UVICORN_WORKERS` | `1`     | Number of Uvicorn worker processes. Recommended: `(2 × CPU cores) + 1`. |

### Security Limits

| Variable                            | Default | Description                                                    |
| ----------------------------------- | ------- | -------------------------------------------------------------- |
| `MAX_LOGIN_ATTEMPTS_PER_HOUR`       | `10`    | Failed login attempts per email per hour before rate limiting. |
| `MAX_REGISTRATIONS_PER_HOUR_PER_IP` | `5`     | Registration attempts per IP per hour.                         |
| `MAX_LOGIN_ATTEMPTS_BEFORE_LOCKOUT` | `5`     | Consecutive failed logins before account lockout.              |
| `LOCKOUT_DURATION_MINUTES`          | `15`    | Account lockout duration in minutes.                           |

## Running Database Migrations

Run migrations before starting the container (or in an init container / release job):

```bash
docker run --rm \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname \
  ghcr.io/tedivm/oscilla:latest \
  oscilla db upgrade
```

## Starting the Container

A minimal `docker-compose.yml` for production:

```yaml
services:
  app:
    image: ghcr.io/tedivm/oscilla:latest
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://user:pass@db:5432/oscilla
      JWT_SECRET: "your-long-random-secret-here"
      CACHE_REDIS_HOST: redis
      BASE_URL: https://example.com
      UVICORN_WORKERS: 3
    depends_on:
      - db
      - redis

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: oscilla
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

volumes:
  pgdata:
```

## Reverse Proxy (Recommended)

In production the container should sit behind a reverse proxy (Caddy, Nginx, Traefik, etc.)
that handles TLS termination and routes traffic to port `8000`.

### URL Layout

All application routes are under the `/api` prefix:

| Path                  | Description                        |
| --------------------- | ---------------------------------- |
| `/api/docs`           | Swagger UI                         |
| `/api/redoc`          | ReDoc                              |
| `/api/openapi.json`   | OpenAPI schema                     |
| `/api/auth/...`       | Auth endpoints                     |
| `/api/games/...`      | Game management                    |
| `/api/characters/...` | Character management               |
| `/health`             | Liveness probe (no `/api` prefix)  |
| `/ready`              | Readiness probe (no `/api` prefix) |
| `/static/...`         | Static file assets                 |
| `/app`                | Compiled Svelte frontend           |

### Example Caddyfile

```caddyfile
example.com {
    reverse_proxy app:8000
}
```

## Health Probes

| Endpoint      | Purpose                                                   |
| ------------- | --------------------------------------------------------- |
| `GET /health` | Liveness — returns `200` when the process is running.     |
| `GET /ready`  | Readiness — returns `200` when the database is reachable. |

These endpoints intentionally have **no `/api` prefix** so they work with standard
Kubernetes/container orchestrator conventions.

## Content Packages

By default the container serves the `content/` directory bundled in the image.
To mount an external game library, set the `GAMES_PATH` environment variable and
bind-mount your library into the container:

```yaml
environment:
  GAMES_PATH: /games
volumes:
  - /path/to/your/games:/games:ro
```
