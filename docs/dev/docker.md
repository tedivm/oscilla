# Docker

This project uses Docker Compose as the primary developer workflow. Running `docker compose up` starts a complete hot-reloading full-stack environment — no manual backend or frontend startup required.

For deploying to production, see [Hosting: Deployment](../hosting/deployment.md).

## Quick Start

```bash
cp .env.example .env          # First time only
docker compose up             # Start everything
docker compose down           # Stop (preserves volumes)
docker compose down -v        # Stop and delete all volumes
```

The application is accessible at `http://localhost` once all services are up.
MailHog (email catcher) is available at `http://localhost:8025`.

## Service Topology

```
host port 80
     │
  gateway          (caddy:2-alpine)
     │
     ├── /api*     →  backend:8000   (FastAPI + uvicorn)
     ├── /static*  →  backend:8000
     ├── /health*  →  backend:8000
     ├── /ready*   →  backend:8000
     └── *         →  frontend:5173  (Vite dev server + SvelteKit HMR)
```

| Service    | Role                            | Host port     |
| ---------- | ------------------------------- | ------------- |
| `gateway`  | Caddy reverse proxy             | 80            |
| `backend`  | FastAPI (Python, uvicorn)       | internal only |
| `frontend` | Vite dev server (SvelteKit HMR) | internal only |
| `db`       | PostgreSQL                      | internal only |
| `redis`    | Redis cache                     | internal only |
| `mailhog`  | Email catcher (SMTP + web UI)   | 8025, 1025    |

## Hot Reload

Both the backend and frontend support live code reloading — no container restarts needed.

**Python (backend):** The `./oscilla` directory is volume-mounted into the container. Uvicorn runs with `RELOAD=true` and watches for `.py` changes. Save a file → uvicorn reloads within ~2 seconds.

**SvelteKit (frontend):** The `./frontend` directory is volume-mounted into the frontend container. Vite's HMR pushes changes to the browser within ~1 second. No page refresh required.

### HMR Through the Proxy

Vite's HMR uses a WebSocket connection. When running behind a reverse proxy, the browser-side HMR client must connect on the proxy's port (80) rather than Vite's internal port (5173). The `HMR_CLIENT_PORT=80` environment variable on the frontend container tells Vite to configure the client accordingly.

### node_modules Named Volume

The `frontend_node_modules` named volume shadows the `node_modules` directory inside the container. This is required because:

- The host (`./frontend/node_modules`) contains macOS binaries (esbuild, rollup).
- The container runs Alpine Linux, which needs Linux binaries.
- Without the named volume, native tooling fails with `Exec format error`.

**After changing `package.json`** you need to rebuild the frontend image to reinstall dependencies:

```bash
docker compose build frontend
docker compose up -d frontend
```

Running `docker compose down -v` removes the named volume; the next `docker compose up` reinstalls from scratch.

## Dockerfile Stages

The `Dockerfile` uses three named stages:

| Stage            | Based on            | Contains                       |
| ---------------- | ------------------- | ------------------------------ |
| `frontend-build` | `node:22-alpine`    | SvelteKit build output         |
| `backend`        | python-uvicorn base | Python app, no frontend assets |
| `production`     | `backend`           | Python app + frontend assets   |

`compose.yaml` targets the `backend` stage. `docker build .` (default) targets `production`, which is the image published to GHCR.

```bash
# Build what compose uses (backend stage — no frontend assets baked in)
docker compose build

# Build the production image (all stages including frontend)
docker build .

# Verify backend stage does NOT include frontend
docker build --target backend -t oscilla-backend-test .
docker run --rm oscilla-backend-test ls /app/frontend/build  # should 404
```

## Caddyfile Routing

The Caddyfile lives at `docker/gateway/Caddyfile`. It contains exactly four routing rules:

```
/api*     → backend:8000   (all API routes)
/static*  → backend:8000   (static assets served by FastAPI)
/health*  → backend:8000   (health probes, always at root)
/ready*   → backend:8000   (readiness probe, always at root)
*         → frontend:5173  (everything else = SvelteKit)
```

Because all API routes live under `/api`, adding a new FastAPI router does **not** require any Caddyfile update. The single `/api*` rule covers all current and future API paths.

## MailHog

MailHog starts with plain `docker compose up` — no profile flag required. It captures all outbound SMTP traffic so no real email is sent during development.

| URL                     | Purpose                     |
| ----------------------- | --------------------------- |
| `http://localhost:8025` | Web UI (view captured mail) |
| `localhost:1025`        | SMTP endpoint               |

Point the application at MailHog in `.env`:

```ini
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USE_TLS=false
SMTP_FROM_ADDRESS=oscilla@localhost
```

## Prestart Script

`docker/www/prestart.sh` runs automatically before uvicorn starts. It:

1. Waits for PostgreSQL to accept connections (polls with `netcat`).
2. Runs `alembic upgrade head` to apply any pending migrations.
3. If `CREATE_TEST_DATA=true` is set, seeds the database with fake data.

## GitHub Actions

The [`.github/workflows/docker.yaml`](.github/workflows/docker.yaml) workflow builds and publishes the production image to GHCR on every push to `main` and on version tags.

Published image: `ghcr.io/tedivm/oscilla`

Tags published:

- Branch name (e.g. `main`)
- PR number (e.g. `pr-42`)
- Semver version on tags (e.g. `1.2.3`, `1.2`, `1`)

## Common Commands

```bash
# Start all services (foreground)
docker compose up

# Start detached
docker compose up -d

# Rebuild images after code changes to Dockerfile or package.json
docker compose build

# Follow logs
docker compose logs -f
docker compose logs -f backend

# Open a shell in a running container
docker compose exec backend bash
docker compose exec frontend sh

# Run a database migration
docker compose exec backend python -m alembic upgrade head

# Stop services (keep volumes)
docker compose down

# Stop services and remove all volumes (full reset)
docker compose down -v
```

## Troubleshooting

**Port 80 already in use:** Change `"80:80"` to e.g. `"8080:80"` in `compose.yaml` under the `gateway` service.

**Frontend changes not hot-reloading:** Check that the browser console doesn't show a WebSocket error. If `HMR_CLIENT_PORT` is not set on the `frontend` container, the HMR socket tries port 5173 (not exposed), and HMR silently fails. The value must be `80`.

**`Exec format error` on npm start:** The named `frontend_node_modules` volume is missing or was built on a different platform. Run `docker compose down -v && docker compose up` to rebuild it.

**Caddyfile syntax error:** Validate with:

```bash
docker run --rm -v "$(pwd)/docker/gateway/Caddyfile:/etc/caddy/Caddyfile" caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile
```

## References

- [Caddy Documentation](https://caddyserver.com/docs/)
- [Multi-Py Uvicorn Images](https://github.com/multi-py/python-uvicorn)
- [Vite Server Options (HMR)](https://vitejs.dev/config/server-options.html#server-hmr)
