# Proposal: MU2 — Game Discovery & Character Management API

## Why

With authentication in place, the next requirement is an API surface that lets authenticated web users discover available games, manage characters, and read complete character state. This change also locks the `CharacterStateRead` response schema — the contract that all frontend panels will depend on for the lifetime of the platform. Getting this schema right before any frontend ships avoids breaking API changes later.

This change introduces no game loop execution. All endpoints are read-only for character state; character creation and deletion are the only mutations.

## What Changes

- **New**: Content registry loaded once at app startup via FastAPI lifespan handler, stored in `app.state.registries: Dict[str, ContentRegistry]`. Restart required to reload content.
- **New**: `GET /games` — list all loaded games with metadata and feature flags.
- **New**: `GET /games/{game_name}` — single game metadata including `GameFeatureFlags` (drives frontend panel visibility).
- **New**: `GET /characters` — list characters for the authenticated user, optionally filtered by game.
- **New**: `POST /characters` — create a new character for the authenticated user.
- **New**: `GET /characters/{id}` — full `CharacterStateRead` (complete schema: stats, inventory, equipment, milestones, quests, skills, buffs, prestige, location, in-game time, and stub fields for roadmap features).
- **New**: `DELETE /characters/{id}` — delete a character owned by the authenticated user.
- **New**: `PATCH /characters/{id}` — rename a character.
- **New**: Pydantic models: `GameRead`, `GameFeatureFlags`, `CharacterSummaryRead`, `CharacterStateRead`, `CharacterCreate`.
- **Updated**: `oscilla/www.py` — games and characters routers mounted; content registry loaded in lifespan.

## Capabilities

### New Capabilities

- `game-discovery`: Authenticated web users can enumerate available games and their feature flags to drive conditional UI panel rendering.
- `character-management`: Authenticated web users can create, list, read, rename, and delete their own characters via the REST API.

## Impact

- `oscilla/www.py` — lifespan handler loads content registries; game and character routers mounted
- `oscilla/routers/games.py` — new file: game discovery endpoints
- `oscilla/routers/characters.py` — new file: character CRUD endpoints
- `oscilla/models/api/` — new Pydantic read/create models for games and characters
- `docs/dev/api.md` — game and character endpoint documentation

## Context

- **Overall architecture:** [frontend-roadmap.md](../../../frontend-roadmap.md) — all technology decisions, the full API surface, database schema changes, and the complete implementation phase breakdown for the Multi-User Platform.
- **Depends on:** [MU1 — Auth & User Accounts](../mu1-auth-and-accounts/proposal.md)
- **Next:** [MU3 — Adventure Execution API](../mu3-adventure-execution-api/proposal.md)
