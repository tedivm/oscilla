# Frontend

The frontend is a SvelteKit SPA mounted by FastAPI at `/app`, with all browser assets built into `frontend/build` and served as static files.

## Project Layout

The frontend code lives under `frontend/`.

- `frontend/src/routes/`: Route files (`+layout.svelte`, `+page.svelte`, dynamic route folders).
- `frontend/src/lib/components/`: Shared UI components and panel components.
- `frontend/src/lib/stores/`: Writable stores (`authStore`, `themeStore`) used by routes and API client code.
- `frontend/src/lib/api/`: Typed API models and endpoint wrappers (`client.ts`, `auth.ts`, `games.ts`, `characters.ts`).
- `frontend/src/lib/theme/`: Tokenized CSS variables in `tokens.css`.
- `frontend/static/`: Static passthrough files copied into the final build.
- `frontend/tests/`: Playwright accessibility and E2E tests.
- `frontend/playwright.config.ts`: Playwright accessibility test config.
- `frontend/playwright.e2e.config.ts`: Playwright E2E config (no webServer block).

## Local Development

1. Run `make install` at the repo root to install Python and frontend dependencies.
2. Run `docker compose up -d` to start backend dependencies.
3. Run `make frontend_dev` to start the SvelteKit dev server.
4. Run `uv run uvicorn oscilla.www:app --reload` (or your normal API run command) for the backend.

The Vite dev proxy forwards `/auth`, `/games`, `/characters`, and `/overworld` to `http://localhost:8000`.

## Architecture Decisions

- `adapter-static` is used so the app can be served by FastAPI `StaticFiles` without a Node runtime in production.
- `paths.base = '/app'` keeps every frontend route and asset URL scoped under the backend mount path.
- SSR is disabled (`ssr = false`, `prerender = false`) to run the frontend as a client-side SPA.
- Visual styling uses CSS custom properties in `src/lib/theme/tokens.css`; components consume tokens rather than hardcoded values.

## Adding New Pages

- Place new route files under `frontend/src/routes/` using SvelteKit naming (`+page.svelte`, `+layout.svelte`, `[id]/+page.svelte`).
- Use the three-state async pattern for fetch-heavy pages:
  - `loading === true`: render `LoadingSpinner`.
  - `error !== null`: render `ErrorBanner`.
  - Success: render page content.
- Use `base` from `$app/paths` when constructing route links and `goto(...)` navigation targets.
- Protected routes rely on the auth guard in root layout; keep new protected routes under `/games` or `/characters` unless guard logic is explicitly updated.

## Adding New Components

- Place shared components in `frontend/src/lib/components/`.
- Place character-sheet panel components in `frontend/src/lib/components/panels/`.
- Export reusable components from `frontend/src/lib/components/index.ts`.
- Type props explicitly in each `.svelte` file.

## API Client Conventions

- Always call backend endpoints through `apiFetch` from `src/lib/api/client.ts`.
- Add endpoint modules by domain (`api/foo.ts`) and keep request/response typing in `api/types.ts`.
- `authStore` owns token lifecycle (login/register/logout/refresh/init).
- Access token is in-memory only; refresh token is persisted in `sessionStorage`.

## Testing Conventions

- Unit tests: `vitest` for store and API-client behavior (`src/**/*.test.ts`).
- Component tests: Testing Library for Svelte components/routes where Vitest runtime support is available.
- Accessibility tests: Playwright + axe in `frontend/tests/accessibility.test.ts`.
- E2E tests: Playwright in `frontend/tests/e2e/` run with `make frontend_e2e` against a live stack.
- Full E2E orchestration: `make frontend_e2e_stack`.

## CI and Validation

Frontend checks are integrated into Make targets:

- `make frontend_check`: `svelte-check` type and diagnostics validation.
- `make frontend_test`: Vitest suite.
- `make frontend_format_check`: Prettier formatting check for `frontend/src`.
- `make frontend_format_fix`: Prettier auto-fix for `frontend/src`.

`make tests` includes `frontend_check` and `frontend_test`, so backend and frontend validation run together.
