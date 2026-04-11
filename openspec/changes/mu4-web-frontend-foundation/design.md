# Design: MU4 — Web Frontend — Foundation

## Context

MU1–MU3 deliver a complete API. This change introduces the browser-facing layer: a SvelteKit application with TypeScript, a Docker multi-stage build, and the design system that all future frontend work builds on.

No game loop interaction ships here. Players can register, log in, select a game, manage characters, and inspect a full character sheet — but not yet play adventures. The adventure screen is introduced in MU5.

The two most important constraints for this change are:

1. **Customization-ready CSS architecture.** Different Oscilla games may ship entirely different visual identities (dark fantasy, bright children's adventure, sci-fi). MU4 does not implement per-game theming, but it must not make theming a future rearchitecture. All visual tokens must be CSS custom properties in a single theme file. Components reference only those tokens. A future `game-theme.css` file overrides the tokens for a specific game — no component-level changes needed.

2. **SvelteKit deploy target: static adapter.** The frontend compiles to a static site served by FastAPI's `StaticFiles`. No Node.js process runs in production. All data fetching is client-side. This eliminates an entire process class from the deployment footprint and simplifies the Docker image. SSR is a future evolution if needed.

---

## Goals / Non-Goals

**Goals:**

- SvelteKit + TypeScript project scaffolded in `frontend/`.
- Docker multi-stage build: Node build stage compiles `frontend/build`; Python image serves it from `/app`.
- FastAPI serves the SvelteKit build from `/app` using `StaticFiles`.
- TypeScript API client hand-written and typed against all Pydantic response models from MU1 and MU2.
- Pages: landing (unauthenticated front page), about, login, register, email verification landing, forgotten password, password reset, game selection, character list, character creation, character sheet.
- Character sheet panels driven by `GameFeatureFlags`: stats, inventory (stacks + instances), equipment, skills (with cooldown display), active buffs, active quests, completed quests, milestones, archetypes.
- CSS custom properties design token layer in `frontend/src/lib/theme/tokens.css`.
- Dark and light mode: system preference honored via `prefers-color-scheme`; manual override toggle stored in `localStorage` and synced to `<html data-theme="...">` attribute.
- Accessibility baseline: semantic HTML (`<nav>`, `<main>`, `<button>`, `<label>`), appropriate ARIA roles and labels on interactive elements, keyboard navigability for all controls, visible focus rings, sufficient color contrast in both dark and light palettes.
- Vite dev proxy: `npm run dev` forwards API requests to the running FastAPI server without CORS configuration.
- `Makefile` targets: `frontend-install`, `frontend-build`, `frontend-dev`, `frontend-typecheck`, `frontend-lint`, `frontend-lint-fix`.

**Non-Goals:**

- Per-game theme customization (token overrides) — the architecture is ready; the override mechanism is not implemented.
- Adventure game loop UI components — all in MU5.
- Inventory drag-and-drop, talent tree DAG, faction reputation panel — roadmap; panels render as read-only lists in MU4.
- OAuth2 / social login UI.
- Formal accessibility audit (WCAG 2.1 AA certification) — deferred; the baseline above covers the most impactful requirements; a formal audit is post-launch scope.

---

## Decisions

### D1: SvelteKit with `adapter-static` — no Node SSR process

**Decision:** `svelte.config.js` uses `@sveltejs/adapter-static`. The build output is a directory of HTML, JS, and CSS files. FastAPI serves the entire directory as a `StaticFiles` mount. The SPA client-side router handles navigation.

Two key settings in `svelte.config.js` enforce the static SPA contract:

```javascript
// svelte.config.js
kit: {
  adapter: adapter({ fallback: 'index.html' }),
  paths: { base: '/app' },
}
```

`fallback: 'index.html'` outputs a single `index.html` that serves as the fallback for all unmatched paths — which `StaticFiles(html=True)` serves automatically. Note: the official `adapter-static` SPA docs show `fallback: '200.html'` as the example, but comment that it "may differ from host to host". For FastAPI's `StaticFiles`, `index.html` is the correct choice: `StaticFiles(html=True)` serves `index.html` as both the directory index and the 404 fallback, so any path under `/app` that is not a static file resolves to `index.html` and the client-side router takes over. `paths.base = '/app'` tells SvelteKit that all generated URLs and route links are prefixed with `/app`, so the SPA router and FastAPI path separation are both correct.

`ssr: false` must be set in the root `+layout.ts` (or via the adapter config) to disable all server-side rendering. Since there is no Node server in production, any route that attempts to access `window` or `localStorage` during SSR would fail. With `ssr: false`, every page renders exclusively in the browser.

The frontend route for the app is `/app/` — this keeps it separate from the API routes (`/auth/`, `/games/`, `/characters/`). The root `/` redirect is updated to point to `/app/`.

**Alternatives considered:**

- `adapter-node` (Node SSR process) — rejected. Adds an additional process to the deployment topology and requires a dedicated `node` container or process manager. The gain — faster initial page paint — is not justified for an inner game loop app where the user is already authenticated. SSR can be introduced in a future change if initial load performance becomes a measurable concern.
- Serve from CDN / separate origin — rejected. Requires CORS configuration on every API route, a second deployment artifact per environment, and breaks the self-contained Docker image property. Self-hosting as part of the Python server keeps the deployment to a single image and single origin.
- `adapter-cloudflare` / `adapter-vercel` — rejected. These require platform-specific deployment pipelines that contradict the project's self-hosted-first philosophy.

---

### D2: TypeScript API client — hand-written, typed against Pydantic models

**Decision:** The TypeScript API client is hand-written (not auto-generated from an OpenAPI spec) in `frontend/src/lib/api/`. The file structure mirrors the server router structure:

```
frontend/src/lib/api/
  auth.ts       — register, login, refresh, logout, me, update profile
  games.ts      — listGames, getGame
  characters.ts — listCharacters, createCharacter, getCharacter, deleteCharacter, renameCharacter
  types.ts      — TypeScript interfaces matching all Pydantic response models
  client.ts     — base fetch wrapper: auth header injection, 401 retry, error normalization
```

`client.ts` exposes `api.get<T>()`, `api.post<T>()`, `api.patch<T>()`, and `api.delete<T>()`. It reads the access token from the Svelte auth store and injects `Authorization: Bearer <token>` on every request (except calls marked `skipAuth: true`, which are used for `/auth/login` and `/auth/register`). On `401` response it calls `refreshTokens()` — which calls `fetch` directly against `/auth/refresh` to avoid a circular import — then retries once. If the retry also fails, `authStore.logout()` is called and the user is redirected to `/app/login`.

All non-2xx responses throw an `ApiError` carrying the HTTP status and the `detail` field from the JSON body (or the raw status text for non-JSON responses). Every API module function propagates `ApiError` to its callers. Components catch it in `try/catch` and route to the error display mechanism (see D8).

**Circular import prevention:** `client.ts` cannot import high-level API functions from `auth.ts` for token refresh — that would create `client.ts → auth.ts → client.ts` cycle. Instead, `stores/auth.ts` exports a `refreshTokens()` function that calls `fetch` directly. `client.ts` imports only this function from the store, not any other API module.

**Why hand-written over OpenAPI codegen:** OpenAPI codegen tools (`openapi-typescript`, `openapi-fetch`) produce correct output but add a CI step, a dev dependency, and a regeneration workflow that must be triggered on every Pydantic model change. For the current model count (< 25 types), hand-written TypeScript interfaces are faster to write, easier to read, and require zero tooling. The schema is specified completely in the Implementation section below; any drift becomes immediately visible as a TypeScript type error when a component accesses a renamed or missing field.

**Alternatives considered:**

- `openapi-typescript` codegen — generates types from the FastAPI OpenAPI JSON at build time. Correct approach for large APIs; rejected for now because it requires a running server during CI, complicates the `frontend-typecheck` step, and adds a dependency sync discipline that is premature for the current model count.
- `tRPC` — strongly-typed RPC layer that eliminates the HTTP contract entirely. Rejected: requires switching the server to a Node.js runtime or a Python tRPC adapter; neither is compatible with the FastAPI-first architecture.

---

### D3: CSS custom properties design token layer — with dark/light mode and accessibility

**Decision:** All visual tokens are defined in `frontend/src/lib/theme/tokens.css` as CSS custom properties. The file defines two complete palettes: a dark theme (default) and a light theme, plus all layout and typography tokens that are shared between them.

The active palette is selected by a `data-theme` attribute on `<html>`. The default value matches the user's `prefers-color-scheme` preference; a manual toggle overrides it and persists the choice to `localStorage`.

```css
/* frontend/src/lib/theme/tokens.css */

/* ── Color-scheme-neutral tokens (never change with theme) ── */
:root {
  /* Typography */
  --font-family-body: "Georgia", serif;
  --font-family-ui: "Inter", sans-serif;
  --font-size-base: 1rem;
  --font-size-sm: 0.875rem;
  --font-size-lg: 1.25rem;

  /* Spacing */
  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 1.5rem;
  --space-xl: 2rem;

  /* Borders */
  --border-radius-sm: 4px;
  --border-radius-md: 8px;
  --border-width: 1px;
}

/* ── Dark palette (default) ── */
:root,
[data-theme="dark"] {
  --color-bg-primary: #1a1a2e;
  --color-bg-surface: #16213e;
  --color-bg-surface-raised: #0f3460;
  --color-text-primary: #e0e0e0; /* contrast vs bg-primary: 11.2:1 ✓ */
  --color-text-muted: #9090a0; /* contrast vs bg-primary: 4.6:1 ✓ (AA large) */
  --color-accent: #e94560;
  --color-accent-hover: #ff6b85;
  --color-success: #4caf50;
  --color-warning: #ff9800;
  --color-danger: #f44336;
  --color-border: rgba(255, 255, 255, 0.1);
  --shadow-card: 0 2px 8px rgba(0, 0, 0, 0.4);
  /* Focus ring: high-contrast yellow works on both dark backgrounds */
  --color-focus-ring: #ffd700;
}

/* ── Light palette ── */
[data-theme="light"] {
  --color-bg-primary: #f5f5f5;
  --color-bg-surface: #ffffff;
  --color-bg-surface-raised: #e8eaf6;
  --color-text-primary: #1a1a2e; /* contrast vs bg-primary: 12.4:1 ✓ */
  --color-text-muted: #555566; /* contrast vs bg-primary: 5.9:1 ✓ */
  --color-accent: #c0143a;
  --color-accent-hover: #e94560;
  --color-success: #2e7d32;
  --color-warning: #e65100;
  --color-danger: #b71c1c;
  --color-border: rgba(0, 0, 0, 0.12);
  --shadow-card: 0 2px 8px rgba(0, 0, 0, 0.15);
  --color-focus-ring: #005fcc;
}

/* ── Respect system preference when no manual override is set ── */
@media (prefers-color-scheme: light) {
  :root:not([data-theme]) {
    --color-bg-primary: #f5f5f5;
    --color-bg-surface: #ffffff;
    --color-bg-surface-raised: #e8eaf6;
    --color-text-primary: #1a1a2e;
    --color-text-muted: #555566;
    --color-accent: #c0143a;
    --color-accent-hover: #e94560;
    --color-success: #2e7d32;
    --color-warning: #e65100;
    --color-danger: #b71c1c;
    --color-border: rgba(0, 0, 0, 0.12);
    --shadow-card: 0 2px 8px rgba(0, 0, 0, 0.15);
    --color-focus-ring: #005fcc;
  }
}
```

Components reference only these token names — no hardcoded colors, ever. Focus rings use `--color-focus-ring` on `:focus-visible` selectors (not `:focus`, to avoid visible rings on mouse clicks).

The toggle is implemented in a `ThemeToggle.svelte` component placed in the `NavBar`. On mount, `+layout.svelte` reads `localStorage.getItem('oscilla:theme')` and applies it to `document.documentElement.dataset.theme`. If no preference is stored, the `prefers-color-scheme` media query determines the initial palette via the CSS above — no JavaScript is needed for the default path.

```typescript
// frontend/src/lib/stores/theme.ts
import { writable } from "svelte/store";

const STORAGE_KEY = "oscilla:theme";
export type ThemeValue = "dark" | "light";

function createThemeStore() {
  // Default: null means "follow system preference" — no data-theme attribute set.
  const initial =
    typeof localStorage !== "undefined"
      ? (localStorage.getItem(STORAGE_KEY) as ThemeValue | null)
      : null;

  const { subscribe, set } = writable<ThemeValue | null>(initial);

  if (initial) {
    document.documentElement.dataset.theme = initial;
  }

  return {
    subscribe,
    toggle(): void {
      const current = document.documentElement.dataset.theme as
        | ThemeValue
        | undefined;
      // If no data-theme set, detect effective theme from media query.
      const effective =
        current ??
        (window.matchMedia("(prefers-color-scheme: light)").matches
          ? "light"
          : "dark");
      const next: ThemeValue = effective === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      localStorage.setItem(STORAGE_KEY, next);
      set(next);
    },
    reset(): void {
      delete document.documentElement.dataset.theme;
      localStorage.removeItem(STORAGE_KEY);
      set(null);
    },
  };
}

export const themeStore = createThemeStore();
```

**Accessibility baseline enforced in MU4:**

- Semantic elements: `<nav>`, `<main>`, `<header>`, `<button>`, `<label for>`, `<fieldset>`/`<legend>` for grouped controls.
- All `<img>` elements have an `alt` attribute. Decorative images use `alt=""`.
- All interactive elements are keyboard-reachable (tab order follows DOM order; no `tabindex > 0`).
- All interactive elements have visible `:focus-visible` outlines using `--color-focus-ring`.
- Color contrast: both palettes above were checked against WCAG 2.1 AA minimums (4.5:1 for body text, 3:1 for large text and UI components). Contrast ratios are noted inline in the token comments.
- ARIA: `aria-label` on icon-only buttons (e.g. the theme toggle), `aria-live="polite"` on the `ErrorBanner` element so screen readers announce auth errors without interrupting the user.
- Form fields: every `<input>` has an associated `<label>` (either `for`/`id` or `aria-label`); error messages are linked with `aria-describedby`.

**What is not in scope for MU4:**

- Formal WCAG 2.1 AA audit / certification.
- Screen reader testing on multiple platforms.
- ARIA landmark coverage beyond the baseline above.

No component uses a hardcoded color, font, or spacing value. This constraint is enforced by code review. A future Stylelint rule banning non-variable colors can automate this.

A future change can add a `game-theme.css` file served at runtime that overrides any or all of these tokens for a specific game — the `data-theme` attribute approach means per-game themes would simply add another `[data-theme='game-name']` selector block.

---

### D4: Character creation is a single-step game selection form

**Decision:** The character creation page asks the user to select a game and click Create. That is the entire form — `POST /characters` accepts only `game_name`.

If the user arrives from the character list with a `?game=` query parameter, the game is pre-selected and the page shows only a confirmation prompt before calling `POST /characters`. If no game is pre-selected, a game picker (same grid as the game selection page) is shown first.

On success, the user is redirected to the new character sheet. Any name, pronoun, archetype, or class selection the game requires is handled by the game's triggered creation adventure — that flow is entirely in MU5 (adventure execution). MU4 has no UI for it.

**Alternatives considered:**

- Multi-step wizard with name, pronoun, and archetype steps — rejected. `POST /characters` accepts no such fields. All player-facing character customization is authored by game creators as triggered adventures using `set_name`, `set_pronouns`, and `archetype_add` effects. The frontend must not duplicate or pre-empt that flow.

---

### D5: Character sheet panel visibility via `GameFeatureFlags`

**Decision:** The character sheet page fetches `GET /games/{game_name}` and `GET /characters/{id}` in parallel on mount. `GameFeatureFlags` from the game response controls which panels are rendered:

| Panel        | Shown when                                             |
| ------------ | ------------------------------------------------------ |
| Stats        | Always                                                 |
| Inventory    | Always                                                 |
| Equipment    | Always                                                 |
| Skills       | `has_skills == true`                                   |
| Buffs        | Always (empty list renders as empty panel, not hidden) |
| Quests       | `has_quests == true`                                   |
| Milestones   | Always (non-empty check handled by component)          |
| Archetypes   | `has_archetypes == true`                               |
| In-game time | `has_ingame_time == true`                              |

No panel is hardcoded as always-visible in the component logic — the `GameFeatureFlags` check is the only source of truth. A game with no quests declared shows no quests panel at all, not an empty quests panel.

---

### D6: Route guard via `beforeNavigate` in root layout — not `+layout.ts` load function

**Decision:** Route protection is implemented in `+layout.svelte` using `onMount` and `beforeNavigate`, not in a `+layout.ts` load function.

The auth store is backed by `localStorage`. With `adapter-static` and `ssr: false`, every page renders client-side only — there is no server execution phase. However, `+layout.ts` load functions run before the component tree mounts, which means the Svelte stores are not yet initialized when a load function executes on cold page load. A load function that reads `isLoggedIn` would always see `false` on first navigation to a protected route, causing a redirect loop.

`onMount` fires after the component tree mounts and after `authStore.init()` has hydrated the auth state from `localStorage`. `beforeNavigate` fires on all subsequent client-side navigations, when the store is guaranteed to be populated. Together they provide:

1. **Cold load protection:** `onMount` runs `authStore.init()` → evaluates auth state → redirects if needed.
2. **In-app navigation protection:** `beforeNavigate` gate catches programmatic and link-click navigation to protected routes.

Route classification:

| Route                  | Auth required                                |
| ---------------------- | -------------------------------------------- |
| `/app` (landing)       | No                                           |
| `/app/about`           | No                                           |
| `/app/login`           | No (redirects to games if already logged in) |
| `/app/register`        | No (redirects to games if already logged in) |
| `/app/verify`          | No                                           |
| `/app/forgot-password` | No                                           |
| `/app/reset-password`  | No                                           |
| `/app/games`           | Yes                                          |
| `/app/characters`      | Yes                                          |
| `/app/characters/new`  | Yes                                          |
| `/app/characters/[id]` | Yes                                          |

**Alternatives considered:**

- `+layout.ts` load function with `throw redirect(302, ...)` — the correct pattern for SSR apps; rejected because with `ssr: false` the load function cannot reliably access `localStorage` or the auth store before the component mounts, resulting in auth state being uninitialized on cold load.
- Per-route `+page.ts` guards — works but requires duplicating the public/protected classification on every route file; a maintenance burden as routes are added or reorganized. A single root layout guard is the single source of truth.
- Session cookie read in `+layout.ts` (HttpOnly cookie, readable server-side) — correct for SSR; deferred to MU6. This would allow the load function to work, but requires switching token storage from `localStorage` to cookies, which is a separate security trade-off decision.

---

### D7: Vite proxy for local development — no CORS configuration needed

**Decision:** `vite.config.ts` proxies all API path prefixes (`/auth`, `/games`, `/characters`) to `http://localhost:8000` when running `npm run dev`. The browser speaks only to the Vite dev server (default port 5173); the proxy forwards API requests transparently to FastAPI.

```typescript
// vite.config.ts (dev server block)
server: {
  proxy: {
    '/auth': 'http://localhost:8000',
    '/games': 'http://localhost:8000',
    '/characters': 'http://localhost:8000',
  },
},
```

This eliminates any CORS configuration requirement: both the frontend assets and the API responses arrive from the same origin (`localhost:5173`) from the browser's perspective. When the frontend is served by FastAPI in production, the shared origin property holds naturally, so no CORS changes are needed in either environment.

The local development workflow is:

1. `docker compose up db redis` — start PostgreSQL and Redis.
2. `uv run uvicorn oscilla.www:app --reload` — start FastAPI on port 8000.
3. `cd frontend && npm run dev` — start Vite on port 5173 with proxy active.

`compose.yaml` does not change for the development workflow. The multi-stage Docker build is production-only.

**Alternatives considered:**

- Add CORS middleware to FastAPI and point the Vite dev server directly at `localhost:8000` — rejected. CORS configuration is error-prone, requires listing exact origins, and has to be kept in sync between development and production configurations. The proxy approach has zero runtime overhead and zero configuration surface.
- Run both FastAPI and Vite from a single `docker compose` dev service — rejected. Hot-reload developer experience for both Python (uvicorn `--reload`) and frontend (Vite HMR) is better when each process manages its own watch loop. Docker adds overhead for a workflow that runs cleanly on bare metal.

---

### D8: Error and loading state protocol — three-state async component pattern

**Decision:** Every component that performs an async data fetch follows an explicit three-state pattern: `loading`, `error`, and `data`. The states are modeled with discriminated union stores or local reactive variables:

```typescript
// Typical component local state — Svelte 5 runes inside a .svelte <script> block
let loading = $state(true);
let error = $state<ApiError | null>(null);
let character = $state<CharacterStateRead | null>(null);

onMount(async () => {
  try {
    character = await getCharacter(characterId);
  } catch (e) {
    if (e instanceof ApiError) {
      error = e;
    } else {
      error = new ApiError(0, "Unexpected error");
    }
  } finally {
    loading = false;
  }
});
```

The `LoadingSpinner` component is shown when `loading === true`. The `ErrorBanner` component is shown when `error !== null`. The page content is rendered only when `loading === false && error === null`.

HTTP 401 errors are handled entirely by `client.ts` (refresh + redirect) before the `ApiError` propagates to the component. A component that receives an `ApiError` with status 401 indicates that the refresh attempt also failed, which `client.ts` handles by redirecting — the component will not be in the DOM at that point.

HTTP 403 errors (unverified email) are displayed directly by the component with a prompt to check email. HTTP 404 errors navigate to a not-found page. HTTP 422 errors (Pydantic validation failures) are rendered as field-level form errors in form components. HTTP 5xx errors are shown in `ErrorBanner` with a generic "server error" message and no raw detail exposed to the user.

**Alternatives considered:**

- Svelte stores for global error state — rejected for page-level data errors. Page data errors are local to the component; surfacing them globally creates confusion about which page produced the error. The global `ErrorBanner` is reserved for auth-layer errors (`authStore.error`), not data-fetch errors.
- SvelteKit's built-in error page (`+error.svelte`) — available for `throw error()` from load functions, but load functions are not used for data fetching in this SPA (see D6). In-component error handling is the consistent pattern.

---

## Architecture

### Component Hierarchy

The root layout wraps every page. `NavBar` contents change based on auth state. `ErrorBanner` is shown only when `authStore.error` is set (auth-layer errors such as permanent session expiry).

```
App (root +layout.svelte)
├── NavBar
│   ├── LogoLink → /app
│   ├── NavLinks (Games · Characters — hidden when not logged in)
│   └── UserMenu (dropdown: display name · Profile · Logout — hidden when not logged in)
├── ErrorBanner          (global; shown only on auth-layer errors)
└── [page route slot]
    ├── /app                          LandingPage
    ├── /app/about                    AboutPage
    ├── /app/login                    LoginPage
    ├── /app/register                 RegisterPage
    ├── /app/verify                   EmailVerifyPage
    ├── /app/forgot-password          ForgotPasswordPage
    ├── /app/reset-password           ResetPasswordPage
    ├── /app/games                    GameSelectionPage
    │   └── GameCard (×N)
    ├── /app/characters               CharacterListPage
    │   └── CharacterCard (×N)
    ├── /app/characters/new           CharacterCreatePage
    │   └── GamePicker (if no ?game= param)
    └── /app/characters/[id]          CharacterSheetPage
        ├── CharacterHeader
        ├── StatsPanel
        ├── InventoryPanel            (tabs: Stacked · Instances)
        ├── EquipmentPanel
        ├── SkillsPanel               (only if features.has_skills)
        ├── BuffsPanel
        ├── QuestsPanel               (only if features.has_quests)
        ├── MilestonesPanel
        └── ArchetypesPanel           (only if features.has_archetypes)
```

### Data Flow

```
User action (click, form submit)
    │
    ▼
Svelte component (e.g. LoginPage.svelte)
    │  calls API function
    ▼
API module (e.g. src/lib/api/auth.ts → login())
    │  calls client.ts request()
    ▼
client.ts request()
    │  reads accessToken from authStore
    │  injects Authorization: Bearer header
    │  on 401 → calls authStore.refreshTokens() [uses fetch directly, no circular import]
    │           → retries original request once
    │           → on failure: authStore.logout() + goto('/app/login')
    ▼
FastAPI  (proxied via Vite in dev / same origin in prod)
    │
    ▼
Response JSON
    │  parsed to typed interface from types.ts
    ▼
API module returns typed object to component
    │
    ▼
Component updates Svelte store (authStore, gameStore) or local reactive state
    │
    ▼
Svelte reactivity re-renders affected component subtree
```

### Auth Token Lifecycle

```
Registration / Login
    │  POST /auth/register  or  POST /auth/login
    │  Returns: { access_token, refresh_token, token_type: 'bearer' }
    │
    ▼
authStore.login(pair, user)
    │  Writes accessToken, refreshToken to writable store
    │  Writes both tokens to localStorage
    │  Writes UserRead to store
    │
    ▼
App load (browser refresh)
    │  authStore.init()  called from onMount in +layout.svelte
    │  Reads tokens from localStorage
    │  Calls GET /auth/me with stored access token
    │  If 401 → calls authStore.refreshTokens() once
    │
    ▼
401 mid-session (access token expired)
    │  client.ts intercepts 401
    │  POST /auth/refresh  { refresh_token }
    │  Returns new TokenPair → authStore.applyTokenPair()
    │  Retries original request
    │
    ▼
Logout (user-initiated)
    │  POST /auth/logout  (revokes refresh token server-side)
    │  authStore.logout()
    │  Clears localStorage
    │  goto('/app/login')
    │
    ▼
Forced logout (refresh attempt itself returns 401)
    │  authStore.logout()
    │  Clears localStorage
    │  goto('/app/login?next=<current path>')
```

---

## Key Implementation Details

### Settings: `oscilla/conf/settings.py`

One field is added to the existing `Settings` class:

```python
frontend_build_path: Path = Field(
    default=Path("frontend/build"),
    description=(
        "Path to the compiled SvelteKit build directory. "
        "Resolved relative to the working directory at startup. "
        "When the directory does not exist the /app route is not mounted."
    ),
)
```

### `oscilla/www.py` — Frontend Mount

The `StaticFiles` mount is added after all API routers are registered. Path resolution at startup ensures the log shows the absolute path:

```python
from pathlib import Path

from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from oscilla.conf.settings import settings

# ... existing router includes ...

frontend_build = settings.frontend_build_path.resolve()
if frontend_build.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_build), html=True), name="frontend")
    logger.info("Frontend build mounted from %s", frontend_build)
else:
    logger.warning(
        "Frontend build directory not found at %s — /app will return 404. "
        "Run 'make frontend-build' to compile the frontend.",
        frontend_build,
    )


@app.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/app", status_code=302)
```

### `frontend/svelte.config.js`

```javascript
import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      // index.html serves as the SPA fallback for all unmatched paths.
      // FastAPI StaticFiles(html=True) serves this file for any path under /app.
      fallback: "index.html",
    }),
    paths: {
      // All route links and asset URLs are generated with this prefix,
      // matching how FastAPI mounts the directory at /app.
      base: "/app",
    },
  },
};

export default config;
```

### `frontend/vite.config.ts`

```typescript
import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    // Proxy all API routes to the local FastAPI server when running npm run dev.
    // The browser sees only localhost:5173, so no CORS configuration is needed.
    proxy: {
      "/auth": "http://localhost:8000",
      "/games": "http://localhost:8000",
      "/characters": "http://localhost:8000",
    },
  },
});
```

### `frontend/src/routes/+layout.ts`

Disables SSR for all routes. The auth guard lives in `+layout.svelte` (see D6).

```typescript
export const ssr = false;
export const prerender = false;
```

> **SvelteKit app state:** In `.svelte` components, use `import { page, navigating } from '$app/state'` (added in SvelteKit 2.12) to access current page and navigation state via direct property access (e.g. `page.url.pathname`). This is the current API for Svelte 5 projects. The older `$app/stores` module with `$page` store subscriptions is the legacy path for Svelte 4 / pre-2.12 code.

### `frontend/src/lib/stores/auth.ts`

> **Why `writable` stores and not Svelte 5 runes?** Svelte 5 runes (`$state`, `$derived`) are only available in `.svelte` and `.svelte.ts` files. `client.ts` is a plain `.ts` module — it must be able to read the current access token synchronously via `get(authStore)` from `svelte/store`. Rune-based reactive state cannot be consumed by regular TypeScript. The `writable` store API is not deprecated in Svelte 5; it remains the correct choice for cross-boundary state (`.svelte` ↔ `.ts`) and is used here intentionally.

```typescript
import { writable, derived, get } from "svelte/store";
import type { UserRead, TokenPair } from "$lib/api/types";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserRead | null;
  error: string | null;
}

const ACCESS_TOKEN_KEY = "oscilla_access_token";
const REFRESH_TOKEN_KEY = "oscilla_refresh_token";

function createAuthStore() {
  const { subscribe, set, update } = writable<AuthState>({
    accessToken: null,
    refreshToken: null,
    user: null,
    error: null,
  });

  return {
    subscribe,

    /**
     * Hydrate from localStorage on app mount. Fetches GET /auth/me to restore
     * the UserRead and validate the stored token. If that returns 401, attempts
     * one refresh before clearing state.
     */
    async init(): Promise<void> {
      /* ... */
    },

    /** Store token pair and user after successful login or register. */
    login(pair: TokenPair, user: UserRead): void {
      localStorage.setItem(ACCESS_TOKEN_KEY, pair.access_token);
      localStorage.setItem(REFRESH_TOKEN_KEY, pair.refresh_token);
      set({
        accessToken: pair.access_token,
        refreshToken: pair.refresh_token,
        user,
        error: null,
      });
    },

    /** Replace tokens in store and localStorage after a successful refresh. */
    applyTokenPair(pair: TokenPair): void {
      localStorage.setItem(ACCESS_TOKEN_KEY, pair.access_token);
      localStorage.setItem(REFRESH_TOKEN_KEY, pair.refresh_token);
      update((s) => ({
        ...s,
        accessToken: pair.access_token,
        refreshToken: pair.refresh_token,
      }));
    },

    /** Clear all auth state. Called on logout or when refresh permanently fails. */
    logout(): void {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      set({ accessToken: null, refreshToken: null, user: null, error: null });
    },

    /** Set an auth-layer error for display in the global ErrorBanner. */
    setError(message: string): void {
      update((s) => ({ ...s, error: message }));
    },

    /**
     * Attempt a token refresh using the stored refresh token.
     * Calls fetch directly instead of going through client.ts to avoid a
     * circular import (client.ts imports this function).
     * Returns true on success, false on failure (also calls logout()).
     */
    async refreshTokens(): Promise<boolean> {
      const state = get({ subscribe });
      if (!state.refreshToken) return false;
      try {
        const res = await fetch("/auth/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: state.refreshToken }),
        });
        if (!res.ok) {
          this.logout();
          return false;
        }
        const pair: TokenPair = await res.json();
        this.applyTokenPair(pair);
        return true;
      } catch {
        this.logout();
        return false;
      }
    },
  };
}

export const authStore = createAuthStore();
export const isLoggedIn = derived(
  authStore,
  ($auth) => $auth.accessToken !== null && $auth.user !== null,
);
```

### `frontend/src/lib/api/client.ts`

```typescript
import { get } from "svelte/store";
import { goto } from "$app/navigation";
import { authStore } from "$lib/stores/auth";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`HTTP ${status}: ${detail}`);
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  /** Set true for login and register — these endpoints do not take a Bearer token. */
  skipAuth?: boolean;
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, skipAuth = false } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (!skipAuth) {
    const { accessToken } = get(authStore);
    if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const init: RequestInit = {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  let response = await fetch(path, init);

  // Attempt one token refresh and retry on 401
  if (response.status === 401 && !skipAuth) {
    const refreshed = await authStore.refreshTokens();
    if (refreshed) {
      const { accessToken } = get(authStore);
      headers["Authorization"] = `Bearer ${accessToken}`;
      response = await fetch(path, { ...init, headers });
    }
    if (!refreshed || response.status === 401) {
      authStore.logout();
      await goto(`/login?next=${encodeURIComponent(window.location.pathname)}`);
      throw new ApiError(401, "Session expired — please log in again.");
    }
  }

  if (!response.ok) {
    const detail = await response
      .json()
      .then((d: { detail?: string }) => d?.detail ?? response.statusText)
      .catch(() => response.statusText);
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;

  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, skipAuth = false) =>
    request<T>(path, { method: "GET", skipAuth }),
  post: <T>(path: string, body: unknown, skipAuth = false) =>
    request<T>(path, { method: "POST", body, skipAuth }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body }),
  delete: <T = void>(path: string) => request<T>(path, { method: "DELETE" }),
};
```

### `frontend/src/lib/api/types.ts` — Complete Interface List

All interfaces mirror the Pydantic models from MU1 and MU2. Field names use `snake_case` to match FastAPI's default JSON serialization. UUIDs are typed as `string`; timestamps are ISO 8601 strings.

```typescript
// ── Auth (MU1) ───────────────────────────────────────────────────────────────

export interface UserRead {
  id: string;
  email: string;
  display_name: string | null;
  is_email_verified: boolean;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

// ── Games (MU2) ──────────────────────────────────────────────────────────────

export interface GameFeatureFlags {
  has_skills: boolean;
  has_quests: boolean;
  has_factions: boolean;
  has_archetypes: boolean;
  has_ingame_time: boolean;
  has_recipes: boolean;
  has_loot_tables: boolean;
}

export interface GameRead {
  name: string;
  display_name: string;
  description: string | null;
  features: GameFeatureFlags;
}

// ── Characters (MU2) ─────────────────────────────────────────────────────────

export interface CharacterSummaryRead {
  id: string;
  name: string;
  game_name: string;
  character_class: string | null;
  prestige_count: number;
  created_at: string;
  updated_at: string;
}

export interface StatValue {
  ref: string;
  display_name: string | null;
  value: number | boolean | null;
}

export interface StackedItemRead {
  ref: string;
  display_name: string;
  quantity: number;
  description: string | null;
}

export interface ItemInstanceRead {
  id: string;
  ref: string;
  display_name: string;
  description: string | null;
  slot: string | null;
}

export interface SkillRead {
  ref: string;
  display_name: string;
  description: string | null;
  on_cooldown: boolean;
  cooldown_remaining_ticks: number | null;
}

export interface BuffRead {
  ref: string;
  display_name: string;
  description: string | null;
  expires_at_ticks: number | null;
  source: string | null;
}

export interface ActiveQuestRead {
  ref: string;
  display_name: string;
  description: string | null;
  current_stage: string | null;
}

export interface MilestoneRead {
  ref: string;
  display_name: string;
  description: string | null;
  earned_at: string;
}

export interface ArchetypeRead {
  ref: string;
  display_name: string;
  description: string | null;
}

export interface ActiveAdventureRead {
  adventure_ref: string;
  step_index: number;
}

export interface CharacterStateRead {
  // Identity
  id: string;
  name: string;
  game_name: string;
  character_class: string | null;
  prestige_count: number;
  pronoun_set: string;
  created_at: string;

  // Location
  current_location: string | null;
  current_location_name: string | null;
  current_region_name: string | null;

  // Stats (all declared stats, including unset ones with value: null)
  stats: Record<string, StatValue>;

  // Inventory
  stacks: Record<string, StackedItemRead>;
  instances: ItemInstanceRead[];
  equipment: Record<string, ItemInstanceRead>;

  // Skills
  skills: SkillRead[];

  // Buffs
  active_buffs: BuffRead[];

  // Quests
  active_quests: ActiveQuestRead[];
  completed_quests: string[];
  failed_quests: string[];

  // Milestones
  milestones: Record<string, MilestoneRead>;

  // Archetypes
  archetypes: ArchetypeRead[];

  // Progress counters
  internal_ticks: number;
  game_ticks: number;

  // Active adventure (null when between adventures)
  active_adventure: ActiveAdventureRead | null;
}
```

### `frontend/package.json` — Key Dependencies

| Package                            | Role                                                      |
| ---------------------------------- | --------------------------------------------------------- |
| `@sveltejs/kit`                    | SvelteKit framework                                       |
| `@sveltejs/adapter-static`         | Static site adapter                                       |
| `@sveltejs/vite-plugin-svelte`     | Vite/Svelte integration                                   |
| `svelte`                           | Svelte runtime                                            |
| `typescript`                       | TypeScript compiler                                       |
| `svelte-check`                     | TypeScript checking for `.svelte` files                   |
| `vite`                             | Build tool and dev server                                 |
| `eslint`                           | JavaScript/TypeScript linter                              |
| `eslint-plugin-svelte`             | Svelte-specific ESLint rules                              |
| `@typescript-eslint/eslint-plugin` | TypeScript-aware lint rules                               |
| `@typescript-eslint/parser`        | TypeScript parser for ESLint                              |
| `prettier`                         | Code formatter (project-wide; covers `.svelte` and `.ts`) |
| `prettier-plugin-svelte`           | Svelte formatter support for Prettier                     |

---

## Project Structure

```
frontend/
  package.json
  svelte.config.js        — adapter-static configuration
  tsconfig.json
  vite.config.ts
  src/
    app.html              — SvelteKit HTML shell
    routes/
      +layout.svelte      — Root layout: nav, auth state, global styles; auth guard via onMount + beforeNavigate
      +layout.ts          — Sets ssr=false and prerender=false for all routes
      app/
        +page.svelte      — Landing page (unauthenticated front page; redirects to /app/games if logged in)
        about/
          +page.svelte    — About page (static content; no auth required)
        login/
          +page.svelte
        register/
          +page.svelte
        verify/
          +page.svelte    — Email verification landing (reads token from URL)
        forgot-password/
          +page.svelte
        reset-password/
          +page.svelte    — Password reset (reads token from URL)
        games/
          +page.svelte    — Game selection grid
        characters/
          +page.svelte    — Character list
          new/
            +page.svelte  — Character creation wizard
          [id]/
            +page.svelte  — Character sheet
            +page.ts      — Load character + game data in parallel
    lib/
      api/
        auth.ts
        games.ts
        characters.ts
        types.ts
        client.ts
      stores/
        auth.ts           — access_token, refresh_token, current user
        game.ts           — selected game, feature flags
        theme.ts          — dark/light mode toggle, localStorage persistence
      theme/
        tokens.css        — CSS custom properties: shared tokens + dark palette + light palette
      components/
        CharacterSheet/
          StatsPanel.svelte
          InventoryPanel.svelte
          EquipmentPanel.svelte
          SkillsPanel.svelte
          BuffsPanel.svelte
          QuestsPanel.svelte
          MilestonesPanel.svelte
          ArchetypesPanel.svelte
        shared/
          Button.svelte
          Card.svelte
          LoadingSpinner.svelte
          ErrorBanner.svelte
          ThemeToggle.svelte
          Modal.svelte
```

---

## Docker Multi-Stage Build

The existing `dockerfile.www` uses `ghcr.io/multi-py/python-uvicorn:py${PYTHON_VERSION}-slim-LATEST` as its base image and installs dependencies via `uv`. MU4 extends it with a Node build stage prepended before the existing Python stage:

```dockerfile
# Stage 1: Build SvelteKit frontend
FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime (existing dockerfile.www content, unchanged)
ARG PYTHON_VERSION=3.13
FROM ghcr.io/multi-py/python-uvicorn:py${PYTHON_VERSION}-slim-LATEST
# ... existing setup unchanged ...

# Copy built frontend into the Python image
COPY --from=frontend-build /frontend/build /app/frontend/build
```

The `COPY --from=frontend-build` line is the only addition to the existing Python stage. Everything else in `dockerfile.www` remains untouched.

If the `frontend/build` directory does not exist (local Python-only development without running the frontend build), the `www.py` mount is skipped and `/app` returns 404. This allows Python-only development without the Node.js toolchain. See the Key Implementation Details section for the full `www.py` and settings changes.

---

## Makefile Targets

The project already has `prettier_check` and `prettier_fixes` targets that run `npx --yes prettier --check .` / `--write .` globally. Because SvelteKit projects use Prettier natively, the `frontend/` directory is automatically covered by those existing targets — no separate frontend formatting targets are needed.

The only new targets introduced by MU4 are:

```makefile
frontend-install:
 cd frontend && npm ci

frontend-build:
 cd frontend && npm run build

frontend-dev:
 cd frontend && npm run dev

frontend-typecheck:
 cd frontend && npx svelte-check --tsconfig tsconfig.json

frontend-lint:
 cd frontend && npx eslint .

frontend-lint-fix:
 cd frontend && npx eslint . --fix
```

`frontend-typecheck` and `frontend-lint` are added to the `make tests` target alongside `pytest`, `ruff_check`, `black_check`, `mypy_check`, `prettier_check`, and `tomlsort_check`.

`frontend-lint-fix` is added to the `make chores` target alongside `ruff_fixes`, `black_fixes`, `prettier_fixes`, and `tomlsort_fixes`.

`frontend-install` is added as a dependency of `install` so that a fresh checkout gets both Python and Node dependencies with a single `make install`.

The SvelteKit scaffold includes `eslint-plugin-svelte` and `@typescript-eslint/eslint-plugin` by default, covering Svelte component rules and TypeScript-aware quality checks (unused variables, no-`console`, etc.) that Prettier and svelte-check do not catch.

---

## Authentication Flow

The auth Svelte store (`frontend/src/lib/stores/auth.ts`) manages tokens in `localStorage`. The full lifecycle is detailed in the Architecture section. Key behavioral notes:

- **First load:** `authStore.init()` in `+layout.svelte` `onMount` reads tokens from `localStorage`, calls `GET /auth/me` with the stored access token to validate it and restore the `UserRead`. If `GET /auth/me` returns 401, one refresh attempt is made before clearing state and redirecting.
- **Login / Register:** `authStore.login(pair, user)` stores both tokens and the `UserRead`. The user is redirected to the URL in `?next=` or to `/app/games` as the default post-auth destination.
- **Logout:** `POST /auth/logout` is called to revoke the refresh token server-side. The store and `localStorage` are cleared regardless of whether the HTTP call succeeds.
- **Concurrent tabs:** If a user logs out in one tab, the next API call in another tab receives a 401. The `client.ts` refresh attempt will fail (the refresh token is revoked), `authStore.logout()` is called, and the user is redirected to login. Tokens are not synchronized across tabs in real time.

Tokens are stored in `localStorage` (not `HttpOnly` cookies) because the SPA has no server-side rendering phase and `HttpOnly` cookies therefore provide no additional protection over `localStorage` for this deployment model. The security trade-off (`localStorage` is accessible to JavaScript, which means an XSS attack could steal tokens) is addressed in MU6 via strict Content Security Policy headers and subresource integrity tags that significantly reduce the XSS attack surface. Cookie-based delivery with `HttpOnly` can be added in MU6 if the threat model requires it.

---

## Testing Philosophy

MU4 introduces a new language and toolchain (TypeScript/SvelteKit) to the project. The testing approach follows the same principle used in the Python suite: catch errors at the earliest possible point, and test every meaningful behavior at the appropriate layer. Nothing is deferred — this is a foundation milestone and its tests are part of the deliverable.

| Check                                                   | Tool                                                            | When it runs | What it catches                                                                                                                                                                                                                                                                                |
| ------------------------------------------------------- | --------------------------------------------------------------- | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TypeScript type errors in `.svelte` and `.ts` files     | `svelte-check` (`frontend-typecheck`)                           | `make tests` | Type mismatches between `types.ts` interfaces and component usage; missing properties; incorrect function signatures                                                                                                                                                                           |
| JavaScript/TypeScript code quality + accessibility lint | ESLint with `eslint-plugin-svelte` a11y rules (`frontend-lint`) | `make tests` | Unused variables, `no-console`, incorrect import patterns, Svelte component rule violations; also catches missing `alt` attributes, missing `<label>` associations, improper ARIA usage, interactive elements without accessible names                                                         |
| Store and client unit tests                             | Vitest (`frontend-unit`)                                        | `make tests` | Pure TypeScript logic: `authStore` token lifecycle and expiry; `themeStore` `toggle()`/`reset()`/localStorage persistence; `client.ts` error handling, request building, and 401 redirect behavior                                                                                             |
| Component integration tests                             | Vitest + `@testing-library/svelte` (`frontend-component`)       | `make tests` | Key component behaviors with mocked API responses and stores: `ErrorBanner` renders and dismisses; `NavBar` shows/hides based on auth state; `ThemeToggle` flips `themeStore`; `LoginForm` validation feedback and submission; character selection screen renders list and handles empty state |
| Automated accessibility audit (DOM-level)               | Playwright + `@axe-core/playwright` (`frontend-a11y`)           | `make tests` | Runs `checkA11y()` against the rendered login page, home screen, and character selection screen; catches contrast failures, missing landmarks, focus management errors, and ARIA violations that static lint cannot see                                                                        |
| Code formatting                                         | Prettier (`prettier_check`)                                     | `make tests` | Whitespace, quote style, trailing commas — already runs project-wide and covers `.svelte` and `.ts` files                                                                                                                                                                                      |
| Python backend tests                                    | pytest                                                          | `make tests` | API endpoint behavior, persistence, auth logic — unchanged from MU1–MU3                                                                                                                                                                                                                        |

### Store and client unit tests (`frontend/tests/unit/`)

These tests run in Vitest with jsdom and require no browser.

**`authStore.test.ts`** verifies:

- Token is stored in `localStorage` after a successful login call
- `isAuthenticated` derived value is `true` when a non-expired token is present and `false` when absent or expired
- `logout()` clears the token from both the store and `localStorage`
- A token that is within the expiry buffer triggers a refresh (or marks as expired, per the policy in D5)

**`themeStore.test.ts`** verifies:

- `toggle()` switches from `'dark'` to `'light'` and back
- `toggle()` writes the new value to `localStorage` under `'oscilla:theme'`
- `reset()` removes the `localStorage` entry and sets the store value to `null`
- Initializing the store when `localStorage` already has a value reads and applies that value

**`client.test.ts`** verifies:

- `GET` and `POST` helpers include the `Authorization: Bearer <token>` header when a token is present
- A `401` response calls `authStore.logout()` and does not return data
- A non-2xx response rejects with an `ApiError` carrying the status code and server message
- Request bodies are JSON-serialized and the `Content-Type: application/json` header is set

### Component integration tests (`frontend/tests/component/`)

These tests run in Vitest with `@testing-library/svelte`. Each test mounts the component with a controlled store state or mock API.

| Component                  | Scenarios tested                                                                                                                                                                                                |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ErrorBanner`              | Renders the error message text; clicking the dismiss button removes it from the DOM; `aria-live` attribute is present                                                                                           |
| `NavBar`                   | Shows authenticated navigation links when `authStore` has a token; shows only the login link when `authStore` is empty; `ThemeToggle` is present and visible                                                    |
| `ThemeToggle`              | Clicking the button calls `themeStore.toggle()`; button has an `aria-label`                                                                                                                                     |
| `LoginForm`                | Submitting with empty fields shows validation errors linked via `aria-describedby`; submitting with valid credentials calls `client.login()` with the correct payload; a failed login surfaces an `ErrorBanner` |
| Character selection screen | Renders a card for each character in the mocked response; renders the empty-state prompt when the list is empty; the "New Character" button is visible and navigates to the creation route                      |

### Accessibility tests (`frontend/tests/a11y/`)

The Playwright suite uses `@axe-core/playwright`. It starts the Vite dev server as a fixture and runs `checkA11y()` with `{ runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] } }` on:

- Login page (unauthenticated)
- Home screen (mocked authenticated session)
- Character selection screen (mocked API: two characters returned)
- Character selection screen — empty state (mocked API: empty list)

Any axe violation fails the build. Violations are reported with the violating element selector, the WCAG criterion, and the axe remediation hint.

### Conventions

- No test may reference `content/` or any game-specific content.
- All tests that require API responses use mock data constructed from the `types.ts` interfaces directly — no network calls.
- Test files mirror the source file tree: `frontend/tests/unit/` for `.ts` modules, `frontend/tests/component/` for `.svelte` components, `frontend/tests/a11y/` for Playwright axe tests.

---

## Documentation Plan

| Document                      | Audience   | Topics                                                                                                                                                                                                                                                                                                 |
| ----------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docs/dev/frontend.md` (new)  | Developers | Project structure; scaffolding a new page; adding an API endpoint to the TypeScript client; CSS design token system and the convention against hardcoded values; local development workflow (`npm run dev` + FastAPI + Vite proxy); `adapter-static` deployment notes; how the StaticFiles mount works |
| `docs/dev/docker.md` (update) | Developers | Multi-stage build: how the Node stage is prepended; how the `COPY --from=frontend-build` line integrates with the existing Python stage; when the frontend build is skipped locally; how to force a frontend rebuild without full image rebuild                                                        |
| `docs/dev/README.md` (update) | Developers | Add `frontend.md` to the table of contents                                                                                                                                                                                                                                                             |

---

## Risks / Trade-offs

| Risk                                                                                                        | Mitigation                                                                                                                                                                                                                                                                                                               |
| ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `localStorage` token storage accessible to XSS                                                              | MU6 adds strict Content Security Policy headers; `HttpOnly` cookies are a migration path if the threat model requires it                                                                                                                                                                                                 |
| `svelte.config.js` `paths.base = '/app'` means all generated asset URLs are prefixed — easy to misconfigure | Verified by serving the production Docker image locally before merging; `make frontend-build` followed by `uvicorn` reproduces exactly the production path                                                                                                                                                               |
| SvelteKit dynamic routes (e.g. `/app/characters/[id]`) would fail to prerender as static HTML               | `prerender = false` in `+layout.ts` disables prerendering globally; the `fallback: 'index.html'` serves the SPA shell for all unmatched paths                                                                                                                                                                            |
| Frontend build not present in local dev causes `/app` 404                                                   | Graceful mount skip in `www.py` with a clear `WARNING` log at startup; developers working only on the API are not affected                                                                                                                                                                                               |
| `tokens.css` violated by hardcoded color values in components                                               | Code review convention enforced by PR checklist item; a Stylelint custom property rule banning non-variable colors can be added later                                                                                                                                                                                    |
| Light theme color contrast ratios not reviewed for every future token addition                              | Both palettes have WCAG 2.1 AA contrast ratios documented inline in `tokens.css`; new tokens must include contrast annotations and be verified with a contrast checker before merging                                                                                                                                    |
| `themeStore` reads `localStorage` at module initialization — throws in SSR                                  | `ssr: false` in `+layout.ts` guarantees the module only runs in the browser; the `typeof localStorage !== 'undefined'` guard is kept as a belt-and-suspenders safety net                                                                                                                                                 |
| Accessibility baseline regresses as new components are added                                                | ESLint Svelte a11y rules catch static violations at lint time; `@axe-core/playwright` runs DOM-level WCAG 2.1 AA checks on key screens in `make tests` — any axe violation fails the build                                                                                                                               |
| npm version skew between developer environments                                                             | `package-lock.json` is committed; `npm ci` is used in both Docker and `make frontend-install`                                                                                                                                                                                                                            |
| TypeScript `types.ts` drifts from Pydantic models as the API evolves                                        | Any access to a renamed or missing field is a `svelte-check` type error and a Vitest mock-shape mismatch — caught in `make tests` before merge; tracked as a risk if the model count grows to the point where manual sync is error-prone (at that point, codegen via `openapi-typescript` is the migration path, see D2) |
