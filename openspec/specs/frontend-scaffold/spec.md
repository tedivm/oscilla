# Frontend Scaffold

## Purpose

Specifies the SvelteKit project structure, the `adapter-static` build configuration, the Python-side `StaticFiles` mount, the Docker multi-stage build extension, and the Makefile integration that establishes the foundation every other MU4 spec builds on.

---

## Requirements

### Requirement: SvelteKit project at `frontend/` with adapter-static

A SvelteKit 2.x + Svelte 5 project SHALL be scaffolded in `frontend/` at the repository root using `npx sv create`. It SHALL be configured with `@sveltejs/adapter-static` so that `npm run build` produces a static directory ready to be served by FastAPI's `StaticFiles`.

`svelte.config.js` SHALL set:

- `adapter({ fallback: 'index.html' })` — the single fallback HTML file that FastAPI's `StaticFiles(html=True)` serves for all unmatched paths, enabling the SvelteKit client-side router to handle navigation.
- `paths: { base: '/app' }` — all generated asset URLs and route links are prefixed with `/app`, matching how FastAPI mounts the directory.

`frontend/src/routes/+layout.ts` SHALL export `export const ssr = false` and `export const prerender = false` to disable SSR for all routes. This is required because `adapter-static` without SSR means every page is rendered exclusively in the browser and no server exists to handle SSR requests.

#### Scenario: Build output is a static directory

- **WHEN** `npm run build` is run inside `frontend/`
- **THEN** `frontend/build/` is created and contains `index.html`, `_app/` directory with hashed JS and CSS chunks, and no Node.js server files.

#### Scenario: Fallback serves SPA for unknown paths

- **GIVEN** FastAPI mounts `frontend/build` at `/app` with `StaticFiles(html=True)`
- **WHEN** the browser GETs `/app/characters/some-uuid`
- **THEN** FastAPI serves `frontend/build/index.html` (since no file matches that path) and the SvelteKit router handles the route client-side.

---

### Requirement: `frontend_build_path` setting in `oscilla/conf/settings.py`

A `frontend_build_path: Path` field SHALL be added to the `Settings` class with:

- `default=Path("frontend/build")`
- A `description` explaining that the path is resolved relative to the working directory at startup, and that when the directory does not exist the `/app` route is not mounted.

#### Scenario: Setting resolves relative to working directory

- **WHEN** the server starts with `FRONTEND_BUILD_PATH` unset
- **THEN** `settings.frontend_build_path` is `Path("frontend/build")`
- **AND** `settings.frontend_build_path.resolve()` is the absolute path rooted at the process working directory.

---

### Requirement: `oscilla/www.py` mounts the frontend build at `/app`

After all API routers are registered, `www.py` SHALL:

1. Resolve `settings.frontend_build_path` to an absolute path.
2. If the directory exists, mount it with `StaticFiles(directory=..., html=True)` at `/app` and log INFO.
3. If the directory does not exist, log WARNING and skip the mount (so `/app` returns 404 rather than crashing startup).
4. Replace the existing root `GET /` redirect target from `/docs` to `/app`.

This is a graceful degradation: Python-only development without running the frontend build is unaffected.

#### Scenario: Root redirect points to frontend

- **GIVEN** the server is running
- **WHEN** a browser GETs `/`
- **THEN** the response is `302 Found` with `Location: /app`

#### Scenario: Startup proceeds without frontend build

- **GIVEN** `settings.frontend_build_path` points to a non-existent directory
- **WHEN** the server starts
- **THEN** startup succeeds without error
- **AND** a WARNING log entry is emitted naming the missing path
- **AND** `GET /app` returns a 404 (or 307 to login, depending on browser) rather than a 500.

---

### Requirement: Vite dev proxy for API routes

`vite.config.ts` SHALL configure a `server.proxy` that forwards all requests whose paths begin with `/auth`, `/games`, and `/characters` to `http://localhost:8000` when running `npm run dev`. This eliminates any CORS configuration in both development and production: from the browser's perspective, the Vite dev server (`localhost:5173`) and the API share a single origin.

#### Scenario: API call from Vite dev server reaches FastAPI

- **GIVEN** `npm run dev` is running and FastAPI is running on port 8000
- **WHEN** the browser POSTs to `/auth/login` via `localhost:5173`
- **THEN** Vite proxies the request to `http://localhost:8000/auth/login` transparently
- **AND** the browser never makes a cross-origin request.

---

### Requirement: Docker multi-stage build prepends a Node build stage

`dockerfile.www` SHALL be updated with a `FROM node:22-alpine AS frontend-build` stage that:

1. Copies `frontend/package.json` and `frontend/package-lock.json`.
2. Runs `npm ci`.
3. Copies `frontend/` and runs `npm run build`.

The existing Python runtime stage SHALL receive one new line:

```dockerfile
COPY --from=frontend-build /frontend/build /app/frontend/build
```

All other lines in the Python stage remain unchanged.

#### Scenario: Docker image contains frontend build

- **GIVEN** a Docker image built with `docker build -f dockerfile.www .`
- **WHEN** the container starts
- **THEN** `GET /app` serves the SvelteKit landing page
- **AND** `GET /auth/me` (unauthenticated) returns `401`, confirming the API is also live.

---

### Requirement: Makefile frontend targets

The `makefile` SHALL define the following targets:

| Target               | Command                                                    |
| -------------------- | ---------------------------------------------------------- |
| `frontend-install`   | `cd frontend && npm ci`                                    |
| `frontend-build`     | `cd frontend && npm run build`                             |
| `frontend-dev`       | `cd frontend && npm run dev`                               |
| `frontend-typecheck` | `cd frontend && npx svelte-check --tsconfig tsconfig.json` |
| `frontend-lint`      | `cd frontend && npx eslint .`                              |
| `frontend-lint-fix`  | `cd frontend && npx eslint . --fix`                        |

`frontend-typecheck` and `frontend-lint` SHALL be added to the `tests` target. `frontend-lint-fix` SHALL be added to the `chores` target. `frontend-install` SHALL be added as a prerequisite of the `install` target so that a fresh checkout sets up both Python and Node dependencies with one command.

#### Scenario: `make tests` includes frontend checks

- **WHEN** `make tests` is run from the repository root
- **THEN** `svelte-check` and ESLint are invoked against the `frontend/` directory in addition to all Python checks
- **AND** any TypeScript type error or ESLint violation fails the build.
