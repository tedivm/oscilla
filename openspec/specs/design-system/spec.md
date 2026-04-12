# Design System

## Purpose

Specifies the CSS custom properties token layer, the dark/light theme mechanism, the shared Svelte components, and the accessibility baseline that all MU4 pages build on. No component may use a hardcoded color, font, or spacing value — all visual tokens must be referenced through CSS custom properties defined in `frontend/src/lib/theme/tokens.css`.

---

## Requirements

### Requirement: CSS custom properties in `tokens.css`

`frontend/src/lib/theme/tokens.css` SHALL define all visual tokens as CSS custom properties. The file SHALL contain three sections:

1. **Color-scheme-neutral tokens** (`:root`) — typography, spacing, border-radius, and border-width properties that do not change between dark and light palettes.
2. **Dark palette** (`:root, [data-theme="dark"]`) — the default color palette.
3. **Light palette** (`[data-theme="light"]`) — the alternative color palette, also applied by a `@media (prefers-color-scheme: light) { :root:not([data-theme]) { ... } }` block to respect system preference when no manual override is set.

All component stylesheets SHALL reference only token names from this file and never use hardcoded color, font, or spacing values. This constraint is enforced by code review; a Stylelint rule banning non-variable colors can be added in a future change.

Both palettes SHALL have sufficient color contrast for WCAG 2.1 AA compliance (4.5:1 for body text, 3:1 for large text and UI components). Contrast ratios SHALL be documented inline in comments within `tokens.css`.

#### Scenario: Theme tokens are accessible in components

- **GIVEN** `tokens.css` is imported in the global styles
- **WHEN** a component uses `color: var(--color-text-primary)`
- **THEN** the rendered value matches the active palette's `--color-text-primary` token
- **AND** changing `document.documentElement.dataset.theme` from `"dark"` to `"light"` immediately updates the rendered color.

---

### Requirement: `themeStore` in `frontend/src/lib/stores/theme.ts`

A `themeStore` writable store SHALL manage the active theme preference:

- It SHALL read `localStorage.getItem('oscilla:theme')` at initialization and apply the stored value to `document.documentElement.dataset.theme` if present.
- `toggle()` SHALL switch the active theme between `'dark'` and `'light'`, persist to `localStorage`, and update `document.documentElement.dataset.theme`.
- `reset()` SHALL remove the `localStorage` entry and remove the `data-theme` attribute from `<html>`, restoring system-preference behavior.
- The store SHALL use `typeof localStorage !== 'undefined'` guards so that it does not throw if executed outside a browser context.

Because `client.ts` imports from this store, and both `client.ts` and other `.ts` modules must be able to read store state synchronously via `get(themeStore)`, the store SHALL use Svelte `writable` (not Svelte 5 runes), which are importable by plain TypeScript modules.

#### Scenario: toggle() persists preference

- **WHEN** `themeStore.toggle()` is called while the current theme is `"dark"`
- **THEN** `document.documentElement.dataset.theme` is `"light"`
- **AND** `localStorage.getItem('oscilla:theme')` is `"light"`.

#### Scenario: reset() removes override

- **WHEN** `themeStore.reset()` is called
- **THEN** `document.documentElement.dataset.theme` is absent
- **AND** `localStorage.getItem('oscilla:theme')` is `null`
- **AND** the browser's `prefers-color-scheme` media query controls the active palette.

---

### Requirement: Shared component library

The following shared components SHALL exist in `frontend/src/lib/components/shared/`:

| Component               | Purpose                                                                                                                                     |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `Button.svelte`         | Standard button with `variant` prop (`primary`\|`secondary`\|`danger`), `disabled` state, and loading spinner slot.                         |
| `Card.svelte`           | Surface container with `--color-bg-surface` background and `--shadow-card` shadow. Accepts default slot content.                            |
| `LoadingSpinner.svelte` | An accessible animated indicator (`role="status"`, `aria-label="Loading"`). Used within the three-state async pattern.                      |
| `ErrorBanner.svelte`    | Displays an error message with `aria-live="polite"` so screen readers announce it. Accepts `message: string` and optional dismiss callback. |
| `ThemeToggle.svelte`    | Icon-only button with `aria-label="Toggle theme"` that calls `themeStore.toggle()`. Placed in the `NavBar`.                                 |
| `Modal.svelte`          | Focus-trapped dialog with keyboard `Escape` dismissal. Requires `open: boolean` prop and `close` event.                                     |

All interactive elements SHALL have visible `:focus-visible` outlines using `--color-focus-ring`. No hardcoded color, font, or spacing value is permitted in any component.

#### Scenario: ErrorBanner announces to screen readers

- **GIVEN** an `ErrorBanner` is rendered with a non-empty `message`
- **THEN** the element has `aria-live="polite"` set
- **AND** the message text is visible in the DOM.

#### Scenario: ThemeToggle has accessible label

- **GIVEN** the `ThemeToggle` is rendered
- **THEN** the `<button>` element has an `aria-label` attribute with a non-empty value.

---

### Requirement: Root layout with NavBar and auth guard

`frontend/src/routes/+layout.svelte` SHALL be the root layout wrapping all pages. It SHALL:

1. In `onMount`, call `authStore.init()` (which hydrates tokens from `localStorage`, calls `GET /auth/me`, and handles the refresh-then-redirect flow) and then evaluate whether the current route requires auth.
2. Use `beforeNavigate` to guard all subsequent client-side navigations: if the destination route is in the protected set and `$isLoggedIn` is `false`, cancel the navigation and call `goto('/app/login?next=...')`.
3. Render a `NavBar` with authenticated links (`Games`, `Characters`) visible only when `$isLoggedIn` is `true`, and a `UserMenu` dropdown (display name, Profile, Logout) when authenticated.
4. Render a global `ErrorBanner` driven by `authStore.error` (auth-layer errors only — individual page data errors are handled locally).
5. Import `tokens.css` as the global stylesheet.

The route classification (protected vs. public) SHALL match the table in design D6 exactly.

`onMount` fires after the Svelte component tree is hydrated from `localStorage`, so `authStore.init()` runs before any route guard logic — preventing the redirect-loop that would occur if a `+layout.ts` load function tried to read `localStorage` before component mount.

#### Scenario: Unauthenticated user is redirected from protected route

- **GIVEN** the user is not logged in (`$isLoggedIn === false`)
- **WHEN** the user navigates to `/app/characters`
- **THEN** the navigation is cancelled and the user is redirected to `/app/login?next=%2Fapp%2Fcharacters`.

#### Scenario: Authenticated user on login page is redirected to games

- **GIVEN** the user is logged in (`$isLoggedIn === true`)
- **WHEN** the user navigates to `/app/login`
- **THEN** the user is redirected to `/app/games` (or the `?next=` URL if present).

#### Scenario: NavBar shows authenticated links when logged in

- **GIVEN** `$isLoggedIn === true`
- **THEN** `NavBar` renders visible "Games" and "Characters" navigation links and the `UserMenu`.

#### Scenario: NavBar hides authenticated links when logged out

- **GIVEN** `$isLoggedIn === false`
- **THEN** `NavBar` does not render the "Games" / "Characters" links or the `UserMenu`.
