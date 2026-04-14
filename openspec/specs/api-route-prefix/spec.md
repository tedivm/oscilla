# Spec: API Route Prefix

## Purpose

Specifies that all FastAPI application API routes are mounted under the `/api` prefix, and that the frontend API client, Vite dev proxy, and Python test suite are all updated to match.

---

## Requirements

### Requirement: All application API routes live under the `/api` prefix

Every FastAPI router that serves application data SHALL be mounted with a `/api` prefix.
The `/health` and `/ready` health probe endpoints SHALL remain at the root (no prefix) — these are consumed by container orchestrators, not application clients.

Routers affected:

- `auth_router` → `/api/auth`
- `games_router` → `/api/games`
- `characters_router` → `/api/characters`
- `play_router` → `/api` (routes within the router already include `/characters/{id}/play/...`)
- `overworld_router` → `/api` (routes within the router already include `/characters/{id}/overworld`)

#### Scenario: Auth endpoint is accessible under `/api`

- **GIVEN** the backend is running
- **WHEN** a client sends `POST /api/auth/register`
- **THEN** the response is `200 OK` (or `201 Created`)

#### Scenario: Health probe is accessible at root

- **GIVEN** the backend is running
- **WHEN** a client sends `GET /health`
- **THEN** the response is `200 OK`
- **AND** no `/api/health` endpoint exists

---

### Requirement: FastAPI docs are served under `/api/docs`

The FastAPI application SHALL be instantiated with:

- `docs_url="/api/docs"` — Swagger UI
- `redoc_url="/api/redoc"` — ReDoc UI
- `openapi_url="/api/openapi.json"` — OpenAPI schema

The default FastAPI locations (`/docs`, `/redoc`, `/openapi.json`) SHALL NOT be served.

#### Scenario: Swagger UI is accessible at `/api/docs`

- **GIVEN** the backend is running
- **WHEN** a browser navigates to `/api/docs`
- **THEN** the Swagger UI is displayed

---

### Requirement: `GET /api` redirects to `/api/docs`

A dedicated route `GET /api` (excluded from the OpenAPI schema) SHALL return a `307 Temporary Redirect` or `302 Found` to `/api/docs`.

#### Scenario: `/api` redirects to docs

- **GIVEN** the backend is running
- **WHEN** a client sends `GET /api`
- **THEN** the response is a redirect to `/api/docs`

---

### Requirement: Frontend API client uses `/api` prefix for all calls

Every `apiFetch` call in the frontend source SHALL use a path beginning with `/api/`. No bare router prefix paths (`/auth/...`, `/games/...`, `characters/...`) SHALL remain in any file under `frontend/src/`.

The token refresh guard in `frontend/src/lib/api/client.ts` that compares `path === "/auth/refresh"` SHALL be updated to `path === "/api/auth/refresh"`.

#### Scenario: Frontend login request targets `/api/auth/login`

- **GIVEN** the SvelteKit frontend is running
- **WHEN** a user submits the login form
- **THEN** the browser network tab shows a request to `/api/auth/login`

---

### Requirement: Vite dev proxy covers `/api` and `/static` — not individual path prefixes

The `server.proxy` configuration in `vite.config.ts` SHALL proxy exactly two path patterns:

- `/api` → `http://localhost:8000`
- `/static` → `http://localhost:8000`

The four-entry proxy (`/auth`, `/games`, `/characters`, `/overworld`) previously used SHALL be removed.

#### Scenario: API call during `vite dev` reaches backend

- **GIVEN** `make frontend_dev` is running alongside `uvicorn`
- **WHEN** the browser makes a request to `/api/auth/login`
- **THEN** the Vite proxy forwards it to `http://localhost:8000/api/auth/login`

---

### Requirement: Python test suite uses `/api` prefixed paths

All test client calls in `tests/routers/` (and any other test file making HTTP calls to the app) SHALL use paths beginning with `/api/`. No bare prefix paths SHALL be present in the test files after migration.

#### Scenario: Auth test uses `/api` path

- **GIVEN** the test client is pointed at the FastAPI test app
- **WHEN** the test calls `client.post("/api/auth/register", ...)`
- **THEN** the test passes with no path-not-found errors

---

### Requirement: Existing auth, games, characters, play, and overworld endpoints remain accessible

All existing API endpoint functionality SHALL be preserved. Only the URL prefix changes — from `/auth/*`, `/games/*`, `/characters/*` to `/api/auth/*`, `/api/games/*`, `/api/characters/*`. Response schemas, status codes, and authentication requirements SHALL be unchanged.

#### Scenario: All existing endpoints are reachable under `/api`

- **GIVEN** the backend is running with `/api` prefixed routers
- **WHEN** a test suite is run against the application
- **THEN** all API tests that previously used bare paths now pass with `/api` prefixed paths
