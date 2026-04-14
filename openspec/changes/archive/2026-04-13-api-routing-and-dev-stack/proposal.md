## Why

The current dev environment requires rebuilding the Docker image every time a frontend file changes — there is no hot reload for Svelte. Developers must also run the backend either in Docker (no Python hot reload) or manually outside Docker, making `docker compose up` an incomplete solution. This change makes `docker compose up` the single, complete developer workflow with full hot reload for both Python and SvelteKit simultaneously.

The current API surface has no consistent prefix — routes are scattered across `/auth`, `/games`, `/characters`, `/overworld`, etc. This forces any reverse proxy (Caddy in dev, a load balancer in production) to enumerate every route prefix explicitly, making routing brittle and requiring updates every time a new API router is added. Moving all API routes under `/api` reduces the gateway to a single rule, and makes the API surface unambiguous.

Additionally, the production Dockerfile is named `dockerfile.www` and the published container image is tagged with a `.www` suffix — both artefacts of an earlier multi-container design that no longer applies. These are cleaned up here.

## What Changes

- **New**: Caddy reverse-proxy gateway container routes `/api/*`, `/static/*`, `/health`, `/ready` to the backend and everything else to the Vite frontend, exposing everything on port 80
- **New**: Dedicated dev-only frontend container (`node:22-alpine` + Vite dev server) with hot module replacement working through the gateway on port 80
- **BREAKING**: All API routes move under `/api` prefix: `/auth/*` → `/api/auth/*`, `/games/*` → `/api/games/*`, `/characters/*` → `/api/characters/*`, `/overworld` → `/api/...` — affects all API consumers including the frontend client and the test suite
- **BREAKING**: FastAPI docs move to `/api/docs` (from `/docs`); `GET /api` redirects to `/api/docs`
- **Modified**: `/health` and `/ready` remain at root — they are infrastructure probes, not public API
- **Modified**: Vite dev proxy simplifies from four explicit path entries to a single `/api` prefix
- **Modified**: Backend container (`dockerfile.www` / `Dockerfile`) renamed and gains explicit named stages (`frontend-build`, `backend`, `production`) so `compose.yaml` can target the `backend` stage — production build behavior is unchanged
- **Modified**: `compose.yaml` replaces the single `www` service with `gateway`, `backend`, and `frontend`; removes the MailHog `profiles` gate so it starts by default
- **Modified**: `frontend/vite.config.ts` adds an `HMR_CLIENT_PORT` env-var hook so the Vite HMR WebSocket client connects to port 80 (through Caddy) rather than the container-internal port 5173
- **BREAKING**: `dockerfile.www` → `Dockerfile` (standard Docker naming)
- **BREAKING**: Published image name changes from `ghcr.io/tedivm/oscilla.www` to `ghcr.io/tedivm/oscilla` (drops the `.www` suffix)
- **Modified**: GitHub Actions `docker.yaml` workflow — drops the strategy matrix, hardcodes the single image, uses `Dockerfile`
- **Modified**: Developer documentation updated throughout

## Capabilities

### New Capabilities

- `dev-docker-environment`: Fully hot-reloading Docker Compose dev stack — single `docker compose up` starts gateway, backend (Python reload), frontend (Vite HMR), database, Redis, and MailHog; everything accessible on port 80
- `api-route-prefix`: All API routes consolidated under `/api`; FastAPI docs at `/api/docs`; `GET /api` redirects to docs; `/health` and `/ready` remain at root as infrastructure probes

### Modified Capabilities

- `production-docker`: Dockerfile renamed, build stages made explicit, published image name simplified; production runtime behavior unchanged
- `frontend-scaffold`: Vite dev server gains `HMR_CLIENT_PORT` configuration so HMR works when Vite is behind a reverse proxy

## Impact

- **API path changes (BREAKING)**: Every API consumer must update paths — Python test suite (~132 occurrences), frontend `apiFetch` calls (7 files), Playwright E2E helpers (0 occurrences — E2E tests use the Svelte UI only)
- **`/auth/refresh` hardcoded check in `client.ts`**: Must be updated to `/api/auth/refresh`
- **`PROTECTED_PREFIXES` in `+layout.svelte`**: These are Svelte route prefixes (`/games`, `/characters`), not API paths — unchanged
- **Vite proxy**: Simplifies from four entries (`/auth`, `/games`, `/characters`, `/overworld`) to one (`/api`)
- **`dockerfile.www` → `Dockerfile`**: Any external script or CI step referencing `dockerfile.www` must be updated (the workflow is updated in this change)
- **Published image tag**: `ghcr.io/tedivm/oscilla.www` → `ghcr.io/tedivm/oscilla`; consumers pulling by the old name will need to update
- **compose.yaml**: Service name `www` replaced — `docker compose exec www` or similar commands will break
- **Port exposure**: Only port 80 (Caddy) is exposed; port 8000 (backend) and 5173 (frontend) are internal only
- **New files**: `docker/gateway/Caddyfile`, `docker/frontend/Dockerfile`
- **MailHog**: No longer requires `--profile dev`; starts with plain `docker compose up`
- **docs/dev/docker.md**, **docs/dev/README.md**, **AGENTS.md**: Updated to reflect new workflow
