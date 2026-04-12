# Proposal: MU3 — Adventure Execution API

## Why

The game loop — the core of Oscilla — must be accessible over HTTP. This change introduces the adventure execution endpoints that allow web clients to run the adventure pipeline, receive narrative output as a stream of Server-Sent Events, and resume from any interruption without data loss.

This is the most technically complex phase. It requires implementing the `WebCallbacks` concrete implementation of the `UICallbacks` protocol (renamed from `TUICallbacks` in this change), an SSE event queue, session locking with force-takeover support, and a crash-recovery table for narrative output.

## What Changes

- **New**: `TUICallbacks` protocol in `engine/pipeline.py` renamed to `UICallbacks`. All call sites updated. `TextualTUI` remains the terminal-specific concrete implementation. This rename is a prerequisite for introducing `WebCallbacks` without a naming conflict.
- **New**: `WebCallbacks` — implements `UICallbacks`, buffers output as SSE events into an async queue, accumulates events to `character_session_output` for crash recovery.
- **New**: `character_session_output` table — persists narrative output produced between overworld actions. Rows cleared when adventure completes or is abandoned.
- **New**: `GET /characters/{id}/play/current` — returns pending adventure state and output log for crash recovery.
- **New**: `POST /characters/{id}/play/begin` → SSE stream — starts an adventure from the overworld.
- **New**: `POST /characters/{id}/play/advance` → SSE stream — submits a choice or acknowledgement and runs the pipeline to the next decision point.
- **New**: `POST /characters/{id}/play/abandon` — exits the current adventure and returns to the overworld.
- **New**: `POST /characters/{id}/play/takeover` — force-releases a stale session lock and acquires it for the requesting session; returns current pending state. Restricted to the character's authenticated owner.
- **New**: `POST /characters/{id}/navigate` — moves the character to a new location within the current region.
- **New**: `GET /characters/{id}/overworld` — returns complete overworld state: current location, available adventures, navigation options, and region hierarchy (including node/edge graph for future map rendering).
- **New**: Web session lock: `session_token` column on `CharacterIterationRecord` (already exists for TUI crash recovery) is repurposed for web session locking; a new `session_token_acquired_at` nullable `DateTime` column is added to the same table. Unlike the TUI's always-succeeds `acquire_session_lock`, a new `acquire_web_session_lock` service function returns a `409 Conflict` when a live session exists, with `acquired_at` timestamp so the frontend can display lock age and offer force-takeover.
- **New**: SSE event type contract locked: `narrative`, `ack_required`, `choice`, `combat_state`, `text_input`, `skill_menu`, `adventure_complete`, `error`. All events carry a `context` object with at minimum `{location_ref, location_name, region_name}`.
- **New**: Alembic migration for `character_session_output` table.

## Capabilities

### New Capabilities

- `web-adventure-execution`: Full adventure game loop playable over HTTP via the Run-Until-Decision model with SSE narrative streaming.
- `web-session-locking`: Prevents concurrent sessions on the same character, with user-initiated force-takeover for stale locks.
- `adventure-crash-recovery`: Narrative output persisted to DB so browser refresh never loses game state.
- `web-overworld`: Location navigation and adventure selection via REST.

### Modified Capabilities

- `tui-callbacks`: `TUICallbacks` protocol renamed to `UICallbacks`. The TUI execution path is otherwise unchanged.

## Impact

- `oscilla/engine/pipeline.py` — `TUICallbacks` → `UICallbacks` rename; all call sites in `engine/steps/` updated
- `oscilla/engine/web_callbacks.py` — new file: `WebCallbacks` implementation
- `oscilla/routers/play.py` — new file: adventure execution endpoints
- `oscilla/models/character_session_output.py` — new SQLAlchemy model
- `oscilla/services/character.py` — new `acquire_web_session_lock`, `release_web_session_lock`, `force_acquire_web_session_lock`, `save_session_output`, `get_session_output`, `clear_session_output` functions; existing TUI `acquire_session_lock`/`release_session_lock` unchanged
- `db/versions/` — new Alembic migration for `character_session_output`
- `docs/dev/api.md` — adventure execution endpoint and SSE event documentation

## Context

- **Overall architecture:** [frontend-roadmap.md](../../../frontend-roadmap.md) — all technology decisions, the full API surface, database schema changes, and the complete implementation phase breakdown for the Multi-User Platform.
- **Depends on:** [MU2 — Game Discovery & Character Management API](../mu2-game-and-character-api/proposal.md)
- **Next:** [MU4 — Web Frontend — Foundation](../mu4-web-frontend-foundation/proposal.md) and [MU5 — Web Frontend — Game Loop](../mu5-web-frontend-game-loop/proposal.md) both depend on this change.
