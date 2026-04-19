---
name: frontend-dev
description: "Work on the Oscilla frontend (SvelteKit/Vite). Use when: writing or modifying any Svelte components, routes, stores, styles, or frontend tests; adding new UI features or pages; fixing frontend bugs; running frontend tests or type checks; managing npm dependencies; working on accessibility or usability; building production assets; or any task that touches files under frontend/."
---

# Frontend Development

> **context7**: If the `mcp_context7` tool is available, resolve and load the full `sveltekit` and `vite` documentation before proceeding:
> ```
> mcp_context7_resolve-library-id: "sveltekit"
> mcp_context7_get-library-docs: <resolved-id>
> mcp_context7_resolve-library-id: "vite"
> mcp_context7_get-library-docs: <resolved-id>
> ```

The Oscilla frontend is built with **SvelteKit** and bundled with **Vite**. Frontend source lives in `frontend/src/`. Tests live in `frontend/tests/`.

All `make` commands below must be run from the project root.

---

## Development Environment

**The preferred way to develop is with the full Docker Compose stack.** It provides a complete, working backend out of the box — authentication, database, API, and all services — and automatically reloads frontend changes via hot module replacement.

```bash
docker compose up -d   # Start the full stack (backend + frontend + gateway)
```

The application is available at `http://localhost`. Changes to `frontend/src/` appear with a very slight delay (due to polling) without restarting anything.

A default developer account is seeded automatically on first startup:

| Field    | Value             |
| -------- | ----------------- |
| Email    | dev@example.com   |
| Password | devpassword       |

See the `docker-compose` skill for full stack management commands (logs, restart, reset, etc.).

**Only use `make frontend_dev` when you need to work on the frontend in isolation** (e.g., no backend needed, or intentionally running against a separately started API). This starts the Vite dev server on your local machine without Docker, using the proxy config in `vite.config.ts` to forward API calls.

---

## Accessibility — The Top Priority

> **Oscilla aims to be extremely accessible to all players and authors. Accessibility is not optional and is not deferred — it is a first-class requirement for every UI change.**

Every new component or page must meet or exceed **WCAG 2.1 AA** as a minimum. Strive for AAA where practical. Specific requirements:

- **Keyboard navigation**: Every interactive element must be fully operable by keyboard alone. Tab order must be logical. Focus must be visible at all times.
- **Screen reader support**: All meaningful elements need descriptive `aria-label`, `aria-labelledby`, or `aria-describedby` attributes. Use semantic HTML elements (`<button>`, `<nav>`, `<main>`, `<section>`, `<article>`) — never fake interactive elements with `<div>` or `<span>`.
- **Color contrast**: Text and interactive elements must meet WCAG contrast ratios. Never rely on color alone to convey information.
- **Motion**: Respect `prefers-reduced-motion`. Animations and transitions must be suppressible.
- **Forms**: All inputs must have visible, associated `<label>` elements. Error messages must be announced to screen readers.
- **Images and icons**: All non-decorative images require `alt` text. Decorative images use `alt=""`.

Accessibility must be **proven with tests** (see below). Writing a component without an accompanying accessibility test is not acceptable.

---

## Usability

After accessibility, usability is the next priority. UI changes must be intentional and user-centered:

- Interactions must be discoverable — users should not need to guess how something works.
- Error states must be clear, actionable, and non-destructive.
- Loading and async states must provide visible feedback.
- The interface must degrade gracefully when the backend is slow or unavailable.
- Responsive layout is required — the UI must work on both desktop and mobile viewports.

---

## Testing Requirements

> **Playwright is a critical tool for frontend testing.** Load the `playwright-cli` skill before writing or debugging any Playwright tests — it covers the full API, selector strategies, and debugging workflows.

**Tests must be written alongside new functionality — not after.** Every new page or component needs:

1. **Accessibility tests** (`make frontend_a11y`) — use Playwright + axe-core to assert no accessibility violations on every new route or significant component.
2. **E2E tests** (`make frontend_e2e`) — cover the primary user flows for any new feature.
3. **Unit tests** (`make frontend_test`) — cover component logic, store behavior, and utility functions.

Tests live in `frontend/tests/`. Run the full suite before committing:

```bash
make frontend_playwright_all   # Accessibility + E2E across Chromium, Firefox, WebKit
make frontend_test             # Vitest unit tests
make frontend_check            # svelte-check type checking
```

| Command                        | What it does                                             |
| ------------------------------ | -------------------------------------------------------- |
| `make frontend_a11y`           | Playwright accessibility tests (axe-core)                |
| `make frontend_e2e`            | Playwright E2E tests via managed stack                   |
| `make frontend_playwright_all` | Accessibility + E2E across Chromium, Firefox, WebKit     |
| `make frontend_test`           | Vitest unit test suite (jsdom, no Playwright required)   |
| `make frontend_check`          | `svelte-check` type checking                             |

Playwright config files: `frontend/playwright.config.ts` (unit/E2E) and `frontend/playwright.e2e.config.ts` (full stack).

---

## Quick Commands

| Command                    | What it does                                     |
| -------------------------- | ------------------------------------------------ |
| `make frontend_install`    | Install npm dependencies (`npm install`)         |
| `make frontend_dev`        | Start the Vite dev server (standalone, no Docker)|
| `make frontend_build`      | Build production frontend assets                 |
| `make frontend_format_fix` | Auto-format frontend source files                |

The frontend formatting check is included in `make chores` and `make tests`.

---

## Dependency Management

```bash
# From frontend/ directory
npm install <package>             # Add a runtime dependency
npm install --save-dev <package>  # Add a dev dependency
npm uninstall <package>           # Remove a dependency
```

After changing `frontend/package.json`, commit both `package.json` and `package-lock.json`.

---

## File Structure

```
frontend/
├── src/
│   ├── routes/          # SvelteKit routes (+page.svelte, +layout.svelte)
│   ├── lib/
│   │   ├── components/  # Shared UI components
│   │   ├── stores/      # Writable stores (authStore, themeStore)
│   │   ├── api/         # Typed API models and endpoint wrappers
│   │   └── theme/       # CSS variable tokens (tokens.css)
├── static/              # Static assets served directly
├── tests/               # Playwright and Vitest tests
├── build/               # Production build output (gitignored)
├── svelte.config.js
├── vite.config.ts
└── package.json
```

---

## Notes

- The Vite dev proxy (in `vite.config.ts`) forwards `/auth`, `/games`, `/characters`, and `/overworld` to `http://localhost:8000` when running standalone.
- `adapter-static` is used so the app can be served by FastAPI `StaticFiles` without a Node runtime in production.

---

## Further Reading

- [docs/dev/frontend.md](../../docs/dev/frontend.md) — Full frontend developer guide covering the SvelteKit project layout, route structure, shared stores, typed API client (`frontend/src/lib/api/`), theme tokens, and architectural decisions (adapter-static, Vite proxy config).
- [SvelteKit Docs](https://kit.svelte.dev/docs)
- [Vite Docs](https://vitejs.dev/)
