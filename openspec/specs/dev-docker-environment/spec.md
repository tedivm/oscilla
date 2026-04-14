# Spec: Dev Docker Environment

## Purpose

Specifies the Docker Compose development stack that provides a complete hot-reloading environment accessible at `http://localhost`. The stack includes a Caddy gateway, the Python backend, the Vite frontend dev server, a PostgreSQL database, Redis, and MailHog.

---

## Requirements

### Requirement: `docker compose up` starts a complete hot-reloading dev stack

Running `docker compose up` (with no profile flag) SHALL start all six services: `gateway`, `backend`, `frontend`, `db`, `redis`, and `mailhog`. The full application SHALL be accessible at `http://localhost` (port 80).

#### Scenario: All services start on `docker compose up`

- **WHEN** `docker compose up -d` is run from the repository root
- **THEN** all six services reach a running state without error
- **AND** `http://localhost` serves the application (redirects to `/app`)
- **AND** `http://localhost:8025` serves the MailHog web UI

---

### Requirement: Caddy gateway routes API paths to backend and all other paths to frontend

A `gateway` service using `caddy:2-alpine` SHALL route requests using exactly four prefix rules. The path prefixes `/api*`, `/static*`, `/health*`, and `/ready*` SHALL be forwarded to the `backend` service on port 8000. All other requests SHALL be forwarded to the `frontend` service on port 5173.

The Caddyfile SHALL be mounted from `docker/gateway/Caddyfile`. Caddy SHALL expose port 80 on the host. No other service SHALL expose a port on the host except `db` (if needed for local inspection tools), `redis`, and `mailhog` (ports 8025 and 1025).

#### Scenario: API request is routed to backend

- **GIVEN** `docker compose up` is running
- **WHEN** a browser makes a request to `http://localhost/api/auth/login`
- **THEN** the request reaches the FastAPI backend

#### Scenario: Frontend request is routed to Vite dev server

- **GIVEN** `docker compose up` is running
- **WHEN** a browser requests `http://localhost/app`
- **THEN** the request is served by the Vite dev server

#### Scenario: WebSocket HMR connection is proxied

- **GIVEN** `docker compose up` is running and the browser has loaded the frontend
- **WHEN** a `.svelte` source file is modified
- **THEN** the browser receives an HMR update and the page hot-reloads without a full page refresh

---

### Requirement: Backend Python source files are hot-reloaded without container restart

The `backend` service SHALL volume-mount `./oscilla` and `./db` from the host and run uvicorn with `RELOAD=true`. Changes to any `.py` file under `oscilla/` SHALL cause uvicorn to reload automatically without requiring a container restart or rebuild.

#### Scenario: Python source change reloads uvicorn

- **GIVEN** the `backend` container is running
- **WHEN** a `.py` file under `oscilla/` is saved
- **THEN** uvicorn detects the change and reloads within ~3 seconds
- **AND** the API continues to respond on the next request

---

### Requirement: Frontend SvelteKit source is hot-reloaded via Vite HMR

The `frontend` service SHALL volume-mount `./frontend` from the host and run `vite dev --host 0.0.0.0`. A Docker named volume (`frontend_node_modules`) SHALL shadow `node_modules` so that native Node binaries (compiled for Alpine Linux) are used instead of host-OS binaries.

The `HMR_CLIENT_PORT` environment variable SHALL be set to `80` on the `frontend` container so that the Vite HMR WebSocket client in the browser connects to port 80 (through Caddy) rather than the container-internal port 5173.

#### Scenario: Svelte source change hot-reloads in browser

- **GIVEN** the `frontend` container is running and the app is open in a browser
- **WHEN** a `.svelte` source file under `frontend/src/` is saved
- **THEN** the browser receives an HMR update within ~1 second without a full page reload

#### Scenario: node_modules uses container-native binaries

- **GIVEN** the `frontend` container is started on a macOS host
- **WHEN** `vite dev` starts inside the container
- **THEN** native Node binaries (esbuild, rollup) execute without `Exec format error`

---

### Requirement: `docker compose down -v` removes the named node_modules volume

The `frontend_node_modules` named volume SHALL be declared in the top-level `volumes` block of `compose.yaml`. Running `docker compose down -v` SHALL remove it.

#### Scenario: Named volume is removed with `-v` flag

- **GIVEN** `docker compose up` has been run at least once
- **WHEN** `docker compose down -v` is run
- **THEN** the `frontend_node_modules` volume is removed
- **AND** a subsequent `docker compose up` reinstalls node_modules inside a fresh volume
