## 1. Python Backend

- [x] 1.1 In `oscilla/conf/settings.py`, add `frontend_build_path: Path = Field(default=Path("frontend/build"), description="Path to the SvelteKit static build output. Mounted at /app by the web server.")` immediately below the existing `games_path` field; add `from pathlib import Path` to imports if not already present; add `FRONTEND_BUILD_PATH=frontend/build` with an inline comment to `.env.example`

- [x] 1.2 In `oscilla/www.py`, add `from starlette.staticfiles import StaticFiles` if not already imported; after all routers are included, add `app.mount("/app", StaticFiles(directory=str(settings.frontend_build_path), html=True), name="frontend")`; this must come **after** the API routers so API routes take precedence

- [x] 1.3 In `oscilla/www.py`, change the root redirect from `RedirectResponse(url="/docs")` to `RedirectResponse(url="/app")`; run `make pytest` to confirm no router tests break

## 2. SvelteKit Project Scaffold

- [x] 2.1 From the workspace root, run `npx sv create frontend` choosing: SvelteKit minimal template, TypeScript, no additional add-ons at init time; verify `frontend/package.json`, `frontend/svelte.config.js`, and `frontend/src/` are created

- [x] 2.2 In `frontend/`, install production and dev dependencies: `npm install` then `npm install -D @sveltejs/adapter-static vitest @vitest/coverage-v8 @testing-library/svelte @testing-library/jest-dom jsdom prettier prettier-plugin-svelte @playwright/test @axe-core/playwright`

- [x] 2.3 Update `frontend/svelte.config.js` to use `adapter-static` with `{ fallback: "index.html" }` and set `kit.paths.base = "/app"`; set `kit.appDir = "_app"` to avoid path collisions with the Python `/static` mount

- [x] 2.4 Create `frontend/src/routes/+layout.ts` with `export const ssr = false; export const prerender = false;` so the SvelteKit app operates entirely as a client-side SPA; verify that `svelte-check` reports no errors

- [x] 2.5 Update `frontend/vite.config.ts` to add a `server.proxy` block forwarding `/auth`, `/games`, `/characters`, `/characters/*`, `/overworld` to `http://localhost:8000` with `changeOrigin: true`; add `test: { environment: "jsdom", globals: true, setupFiles: ["./src/test-setup.ts"] }` to the Vite config for Vitest; create `frontend/src/test-setup.ts` importing `@testing-library/jest-dom`

- [x] 2.6 Update `frontend/tsconfig.json` to set `"strict": true`, `"moduleResolution": "bundler"`, and `"verbatimModuleSyntax": true`; confirm `svelte-check` passes

- [x] 2.7 Add a `.prettierrc` in `frontend/` with `{ "plugins": ["prettier-plugin-svelte"], "overrides": [{ "files": "*.svelte", "options": { "parser": "svelte" } }] }`

## 3. Design System

- [x] 3.1 Create `frontend/src/lib/theme/tokens.css` defining all design tokens as CSS custom properties under `:root` — include at minimum: `--color-bg`, `--color-surface`, `--color-surface-raised`, `--color-text`, `--color-text-muted`, `--color-primary`, `--color-primary-hover`, `--color-danger`, `--color-danger-hover`, `--color-success`, `--color-border`, `--radius-sm`, `--radius-md`, `--radius-lg`, `--space-1` through `--space-8`, `--font-body`, `--font-mono`, `--shadow-card`; add a `[data-theme="dark"]` block that overrides the color tokens with dark palette values

- [x] 3.2 Create `frontend/src/lib/stores/theme.ts` exporting `themeStore: Writable<"light" | "dark">` initialised from `localStorage.getItem("theme")` (defaulting to `"light"`); subscribe to the store and write `document.documentElement.dataset.theme = theme` and persist to `localStorage`; export `toggleTheme(): void`; use `writable` (not Svelte 5 runes) so the store is consumable from `.ts` files

- [x] 3.3 Create `frontend/src/lib/components/Button.svelte` accepting props: `variant: "primary" | "secondary" | "danger" = "primary"`, `disabled: boolean = false`, `type: "button" | "submit" | "reset" = "button"`, `loading: boolean = false`; render a `<button>` element styled via CSS custom properties defined in 3.1; render `LoadingSpinner` inline when `loading === true` and the button is disabled; export the component from `frontend/src/lib/components/index.ts`

- [x] 3.4 Create `frontend/src/lib/components/Card.svelte` with a default slot wrapped in a `<div>` styled as an elevated surface using `--color-surface-raised`, `--radius-md`, and `--shadow-card`; accept an optional `class` prop for consumer overrides; export from `index.ts`

- [x] 3.5 Create `frontend/src/lib/components/LoadingSpinner.svelte` rendering an accessible CSS-animated spinner using only `--color-primary` and `--space-*` tokens; add `aria-label="Loading"` and `role="status"`; export from `index.ts`

- [x] 3.6 Create `frontend/src/lib/components/ErrorBanner.svelte` accepting `message: string | null`; render nothing when `message` is null; render a visually distinct `<div role="alert">` with the message text and a dismiss button that emits a `dismiss` event; export from `index.ts`

- [x] 3.7 Create `frontend/src/lib/components/ThemeToggle.svelte` calling `toggleTheme()` from `themeStore` on click; subscribe to `themeStore` to render appropriate icon or label ("Light" / "Dark") for the current mode; export from `index.ts`

- [x] 3.8 Create `frontend/src/lib/components/Modal.svelte` accepting `open: boolean` and `title: string`; render a `<dialog>` element with backdrop overlay and a labelled header when `open === true`; provide a `#default` slot for body content and an `actions` named slot for buttons; close on `Escape` keydown and backdrop click; emit a `close` event; export from `index.ts`

- [x] 3.9 Create `frontend/src/routes/+layout.svelte` that: imports `tokens.css` (side-effect import), renders a `NavBar` component across the top, wraps `{@render children()}` in a main container div; the `NavBar` shows the app name, a `ThemeToggle`, and auth-aware links (logged-in: "Characters", "Logout"; logged-out: "Login", "Register"); implement an auth guard that redirects unauthenticated users from any path under `/app/games` or `/app/characters` to `/app/login`, using `authStore.user` to determine auth state

- [x] 3.10 Create `frontend/src/routes/+layout.ts` in `frontend/src/routes/` at the root level (if not already done in task 2.4) confirming `ssr = false` and `prerender = false`

## 4. TypeScript API Client

- [x] 4.1 Create `frontend/src/lib/api/types.ts` with TypeScript interfaces for every Pydantic response model currently returned by the API — at minimum: `TokenResponse`, `UserRead`, `GameRead`, `GameFeatureFlags`, `CharacterSummaryRead`, `CharacterStateRead`, `StatValue`, `StackedItemRead`, `ItemInstanceRead`, `SkillRead`, `BuffRead`, `ActiveQuestRead`, `MilestoneRead`, `ArchetypeRead`; field names and types MUST match the actual Python models exactly as documented in `design.md`; add a JSDoc comment on each interface that notes any field omissions from the ideal design (e.g., `SkillRead` lacks `on_cooldown`)

- [x] 4.2 Create `frontend/src/lib/api/client.ts` exporting `class ApiError extends Error { status: number; body: unknown }` and `async function apiFetch<T>(path: string, init?: RequestInit): Promise<T>`; the function MUST: prepend `base` from `$app/paths` to the path, attach the `Authorization: Bearer {accessToken}` header from `authStore` when a token is present, on `401` call `authStore.refresh()` and retry the request once, on second `401` call `authStore.logout()` and throw `ApiError`, on any non-ok status throw `ApiError` with `status` and parsed JSON body, on network error rethrow with a descriptive message; export `base` re-export for convenience

- [x] 4.3 Create `frontend/src/lib/stores/auth.ts` exporting `authStore` as a Svelte `writable` with shape `{ user: UserRead | null, accessToken: string | null, loading: boolean, error: string | null }`; implement and export: `login(email, password)` calling `POST /auth/login`, storing tokens, fetching `GET /auth/me`, updating store; `register(email, password)` calling `POST /auth/register`; `logout()` calling `POST /auth/logout`, clearing stored tokens, resetting store; `refresh()` calling `POST /auth/refresh` with the stored refresh token; `init()` calling `refresh()` on page load if a refresh token cookie or stored token exists; persist `accessToken` in memory only (NOT localStorage) to reduce XSS surface; persist `refreshToken` in `sessionStorage`

- [x] 4.4 Create `frontend/src/lib/api/auth.ts` exporting typed wrappers: `login(email: string, password: string): Promise<TokenResponse>`, `register(email: string, password: string): Promise<UserRead>`, `logout(): Promise<void>`, `me(): Promise<UserRead>`, `refresh(refreshToken: string): Promise<TokenResponse>`, `requestPasswordReset(email: string): Promise<void>`, `resetPassword(token: string, password: string): Promise<void>`, `verifyEmail(token: string): Promise<void>`; each function calls `apiFetch` with the correct HTTP verb and body

- [x] 4.5 Create `frontend/src/lib/api/games.ts` exporting: `listGames(): Promise<GameRead[]>` calling `GET /games`, `getGame(name: string): Promise<GameRead>` calling `GET /games/{name}`

- [x] 4.6 Create `frontend/src/lib/api/characters.ts` exporting: `listCharacters(gameName?: string): Promise<CharacterSummaryRead[]>` calling `GET /characters` with optional `?game=` param, `createCharacter(gameName: string): Promise<CharacterSummaryRead>` calling `POST /characters` with `{ game_name: gameName }`, `getCharacter(id: string): Promise<CharacterStateRead>` calling `GET /characters/{id}`, `deleteCharacter(id: string): Promise<void>` calling `DELETE /characters/{id}`, `renameCharacter(id: string, name: string): Promise<CharacterSummaryRead>` calling `PATCH /characters/{id}` with `{ name }`

## 5. Auth Flow Pages

- [x] 5.1 Create `frontend/src/routes/+page.svelte` (the landing page at `/app/`): render the app name, a short tagline, and two call-to-action `Button` components — "Log In" (navigates to `/app/login`) and "Register" (navigates to `/app/register`); if `authStore.user` is non-null, redirect immediately to `/app/characters`; no auth guard fires here since this is the public landing

- [x] 5.2 Create `frontend/src/routes/about/+page.svelte`: render static content about the application; include app name and description; no data fetch required

- [x] 5.3 Create `frontend/src/routes/login/+page.svelte`: render an email + password form; on submit call `authStore.login(email, password)`; show `LoadingSpinner` (with submit button disabled) while loading; show `ErrorBanner` with `authStore.error` on failure; on success navigate to `/app/characters`; provide a link to `/app/register` and `/app/forgot-password`

- [x] 5.4 Create `frontend/src/routes/register/+page.svelte`: render email + password + confirm-password form; validate that passwords match on the client before submitting; on submit call `authStore.register(email, password)`; on success show a confirmation message "Check your email to verify your account" and a link to `/app/login`; show `ErrorBanner` on failure

- [x] 5.5 Create `frontend/src/routes/verify/+page.svelte`: read the `?token=` query parameter on mount; call `verifyEmail(token)` from `api/auth.ts`; on success render a "Email verified!" message and a link to `/app/login`; on failure render an `ErrorBanner` with the error detail and a link to request a new verification email

- [x] 5.6 Create `frontend/src/routes/forgot-password/+page.svelte`: render an email form; on submit call `requestPasswordReset(email)`; on success (regardless of whether the email exists) show "If that email is registered, you will receive a reset link shortly."; show `ErrorBanner` on server error (5xx only); provide a link back to `/app/login`

- [x] 5.7 Create `frontend/src/routes/reset-password/+page.svelte`: read `?token=` from query params on mount; render new-password + confirm-password form; validate passwords match; on submit call `resetPassword(token, password)`; on success navigate to `/app/login` with a `?reset=1` flag so the login page can show a success toast; on failure render `ErrorBanner`

## 6. Character Management Pages

- [x] 6.1 Create `frontend/src/routes/games/+page.svelte`: implement the three-state async pattern — on mount call `listGames()`; while loading show `LoadingSpinner`; on error show `ErrorBanner`; on success render one `GameCard` component per game; `GameCard` shows `display_name`, `description` (if present), and a "Select" button navigating to `/app/characters?game={name}`; if the games list is empty render an informational empty-state message

- [x] 6.2 Create `frontend/src/routes/characters/+page.svelte`: read optional `?game=` from URL on mount; call `listCharacters(gameName)` using the three-state pattern; render one `CharacterCard` per character showing `name`, `game_name`, `prestige_count`, and `created_at` formatted as a locale date string; provide a "New Character" button navigating to `/app/characters/new${gameName ? '?game=' + gameName : ''}`; if the list is empty render an empty-state with a "Create your first character" link pointing to `/app/characters/new`

- [x] 6.3 Create `frontend/src/routes/characters/new/+page.svelte`: read `?game=` from URL; if present fetch `GET /games/{game}` and show a confirmation card (game `display_name` + "Create Character" button) without showing the game picker; if absent fetch `GET /games` and render the game picker grid; on confirmation call `createCharacter(gameName)` from `api/characters.ts`; show `LoadingSpinner` + disabled button while submitting; on `201` success navigate to `/app/characters/{id}` using the returned `CharacterSummaryRead.id`; on error show `ErrorBanner`

- [x] 6.4 Create `frontend/src/routes/characters/[id]/+page.svelte`: on mount fetch `GET /characters/{id}` and `GET /games/{game_name}` in parallel (derive `game_name` from `CharacterStateRead` after the first resolves — or fetch both sequentially if needed); implement three-state pattern; on 404 `ApiError` render a not-found state with a "Back to characters" link; on success render `CharacterHeader` and conditionally render each panel based on `GameFeatureFlags` per the spec table; include a "Back" link to `/app/characters`

- [x] 6.5 Create `frontend/src/lib/components/CharacterHeader.svelte`: accept `character: CharacterStateRead`; render `name`, `game_name`, `pronoun_set`, `prestige_count` (prefaced with "Prestige:"), `current_location_name` and `current_region_name` formatted as "location, region" (if both are set)

- [x] 6.6 Create `frontend/src/lib/components/panels/StatsPanel.svelte`: accept `stats: Record<string, StatValue>`; render a table or definition list of stat name → formatted value using `StatValue.current` (with `StatValue.maximum` shown as "current / max" when `maximum` is non-null); show an empty-state message when the record is empty

- [x] 6.7 Create `frontend/src/lib/components/panels/InventoryPanel.svelte`: accept `stacks: Record<string, StackedItemRead>` and `instances: ItemInstanceRead[]`; render two tabs ("Stacked Items" and "Item Instances"); the Stacked tab lists `ref` and `quantity` for each stacked item; the Instances tab lists `item_ref`, `instance_id` (shortened to first 8 chars), `charges_remaining` (if non-null), and any `modifiers` entries; show empty-state messages in each tab when the collection is empty

- [x] 6.8 Create `frontend/src/lib/components/panels/EquipmentPanel.svelte`: accept `equipment: Record<string, ItemInstanceRead>`; render a table of slot name → item reference (`item_ref`) and charges (if present); show an empty-state message when `equipment` has no keys

- [x] 6.9 Create `frontend/src/lib/components/panels/SkillsPanel.svelte`: accept `skills: SkillRead[]`; render a list showing `display_name` (falling back to `ref` when `display_name` is null) for each skill; note: cooldown state is not available from the current API and MUST NOT be shown; show an empty-state message when the list is empty

- [x] 6.10 Create `frontend/src/lib/components/panels/BuffsPanel.svelte`: accept `active_buffs: BuffRead[]`; render a list showing `ref`, `remaining_turns` (if non-null), and `tick_expiry` (if non-null) for each buff; show an empty-state message when the list is empty

- [x] 6.11 Create `frontend/src/lib/components/panels/QuestsPanel.svelte`: accept `active_quests: ActiveQuestRead[]`, `completed_quests: string[]`, and `failed_quests: string[]`; render three sections — "Active" (with `ref` and `current_stage`), "Completed" (refs only), "Failed" (refs only); show per-section empty-state messages when the respective collection is empty

- [x] 6.12 Create `frontend/src/lib/components/panels/MilestonesPanel.svelte`: accept `milestones: Record<string, MilestoneRead>`; render a list showing `ref`, `grant_tick`, and `grant_timestamp` formatted as a locale date string for each milestone; hide the entire component (render nothing) when the record is empty

- [x] 6.13 Create `frontend/src/lib/components/panels/ArchetypesPanel.svelte`: accept `archetypes: ArchetypeRead[]`; render a list showing `ref`, `grant_tick`, and `grant_timestamp` formatted as a locale date string for each archetype; show an empty-state message when the list is empty

## 7. Docker and Build Infrastructure

- [x] 7.1 Prepend a Node build stage to `dockerfile.www`: add `FROM node:22-alpine AS frontend-build` at the top; set `WORKDIR /app/frontend`; copy `frontend/package*.json` then run `npm ci`; copy the rest of `frontend/` and run `npm run build`; in the existing Python stage add `COPY --from=frontend-build /app/frontend/build /app/frontend/build` before the `CMD` line; verify `docker compose build` completes without error

- [x] 7.2 In `makefile`, add the following targets in a `# Frontend` section: `frontend_install` (`cd frontend && npm ci`), `frontend_build` (`cd frontend && npm run build`), `frontend_dev` (`cd frontend && npm run dev`), `frontend_check` (`cd frontend && npx svelte-check --tsconfig ./tsconfig.json`), `frontend_test` (`cd frontend && npx vitest run`), `frontend_format_check` (`cd frontend && npx prettier --check src/`), `frontend_format_fix` (`cd frontend && npx prettier --write src/`)

- [x] 7.3 Update the `install` make target to call `frontend_install` after the existing `uv sync` step so a single `make install` sets up both Python and Node dependencies

- [x] 7.4 Update the `tests` make target to call `frontend_check` and `frontend_test` after the existing Python checks so `make tests` validates the full stack

- [x] 7.5 Update the `chores` make target to call `frontend_format_fix` so `make chores` also formats Svelte/TypeScript source files

## 8. Testing

- [x] 8.1 Create `frontend/src/lib/stores/auth.test.ts`: (a) `login` calls `POST /auth/login` and then `GET /auth/me`, sets `user` and `accessToken` in the store; (b) `logout` calls `POST /auth/logout`, clears `user` and `accessToken`; (c) when `login` receives a 401 response, `error` is set in the store and `user` remains null; (d) `refresh` updates `accessToken` on success; (e) `refresh` calls `logout` on 401; mock `apiFetch` using `vi.mock` in place of real HTTP calls; assert store state transitions using `get(authStore)` after each async call

- [x] 8.2 Create `frontend/src/lib/stores/theme.test.ts`: (a) `themeStore` initialises to `"light"` when `localStorage` is empty; (b) `themeStore` initialises to the stored value when `localStorage.theme` is set; (c) `toggleTheme` switches `"light"` to `"dark"` and vice versa; (d) `toggleTheme` writes to `localStorage`; (e) `toggleTheme` sets `document.documentElement.dataset.theme`

- [x] 8.3 Create `frontend/src/lib/api/client.test.ts`: (a) `apiFetch` attaches `Authorization: Bearer {token}` header when `authStore.accessToken` is non-null; (b) `apiFetch` retries once on 401 after calling `authStore.refresh()`, succeeds on second attempt; (c) `apiFetch` calls `authStore.logout()` and throws `ApiError` after two 401 responses; (d) `apiFetch` throws `ApiError` with the correct `status` for a 422 response; (e) `apiFetch` returns parsed JSON for a 200 response; mock `fetch` with `vi.fn()`

- [x] 8.4 Create `frontend/src/routes/login/login.test.ts` using `@testing-library/svelte`: (a) login form renders email, password fields, and a submit button; (b) submitting the form calls `authStore.login` with the entered values; (c) while `authStore.loading` is true the submit button is disabled; (d) when `authStore.error` is non-null `ErrorBanner` renders the error message

- [x] 8.5 Create `frontend/src/routes/characters/[id]/character-sheet.test.ts` using `@testing-library/svelte`: (a) `LoadingSpinner` is rendered while the fetch is in-flight; (b) after a successful fetch, `CharacterHeader` renders the character name; (c) `SkillsPanel` is absent from the DOM when `features.has_skills === false`; (d) `QuestsPanel` is present when `features.has_quests === true`; (e) `ErrorBanner` renders when the `getCharacter` mock throws a 404 `ApiError`

- [x] 8.6 Create `frontend/tests/accessibility.test.ts` using Playwright and `@axe-core/playwright`: (a) `/{base}/login` has no automatically detectable WCAG 2.1 AA violations; (b) `/{base}/register` has no violations; (c) `/{base}/` (landing page) has no violations; run against the dev server started with `npm run preview` inside the test; add a Makefile target `frontend_a11y` executing `npx playwright test` in `frontend/`

- [x] 8.7 Create `frontend/playwright.e2e.config.ts` with `baseURL: 'http://localhost:4173'`, browser projects for Chromium, Firefox, and WebKit, and no `webServer` block (the live stack is a prerequisite, not managed by Playwright); create `frontend/tests/e2e/auth/register.spec.ts` testing the full registration flow (fill form with a generated `e2e-{uuid}@test.invalid` email, submit, assert verification confirmation is shown), `frontend/tests/e2e/auth/login.spec.ts` testing login and logout, `frontend/tests/e2e/characters/create.spec.ts` testing character creation end-to-end, and `frontend/tests/e2e/characters/sheet.spec.ts` asserting `CharacterHeader` and at least one panel render for an existing character; add a Makefile target `frontend_e2e` executing `npx playwright test --config playwright.e2e.config.ts` in `frontend/` — this target must NOT be added to the `make tests` recipe; add a Makefile target `frontend_e2e_stack` that uses `docker compose up` + `npm run preview` to bring up the full service stack (PostgreSQL, Redis, FastAPI, SvelteKit preview), run `make frontend_e2e`, and tear the stack down on completion — `frontend_e2e_stack` is the recommended single-command entry point for running E2E tests cleanly

## 10. CI Integration

- [x] 10.1 Add `.github/workflows/frontend-playwright.yaml` to run frontend Playwright accessibility and E2E checks in a browser matrix (`chromium`, `firefox`, `webkit`) with artifact upload for reports and logs

- [x] 10.2 Add `.github/workflows/frontend-accessibility.yaml` to run dedicated accessibility checks in a browser matrix (`chromium`, `firefox`, `webkit`) with artifact upload

- [x] 10.3 Update `.github/dependabot.yml` to include weekly npm updates for `/frontend` following the same cooldown, grouping, and PR-limit conventions as existing ecosystems

## 9. Documentation

- [x] 9.1 Create `docs/dev/frontend.md` covering: project layout (`frontend/` tree with annotated roles for each key directory), local dev setup (`make install`, `make frontend_dev` alongside `docker compose up`), architecture decisions (adapter-static rationale, `/app` base path, why SSR is disabled, CSS custom properties token system), adding new pages (naming conventions, route file placement, three-state async pattern, auth guard usage), adding new components (file placement, export from `index.ts`, props typing), API client conventions (using `apiFetch`, `authStore` lifecycle, adding new typed API modules), testing conventions (Vitest unit tests, Testing Library component tests, Playwright a11y tests, Playwright E2E integration tests and the `make frontend_e2e` prerequisite stack), and the CI pipeline

- [x] 9.2 Update `docs/dev/README.md`: add an entry for `frontend.md` in the table of contents under the "Frontend" section (create the section if it does not exist); include a one-sentence summary matching the `docs/dev/frontend.md` first paragraph

- [x] 9.3 Update `docs/dev/docker.md` (create the file if it does not exist): add a "Multi-stage build" section documenting the Node + Python two-stage `dockerfile.www`, the `frontend-build` stage inputs and outputs, how the build artifact is copied into the Python stage, and how to rebuild after frontend changes; include a note on the `FRONTEND_BUILD_PATH` environment variable override for production deployments
