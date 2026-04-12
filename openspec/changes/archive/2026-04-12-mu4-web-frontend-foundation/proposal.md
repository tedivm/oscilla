# Proposal: MU4 — Web Frontend — Foundation

## Why

With a complete API in place, players need a browser interface. This change introduces the SvelteKit frontend application covering authentication flows, game selection, character management, and a read-only character sheet. It establishes the Docker build pipeline, the TypeScript API client, and the feature-flag-driven panel system that all future frontend work builds on.

No game loop interaction ships in this change. Players can log in, create characters, and inspect their full character state, but cannot yet play adventures from the browser.

The frontend must be architected with future per-game customization in mind. Different games may ship with different color schemes, typography, background imagery, or component themes. The MU4 frontend does not implement customization, but its CSS and component structure must not make customization a rearchitecture. Concretely: all visual tokens (colors, fonts, spacing, backgrounds) must live in a single CSS custom properties layer that a future customization system can override, rather than being scattered as hardcoded values throughout components.

## What Changes

- **New**: SvelteKit + TypeScript project in `frontend/`.
- **New**: Docker multi-stage build — Node build stage compiles `frontend/` into `frontend/build`; Python image copies built assets; FastAPI serves them from `/app`.
- **New**: TypeScript API client layer typed against all Pydantic response models from MU1 and MU2.
- **New**: Base layout: navigation bar, auth state display, responsive shell.
- **New**: Pages: login, register, email verification landing, game selection, character list, character creation (game selection form only — `POST /characters` accepts only `game_name`; name, pronoun set, and archetype selection are handled by the game's triggered creation adventure in MU5).
- **New**: Character sheet page — all panels driven by `GameFeatureFlags`: stats, inventory (stackable + instance items), equipment, skills (with cooldown state), active buffs, quests (active + completed), prestige count, in-game time, current location. Read-only; no adventure actions.
- **New**: Feature-flag panel visibility — panels not supported by the current game are hidden, not just empty.
- **New**: CSS custom properties design token layer — all colors, fonts, spacing, and visual variables defined as CSS custom properties in a single theme file. Components reference only these tokens, never hardcoded values. This is the seam that a future per-game customization system will override; no customization logic ships in MU4.
- **New**: `Makefile` targets for frontend build, dev server, and type-check integrated into the project's developer workflow.
- **New**: GitHub Actions workflows for frontend Playwright and accessibility checks across Chromium/Firefox/WebKit.
- **Updated**: Dependabot configuration to include npm dependency updates for `frontend/`.

## Capabilities

### New Capabilities

- `web-ui-foundation`: Authenticated players can use a browser to register, log in, select a game, manage characters, and view their full character state.
- `feature-flag-panels`: Character sheet panel visibility is driven by server-reported game feature flags, not hardcoded frontend logic.
- `customization-ready-theme`: All visual design tokens are CSS custom properties in a single theme layer, making future per-game theming an additive override rather than a component-level rework.

## Impact

- `frontend/` — new SvelteKit project (entire directory)
- `dockerfile.www` — multi-stage build updated with Node build stage
- `compose.yaml` — frontend build step wired into development workflow
- `makefile` — frontend build, type-check, and dev server targets
- `.github/workflows/frontend-playwright.yaml` — browser-matrix frontend Playwright CI
- `.github/workflows/frontend-accessibility.yaml` — browser-matrix accessibility CI
- `.github/dependabot.yml` — npm updates for `frontend/`
- `docs/dev/` — new frontend development document covering project structure, build pipeline, and local dev setup

## Context

- **Overall architecture:** [frontend-roadmap.md](../../../frontend-roadmap.md) — all technology decisions, the full API surface, database schema changes, and the complete implementation phase breakdown for the Multi-User Platform.
- **Depends on:** [MU1 — Auth & User Accounts](../mu1-auth-and-accounts/proposal.md) and [MU2 — Game Discovery & Character Management API](../mu2-game-and-character-api/proposal.md)
- **Next:** [MU5 — Web Frontend — Game Loop](../mu5-web-frontend-game-loop/proposal.md) (also requires MU3)
