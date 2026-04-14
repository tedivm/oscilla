# Design: Dev Environment Overhaul

## Context

The current `compose.yaml` defines a single `www` service built from `dockerfile.www`. This service runs Python (uvicorn) and serves both the API and the compiled SvelteKit static assets. Python files are volume-mounted for hot reload (`RELOAD=true`), but the frontend is burned into the image at build time — changing any `.svelte` file requires `docker compose build && docker compose up`, which typically takes 30–60 seconds.

Additionally, `dockerfile.www` is a non-standard filename that predates a design decision to have only one container. The published container image carries a `.www` suffix (`ghcr.io/tedivm/oscilla.www`) that reflects the same historical artefact.

The goal of this change is:

1. Make `docker compose up` the complete, single dev workflow with full hot reload for both Python and SvelteKit.
2. Move all API routes under `/api` so the gateway routing rule is a single prefix match rather than an enumerated list.
3. Clean up naming artefacts (`dockerfile.www` → `Dockerfile`, image tag de-suffixed).
4. Keep the production image completely unchanged in runtime behavior.

---

## Goals / Non-Goals

**Goals:**

- `docker compose up` starts a fully functional dev environment (gateway, backend, frontend, db, redis, mailhog) on port 80.
- Python source changes reload without container restart.
- SvelteKit source changes hot-reload in the browser with no rebuild step.
- All API routes consolidated under `/api`; gateway routing is a single prefix rule, not an enumerated list.
- `GET /health` and `GET /ready` remain at root — they are infrastructure probes used by orchestrators.
- Production Docker image: same runtime, same security posture, same build artifact, just a renamed file and cleaner stage names.
- Published image name simplified: `ghcr.io/tedivm/oscilla` (no `.www`).
- CI workflow simplified: no strategy matrix.

**Non-Goals:**

- New production runtime behaviour — production serves the same compiled SPA through FastAPI `StaticFiles` as before.
- Changing the SvelteKit adapter or base path.
- SSL/TLS termination in the dev environment.
- Support for running individual services in isolation (e.g. backend-only with no gateway).
- Versioning the API (e.g. `/api/v1/`) — the prefix is `/api` with no version segment.

---

## Decisions

### D1: Caddy as the gateway — not nginx, not Traefik

**Decision:** Use `caddy:2-alpine` as the reverse proxy gateway.

**Rationale:**

- Vite's HMR communicates over a WebSocket. Caddy transparently proxies WebSocket connections with zero configuration. nginx requires explicit `Upgrade` and `Connection` header directives; any omission silently breaks HMR.
- The Caddyfile for this use case is ~15 lines. The equivalent nginx config is ~40 lines and more error-prone.
- Caddy is the same weight as nginx (`~30 MB` Alpine image). No Caddy daemon or persistent process is needed; the community `caddy:2-alpine` image is sufficient.
- Traefik would also work but is overengineered for a dev-only router with two upstreams.

**Alternative considered:** Custom nginx config. Rejected because WebSocket proxying requires explicit config that is easy to get wrong, and the config is significantly more verbose.

### D2: Named volume for `node_modules` — unavoidable for cross-platform correctness

**Decision:** Use a Docker named volume for `frontend_node_modules` mounted at `/app/node_modules` in the frontend container, while bind-mounting `./frontend:/app` for source.

**Rationale:**

When `./frontend` is bind-mounted into the container, `node_modules` from the host (macOS) is also visible to the container (Alpine Linux). Node native binaries (e.g. `esbuild`, `rollup`) are compiled for the host OS and architecture. Running them inside an Alpine container fails silently or with `Exec format error`. The named volume shadows the host's `node_modules` directory with a container-native one, without impacting source hot reload.

**Consequence:** After changing `package.json` (adding/removing deps), the developer must run `docker compose build frontend` or `docker compose down -v && docker compose up` to reinstall. This is documented.

**Alternative considered:** Copying `node_modules` into the image and not using a bind mount. Rejected because source file changes would require container restart.

### D3: HMR client port override via `HMR_CLIENT_PORT` env var

**Decision:** Add a single line to `vite.config.ts` to read `process.env.HMR_CLIENT_PORT` and pass it to `server.hmr.clientPort`.

**Rationale:**

Vite's HMR client (JavaScript injected into the browser) connects back to the dev server's WebSocket endpoint using the same port as the page was loaded from — unless `clientPort` overrides it. When Vite is behind Caddy on port 80, the browser page loads from port 80, but without `clientPort`, the HMR client tries to upgrade to a WS connection on port 5173 (the container-internal port). This is blocked — port 5173 is not exposed externally.

Setting `HMR_CLIENT_PORT=80` in the frontend container's environment, combined with the `clientPort` config, makes the browser HMR WebSocket connect to port 80, which Caddy proxies to Vite internally.

When running Vite outside Docker (e.g. `make frontend_dev`), `HMR_CLIENT_PORT` is unset; `Number(undefined)` evaluates to `NaN`, and `NaN || undefined` is `undefined`. Vite treats `undefined` as "use default" — no change to current local dev behaviour.

**vite.config.ts before:**

```typescript
const apiProxy = {
  "/auth": { target: "http://localhost:8000", changeOrigin: true },
  "/games": { target: "http://localhost:8000", changeOrigin: true },
  "/characters": { target: "http://localhost:8000", changeOrigin: true },
  "/overworld": { target: "http://localhost:8000", changeOrigin: true },
};

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    proxy: apiProxy,
  },
  preview: {
    proxy: apiProxy,
  },
  // ...
});
```

**vite.config.ts after:**

```typescript
// Single prefix covers all API routes. Health probes (/health, /ready) are
// backend-only and not called from the browser, so they don't need proxying.
const apiProxy = {
  "/api": { target: "http://localhost:8000", changeOrigin: true },
  "/static": { target: "http://localhost:8000", changeOrigin: true },
};

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    // When running behind a reverse proxy (e.g. Caddy in Docker), HMR_CLIENT_PORT
    // tells the browser which port to use for the HMR WebSocket. Without this, the
    // HMR client defaults to the Vite dev server's own port (5173), which is not
    // exposed externally. Set HMR_CLIENT_PORT=80 in the container environment.
    // When undefined, Vite uses its own port (correct for local non-Docker dev).
    hmr: {
      clientPort: Number(process.env.HMR_CLIENT_PORT) || undefined,
    },
    proxy: apiProxy,
  },
  preview: {
    proxy: apiProxy,
  },
  // ...
});
```

### D4: Dockerfile stage naming — `frontend-build`, `backend`, `production`

**Decision:** Add explicit `AS backend` to the Python stage and add a new `AS production` final stage that copies the frontend build artifact.

**Before:**

```dockerfile
FROM node:22-alpine AS frontend-build
# ... node build ...

FROM ghcr.io/multi-py/python-uvicorn:py${PYTHON_VERSION}-slim-LATEST
# ... python setup ...
COPY --from=frontend-build /app/frontend/build /app/frontend/build
```

**After:**

```dockerfile
FROM node:22-alpine AS frontend-build
# ... node build ...

FROM ghcr.io/multi-py/python-uvicorn:py${PYTHON_VERSION}-slim-LATEST AS backend
# ... python setup, NO frontend copy ...

FROM backend AS production
COPY --from=frontend-build /app/frontend/build /app/frontend/build
```

**Rationale:** `compose.yaml` dev stack targets `backend` (no frontend build needed — Vite serves dev assets). `docker build .` (default) targets the final stage (`production`), which includes the frontend. The `--target backend` flag can also be used explicitly in CI if a backend-only image is ever needed.

No change to CI `docker build` invocation — it continues to build the default (last) stage.

### D5: Caddy routing — single `/api` prefix, frontend catches the rest

**Decision:** Caddy routes `/api*`, `/static*`, `/health*`, and `/ready*` to the backend. All other requests go to the Vite frontend.

**Rationale:** With all API routes under `/api`, the Caddyfile reduces from ~10 path-specific rules to 4. New API routers added to FastAPI under the `/api` prefix require no Caddyfile change. `/health` and `/ready` remain at root because container orchestrators (Kubernetes, Docker health checks) probe these paths by convention. `/static` routes to the backend because FastAPI serves its own static assets (favicon, etc.) from that mount.

**Caddyfile:**

```caddyfile
:80 {
    # All API routes are under /api — single rule covers everything
    handle /api* {
        reverse_proxy backend:8000
    }
    # FastAPI static assets (favicon, etc.)
    handle /static* {
        reverse_proxy backend:8000
    }
    # Infrastructure health probes — stay at root by convention
    handle /health* {
        reverse_proxy backend:8000
    }
    handle /ready* {
        reverse_proxy backend:8000
    }
    # Everything else: SvelteKit app + Vite HMR WebSocket
    handle {
        reverse_proxy frontend:5173
    }
}
```

### D6: All API routes move under `/api` prefix — single cut, no compatibility shim

**Decision:** Move all API routes to `/api` in a single change. No redirects from old paths to new. Update all consumers (Python tests, frontend `apiFetch` calls, Vite proxy) atomically.

**Rationale:** A compatibility shim (redirecting `/auth/*` → `/api/auth/*`) would halve the cleanup value — the old paths would still need Caddyfile entries, and old test code would continue to pass misleadingly. Since all consumers are in this repository, a clean cut is safe and surgically verifiable by running `make tests`.

**<www.py> changes:**

```python
# Before
app = FastAPI(lifespan=lifespan)
# ...
app.include_router(health_router, tags=["health"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(games_router, prefix="/games", tags=["games"])
app.include_router(characters_router, prefix="/characters", tags=["characters"])
app.include_router(play_router, tags=["play"])
app.include_router(overworld_router, tags=["overworld"])
```

```python
# After
app = FastAPI(
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
# ...
# Health probes stay at root — container orchestrators probe /health and /ready by convention.
app.include_router(health_router, tags=["health"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(games_router, prefix="/api/games", tags=["games"])
app.include_router(characters_router, prefix="/api/characters", tags=["characters"])
# play and overworld routers use full paths hardcoded in the router file;
# they all start with /characters/... so they get the /api prefix here.
app.include_router(play_router, prefix="/api", tags=["play"])
app.include_router(overworld_router, prefix="/api", tags=["overworld"])

@app.get("/api", include_in_schema=False)
async def api_root() -> RedirectResponse:
    return RedirectResponse("/api/docs")
```

**Frontend client changes:**

Every `apiFetch("/auth/...")`, `apiFetch("/games/...")`, `apiFetch("/characters/...")` call becomes `apiFetch("/api/auth/...")` etc. The hardcoded guard in `client.ts` that checks `path === "/auth/refresh"` must also be updated to `"/api/auth/refresh"`.

Files affected:

- `frontend/src/lib/api/auth.ts`
- `frontend/src/lib/api/games.ts`
- `frontend/src/lib/api/characters.ts`
- `frontend/src/lib/api/play.ts`
- `frontend/src/lib/stores/auth.ts`
- `frontend/src/lib/api/client.ts` (the `/auth/refresh` guard)

Tests affected:

- All files under `tests/routers/` — ~132 path string occurrences across ~10 files. Each hardcoded path string (e.g. `"/auth/login"`) gains `/api` prefix.

**Edge case:** Play and overworld routers define their routes as `/characters/{id}/play/...` and `/characters/{id}/overworld` — full paths with no prefix applied in the router itself. Adding `prefix="/api"` in `www.py` makes them `/api/characters/{id}/play/...` which is the correct final path.

---

### D7: Frontend dev Dockerfile — separate file, not a stage of `Dockerfile`

**Decision:** Create `docker/frontend/Dockerfile` as a standalone Dockerfile for the dev frontend container.

**Rationale:** The dev frontend image is conceptually distinct from the production image. Embedding it as a stage in the main `Dockerfile` would pollute the production build context with dev concerns and require `--target` flags to avoid accidentally building it. A separate file is clearer and keeps `Dockerfile` focused on the production artifact.

**docker/frontend/Dockerfile:**

```dockerfile
FROM node:22-alpine

WORKDIR /app

# package files are copied for npm ci; source is bind-mounted at runtime
COPY frontend/package*.json ./

# Install dependencies into the image layer.
# node_modules is later shadowed by a named Docker volume so that
# native binaries are compiled for Alpine, not the host OS.
RUN npm ci

EXPOSE 5173

# --host 0.0.0.0 makes the dev server listen on all container interfaces,
# not just localhost, so Caddy can reach it from its own container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

### D8: MailHog always up — remove profile gate

**Decision:** Remove `profiles: [dev]` from the `mailhog` service in `compose.yaml`. MailHog starts with plain `docker compose up`.

**Rationale:** The profile gate was added to prevent MailHog from starting in production. Production deployments do not use `compose.yaml` at all — they pull and run the published container image. There is no actual production risk from the profile gate's removal. Requiring `--profile dev` for a tool that every developer needs is pure friction.

---

## compose.yaml Design

**Current structure:**

```
www (port 80) — python-uvicorn, Python + frontend static files
db — postgres
redis — redis
mailhog (profile: dev) — mail catcher
```

**New structure:**

```
gateway (port 80) — caddy, routes by path prefix
backend (internal port 8000) — python-uvicorn, API + Python hot reload
frontend (internal port 5173) — node + vite dev server, SvelteKit HMR
db — postgres
redis — redis
mailhog — mail catcher (always starts)
```

**New compose.yaml:**

```yaml
services:
  gateway:
    image: caddy:2-alpine
    ports:
      - "80:80"
    volumes:
      - "./docker/gateway/Caddyfile:/etc/caddy/Caddyfile"
    depends_on:
      - backend
      - frontend

  backend:
    build:
      dockerfile: ./Dockerfile
      target: backend
    volumes:
      - "./oscilla:/app/oscilla"
      - "./db:/app/db"
      - "./content:/app/content"
      - "./docker/www/prestart.sh:/app/prestart.sh"
    environment:
      IS_DEV: true
      RELOAD: true
      DATABASE_URL: postgresql://main:main12345@db/main
      CACHE_REDIS_HOST: redis
      CACHE_REDIS_PORT: 6379
    depends_on:
      - db
      - redis

  frontend:
    build:
      context: .
      dockerfile: ./docker/frontend/Dockerfile
    volumes:
      - "./frontend:/app"
      # Named volume shadows host node_modules with container-native binaries.
      # After changing package.json, run: docker compose build frontend
      - frontend_node_modules:/app/node_modules
    environment:
      HMR_CLIENT_PORT: 80
    depends_on:
      - backend

  redis:
    image: redis

  db:
    image: postgres
    restart: always
    environment:
      POSTGRES_PASSWORD: main12345
      POSTGRES_USER: main
      POSTGRES_DB: main

  mailhog:
    image: mailhog/mailhog
    ports:
      - "8025:8025"
      - "1025:1025"

volumes:
  frontend_node_modules:
```

---

## Dockerfile Changes

The `Dockerfile` (renamed from `dockerfile.www`) gains a `backend` stage name on the Python stage and a `production` final stage. The production artifact is byte-for-byte identical to the current `dockerfile.www` output.

```dockerfile
ARG PYTHON_VERSION=3.13

FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json /app/frontend/
RUN npm ci

COPY frontend/ /app/frontend/
RUN npm run build

# backend stage: Python runtime without the frontend build artifact.
# Used by docker compose dev stack (target: backend).
FROM ghcr.io/multi-py/python-uvicorn:py${PYTHON_VERSION}-slim-LATEST AS backend

ENV APP_MODULE=oscilla.www:app

RUN pip install --no-cache-dir uv
RUN apt-get update && apt-get install -y netcat-traditional && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_DEV=1
ENV UV_LINK_MODE=copy
ENV UV_TOOL_BIN_DIR=/usr/local/bin

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-install-project --python /usr/local/bin/python

COPY ./docker/www/prestart.sh /app/prestart.sh
COPY . /app/

RUN uv sync --frozen --no-dev --python /usr/local/bin/python

RUN groupadd -g 999 oscilla && useradd -u 999 -g 999 -s /bin/bash oscilla
USER oscilla

CMD ["/bin/bash", "-c", "WEB_CONCURRENCY=${UVICORN_WORKERS:-1} exec /start.sh"]

# production stage: extends backend with the compiled frontend SPA.
# This is the default build target (docker build .) used by CI.
FROM backend AS production

COPY --from=frontend-build /app/frontend/build /app/frontend/build
```

Note: the `backend` stage runs as the `oscilla` non-root user. The `production` stage inherits this, so the production image security posture is unchanged.

---

## GitHub Actions Workflow Changes

The `docker.yaml` workflow drops the strategy matrix (which only ever had one entry: `www`) and hardcodes the single image.

**Before (key fields):**

```yaml
strategy:
  matrix:
    image:
      - www
# ...
- name: Extract metadata (tags, labels) for Docker
  id: meta
  uses: docker/metadata-action@v6
  with:
    images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}.${{ matrix.image }}
# ...
- name: Build and push Docker image
  uses: docker/build-push-action@v7
  with:
    file: dockerfile.${{ matrix.image }}
```

**After (key fields):**

```yaml
# No strategy.matrix block
# ...
- name: Extract metadata (tags, labels) for Docker
  id: meta
  uses: docker/metadata-action@v6
  with:
    images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
# ...
- name: Build and push Docker image
  uses: docker/build-push-action@v7
  with:
    file: Dockerfile
```

---

## Risks / Trade-offs

- **`node_modules` volume gotcha** → If `package.json` changes, the developer must run `docker compose build frontend` or `docker compose down -v`. Mitigated by clear documentation in `docs/dev/docker.md` and `docs/dev/README.md`.
- **Caddyfile API route maintenance** → New API prefixes added to FastAPI must also be added to the Caddyfile, or they will be routed to the frontend (404). Mitigated by documenting this in `docs/dev/docker.md` and `AGENTS.md`.
- **Breaking image tag rename** → Any existing deployment or CI pipeline referencing `ghcr.io/tedivm/oscilla.www` will stop receiving updates. This is a single-owner repository; the risk is accepted.
- **Vite dev server exposes `--host 0.0.0.0`** → The frontend container's Vite dev server listens on all interfaces, but the port (5173) is not externally exposed in `compose.yaml` — only Caddy's port 80 is. This is only a risk if the developer explicitly exposes port 5173, which they should not.

---

## Migration Plan

1. `git mv dockerfile.www Dockerfile`
2. Update `Dockerfile` with named stages.
3. Create `docker/gateway/Caddyfile`.
4. Create `docker/frontend/Dockerfile`.
5. Update `compose.yaml`.
6. Update `frontend/vite.config.ts`.
7. Update `.github/workflows/docker.yaml`.
8. Update documentation (`docs/dev/docker.md`, `docs/dev/README.md`, `AGENTS.md`).
9. Run `make chores` and `make tests` to verify nothing is broken.
10. Manual verification: `docker compose build && docker compose up -d`, open `http://localhost`, confirm app loads, edit a `.svelte` file and confirm browser hot-updates, edit a Python file and confirm API picks up the change.

**Rollback:** `git revert` the commit. The old `dockerfile.www` is restored from git history. No state migration is required.

---

## Documentation Plan

| Document                     | Audience                 | Topics to Cover                                                                                                                                                                                                                                                                                                                                                                                  |
| ---------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docs/dev/docker.md`         | Developers               | New service topology (gateway/backend/frontend), Caddyfile routing, `node_modules` named volume caveat, Caddyfile does NOT need updating when new API routes are added (single `/api*` rule), renamed Dockerfile, new image tag, `docker compose up` as full dev stack                                                                                                                           |
| `docs/dev/api.md`            | Developers               | New `/api` prefix convention, base URL structure (`/api/<router>/<resource>`), docs at `/api/docs`, health probes at `/health` and `/ready` (no prefix), how to call the API from frontend (always use `/api/` prefix)                                                                                                                                                                           |
| `docs/dev/README.md`         | Developers               | Quick start updated to `docker compose up` only, correct URLs (port 80 only), note about `/api/docs` for Swagger UI                                                                                                                                                                                                                                                                              |
| `AGENTS.md`                  | AI agents                | Updated Docker commands, note that all API routes live under `/api`, `/health`+`/ready` at root, `GET /api` redirects to `/api/docs`, `docker compose up` as standard dev workflow                                                                                                                                                                                                               |
| `docs/hosting/README.md`     | Operators / self-hosters | Table of contents for the hosting section; brief intro distinguishing this section from dev docs; links to deployment guide and any future hosting docs                                                                                                                                                                                                                                          |
| `docs/hosting/deployment.md` | Operators / self-hosters | How to pull the published image from GHCR (`ghcr.io/tedivm/oscilla`), required environment variables (database URL, Redis, secrets), running PostgreSQL and Redis alongside the container, health probe endpoints (`/health`, `/ready`) for load-balancer or orchestrator readiness checks, upgrading (pull new tag + restart), notes on the production image (multistage build, no dev tooling) |

---

## Testing Philosophy

This change is entirely infrastructure (Docker/Caddy/Vite config). There are no Python code changes to unit-test or integration-test. The test strategy is:

**Tier 1 — Existing automated suite (validates API route migration)**

- `make tests` continues to run against SQLite in-process, no Docker required.
- After updating all path strings in `tests/routers/` from `/auth/...` to `/api/auth/...` (etc.), `make pytest` must pass with zero failures. This is the primary correctness gate for the API route migration.
- `make frontend_test` (vitest) runs frontend unit tests without Docker.

**Tier 2 — Playwright E2E (validates frontend path changes)**

- `make frontend_e2e` runs full end-to-end tests against a managed stack. All `apiFetch` calls in frontend source must use `/api/` prefix; E2E passing confirms the frontend→backend integration is intact.

**Tier 3 — Manual Docker stack verification**

- After implementation, manually verify:
  1. `docker compose build` completes without error.
  2. `docker compose up -d` starts all six services (gateway, backend, frontend, db, redis, mailhog).
  3. `http://localhost` loads the app (redirects to `/app`).
  4. `http://localhost/api/docs` shows the Swagger UI; `http://localhost/api` redirects there.
  5. `http://localhost/health` and `http://localhost/ready` respond at root (no `/api` prefix).
  6. `http://localhost:8025` shows MailHog UI.
  7. Editing `frontend/src/routes/+page.svelte` triggers HMR in the browser within ~1 second.
  8. Editing `oscilla/www.py` (e.g. a log statement) causes uvicorn to reload within ~2 seconds.
  9. `docker compose down` stops all services cleanly.
  10. `docker compose down -v` removes named volumes including `frontend_node_modules`.

No new automated test files are added — the infrastructure changes are validated manually and by the existing suite.

---

## Testlandia Integration

This change modifies developer tooling only — no game engine features, no content schema changes, no new manifest kinds. There is no applicable Testlandia content update. The Testlandia package continues to work unchanged; its purpose (engine feature QA) is orthogonal to this change.
