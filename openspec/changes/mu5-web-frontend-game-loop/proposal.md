# Proposal: MU5 — Web Frontend — Game Loop

## Why

The browser UI needs to close the loop: players must be able to actually play adventures, not just read their character sheets. This change wires the MU3 adventure execution API into the SvelteKit frontend, delivering a fully playable game in the browser.

This includes the SSE-driven narrative display, all decision-point UI components (choice menus, acknowledgement prompts, combat HUD, text input, skill menus), the overworld navigation screen, and crash recovery so browser refresh never loses game state.

## What Changes

- **New**: Narrative log component — SSE consumer that renders `narrative` events as paragraphs with typewriter-style pacing; accumulates the session log for in-page scroll history.
- **New**: Choice menu component — replaces the input area when a `choice` event arrives; submits the selected option to `POST /play/advance`.
- **New**: Acknowledgement prompt — replaces the input area when an `ack_required` event arrives; `Press Enter to continue` interaction.
- **New**: Combat HUD component — renders `combat_state` events as HP bars with combatant names and round counter.
- **New**: Text input component — handles `text_input` events (character naming steps, etc.).
- **New**: Skill menu component — handles `skill_menu` events with available skill display and selection.
- **New**: Adventure complete screen — rendered on `adventure_complete` event; shows outcome and returns to overworld.
- **New**: Overworld screen — current location, available adventure list, navigation options panel, character stat sidebar.
- **New**: Session takeover flow — when `POST /play/begin` or `/advance` returns `409 Conflict`, the UI shows the lock age and a "Take over this session" button that calls `POST /play/takeover`.
- **New**: Crash recovery — on page load or browser refresh during an active adventure, `GET /play/current` is fetched; the output log is re-rendered and the pending decision component is restored.
- **New**: Inventory equip/use controls on the overworld screen.
- **New**: Location and region navigation from the overworld screen.

## Capabilities

### New Capabilities

- `web-game-loop`: Fully playable adventures in the browser via SSE-streamed narrative and REST-committed decisions.
- `web-overworld`: Location navigation, adventure selection, and character management actions accessible from the browser overworld screen.
- `web-session-takeover-ui`: Frontend flow for detecting and recovering from stale session locks.
- `web-crash-recovery-ui`: Browser refresh restores the current adventure state without data loss.

## Impact

- `frontend/src/` — new Svelte components: narrative log, choice menu, ack prompt, combat HUD, text input, skill menu, overworld screen, adventure complete
- `frontend/src/lib/api.ts` — adventure execution endpoints and SSE client wired
- `docs/dev/` — frontend game loop architecture document

## Context

- **Overall architecture:** [frontend-roadmap.md](../../../frontend-roadmap.md) — all technology decisions, the full API surface, database schema changes, and the complete implementation phase breakdown for the Multi-User Platform.
- **Depends on:** [MU3 — Adventure Execution API](../mu3-adventure-execution-api/proposal.md) and [MU4 — Web Frontend — Foundation](../mu4-web-frontend-foundation/proposal.md)
- **Next:** [MU6 — Production Hardening](../mu6-production-hardening/proposal.md)
