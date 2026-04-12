# Design: MU5 — Web Frontend — Game Loop

## Context

MU4 delivers the static shell, authentication flows, and character management UI. MU3 delivers the SSE-based adventure execution API. This change wires them together: the browser becomes a fully playable Oscilla client.

The game loop UI has two distinct interaction modes that share the same screen:

1. **Adventure mode** — the player is inside a running adventure. The screen is dominated by the narrative log and the current decision component (choice menu, ack button, combat HUD, text input, or skill menu). Every action submits `POST /play/advance` and opens a new SSE stream.

2. **Overworld mode** — the player is at a location, not in an active adventure. The screen shows the current location, available adventures, navigation options, and a compact character sidebar. Actions submit to `/navigate` or `/play/begin`.

The fundamental challenge of the game loop UI is **SSE stream management**: the `EventSource` API is used for reading, but SSE is one-way — decisions are submitted via `fetch`. The client must manage the lifecycle of the current stream, prevent multiple concurrent streams, and handle reconnection and crash recovery gracefully.

---

## Goals / Non-Goals

**Goals:**

- Narrative log component — renders accumulated `narrative` events with paragraph-by-paragraph typewriter cadence; scroll anchors on new content.
- Choice menu component — activated by `choice` SSE events; submits selection via `POST /play/advance`.
- Acknowledgement prompt — activated by `ack_required` events; keyboard shortcut (Enter/Space) and click button.
- Combat HUD component — renders `combat_state` events as HP bars; round counter; combatant name display.
- Text input component — handles `text_input` events; free-form text entry.
- Skill menu component — handles `skill_menu` events; displays skill cards with names and descriptions.
- Adventure complete screen — renders `adventure_complete` event; displays outcome; routes to overworld.
- Overworld screen — current location, available adventures, navigation options, compact character sidebar.
- Session takeover flow — `409 Conflict` on begin/advance triggers a modal with lock age and "Take over" button.
- Crash recovery — `GET /play/current` on page load restores session output and pending decision.
- Inventory quick-actions on overworld screen (equip/use).
- Location and region navigation from overworld screen.

**Non-Goals:**

- NPC portrait display — reserved for a future change when content manifests support `image_path`.
- Region map SVG rendering — the `OverworldStateRead.region_graph` data is available; the SVG render component is a future change.
- Talent tree DAG panel — roadmap.
- Faction reputation panel — roadmap.
- Inventory drag-and-drop between inventory and storage — roadmap.
- Sound effects / music — explicitly out of scope for this platform layer.

---

## Decisions

### D1: SSE stream managed via a Svelte store, not `EventSource` directly

**Decision:** A `gameSession` Svelte store manages the lifecycle of the current SSE stream. Components read from the store; only the store interacts with `EventSource` and `fetch`.

```typescript
// frontend/src/lib/stores/gameSession.ts

interface GameSessionState {
  mode: "idle" | "loading" | "adventure" | "overworld" | "complete";
  narrativeLog: NarrativeEntry[];
  pendingEvent: SSEEvent | null;
  overworldState: OverworldStateRead | null;
  error: string | null;
}
```

When `POST /play/begin` or `/advance` is called:

1. The store sets `mode: "loading"` and clears `pendingEvent`.
2. An `EventSource` is opened on the SSE endpoint.
3. Each event arrives and is dispatched:
   - `narrative` → appended to `narrativeLog`.
   - `combat_state`, `choice`, `ack_required`, `text_input`, `skill_menu` → stored as `pendingEvent`.
   - `adventure_complete` → `mode` set to `"complete"`.
   - `error` → `error` field set; `mode` set to `"overworld"` or `"idle"`.
4. When the stream closes (server-side close after decision event), the `EventSource` is closed.
5. `mode` is set to `"adventure"` with the pending event in place.

**Why a store and not a component-local EventSource:** Multiple components need access to the session state (`narrative log`, `pending event display`, `character sidebar`). A store provides a single source of truth and eliminates prop-drilling.

**EventSource close detection:** The browser `EventSource` does not expose a "stream closed" event — it silently reconnects on close. To prevent reconnection, the store uses a `CustomEventSource` wrapper that emits a `stream-end` event when the server closes cleanly (flagged by a `event: stream-end` SSE event emitted by the server before closing).

---

### D2: Narrative log with typewriter cadence

**Decision:** The narrative log appends new `narrative` events as paragraphs. Each paragraph renders with a CSS animation (`opacity: 0 → 1`, duration 300ms) rather than a character-by-character typewriter effect. The rationale: a character-by-character typewriter requires knowing the text length ahead of time and coordinating animation timing. CSS opacity fade is simpler, equally readable, and does not delay the player from seeing the full text immediately.

The log maintains scroll position: new paragraphs are added at the bottom, and the container auto-scrolls to the bottom unless the player has manually scrolled up (in which case, a "Scroll to bottom" button appears).

The log is bounded to the **current session** (since the last overworld entry or adventure begin). Older sessions are not shown — this prevents the log from becoming unboundedly long. The full narrative history feature (if desired) is a future change.

---

### D3: Decision component swapping via Svelte `{#if}` blocks

**Decision:** The input area below the narrative log is a single `<div>` that renders a different component based on `$gameSession.pendingEvent.type`:

```svelte
<!-- frontend/src/routes/characters/[id]/play/+page.svelte -->
{#if pending?.type === 'choice'}
  <ChoiceMenu event={pending} onSelect={handleChoice} />
{:else if pending?.type === 'ack_required'}
  <AckPrompt onAck={handleAck} />
{:else if pending?.type === 'combat_state'}
  <CombatHUD event={pending} onAck={handleAck} />
{:else if pending?.type === 'text_input'}
  <TextInputForm event={pending} onSubmit={handleTextInput} />
{:else if pending?.type === 'skill_menu'}
  <SkillMenu event={pending} onSelect={handleSkillChoice} />
{:else if mode === 'loading'}
  <LoadingSpinner label="Running adventure..." />
{:else if mode === 'complete'}
  <AdventureCompleteScreen event={completeEvent} onContinue={handleAdventureComplete} />
{/if}
```

Each decision component receives a callback prop (e.g. `onSelect`, `onAck`) and calls it when the player acts. The page handler is the only place that calls the API; components are pure UI.

> **Svelte 5 note:** Svelte 5 replaces `createEventDispatcher` and `on:eventname` component event syntax with callback props. Each decision component declares `let { event, onSelect } = $props()` and calls `onSelect(value)` directly. The parent passes `onSelect={handler}`. This is the Svelte 5 canonical pattern. The `{#if}`/`{:else if}` block syntax itself is unchanged.

---

### D4: Keyboard shortcuts for common interactions

**Decision:** The acknowledgement prompt (`ack_required`) responds to `Enter` or `Space` in addition to the button click. The choice menu responds to number keys `1`–`9` for `options[0]`–`options[8]`. These shortcuts are registered via `svelte:window` event handlers that are active only when the corresponding component is mounted, preventing conflicts.

These shortcuts match the TUI experience for players who regularly use both interfaces.

> **Svelte 5 note:** In Svelte 5, `<svelte:window>` uses the same attribute-style event handlers as DOM elements: `<svelte:window onkeydown={handleKey} />` (not `on:keydown`). The shortcut handlers are conditional on the pending component being mounted, not on the svelte:window element — the handler function checks `if (!pending) return;` at the top and ignores irrelevant keys.

---

### D5: Session conflict handled by a non-blocking modal

**Decision:** When `POST /play/begin` or `/advance` returns `409 Conflict`, the `gameSession` store fires a `sessionConflict` event. The page renders a `<SessionConflictModal>` with:

- "Another session is active since `<time>`."
- "Take over this session" button → calls `POST /play/takeover` and resumes.
- "Cancel" button → returns to the overworld without attempting takeover.

The modal is non-blocking (not a full-page overlay) so the player can see the overworld state while deciding.

---

### D6: Crash recovery on page load

**Decision:** The play page `+page.ts` load function calls `GET /characters/{id}/play/current` before rendering. If the response contains a `pending_event` and a non-empty `session_output`, the `gameSession` store is initialized from this state — the narrative log is pre-populated and the decision component is restored. The player sees the adventure in progress immediately, as if they never left.

If `session_output` is empty and `pending_event` is null, the player is on the overworld and the store initializes in `"overworld"` mode.

> **Why use a `+page.ts` load function here?** D8 from MU4 established the `onMount` + `client.ts` pattern for data fetching. That pattern is the default for most pages. The play page uses a load function because SvelteKit guarantees the load function completes before the page component renders — this means the initial `gameSession` state is always populated before any component mounts, avoiding a loading flash or double-render. Because `ssr: false` is inherited from the root `+layout.ts`, the load function runs exclusively in the browser; `get(authStore)` is available when it executes. The load function calls the `client.ts` `request()` wrapper for auth injection, not the raw `fetch` parameter — see implementation details below.

**Alternatives considered:**

- `onMount` fetch in the page component — the narrative log would render empty, then populate after mount, causing a visible flash. A load function avoids this.
- Pre-populate from character sheet `GET /characters/{id}` which may include current play state — rejected. It conflates the character sheet and the play screen's data requirements and risks stale data.

---

### D7: Navigation guard hard-blocks leaving mid-adventure

**Decision:** The root `+layout.svelte` `beforeNavigate` guard checks the `gameSession` store. If `mode === 'adventure'` or `mode === 'loading'`, navigating away from the play page is **unconditionally cancelled** — no confirmation dialog, no escape hatch. The adventure must end through an in-game mechanism (completion, abandonment, or an explicit "leave adventure" action that calls `gameSession.close()`) before the player can navigate elsewhere.

```svelte
<!-- +layout.svelte addition -->
<script>
  import { beforeNavigate } from '$app/navigation';
  import { gameSession } from '$lib/stores/gameSession';

  beforeNavigate(({ cancel, from, to }) => {
    const isLeavingPlay = from?.url.pathname.includes('/play') && !to?.url.pathname.includes('/play');
    if (isLeavingPlay && ($gameSession.mode === 'adventure' || $gameSession.mode === 'loading')) {
      cancel();
    }
  });
</script>
```

The play screen UI must therefore provide an explicit abandonment path (e.g., a menu item or button) that calls `gameSession.close()` before programmatically navigating away. Any UI that lets the player exit an active adventure is responsible for calling `gameSession.close()` first.

**Why hard-block instead of confirm:** The confirmation dialog approach was considered and rejected. A "leave anyway?" prompt creates a path to bypass triggered adventures — specifically game-flow-initiated adventures such as the post-character-creation tutorial that the engine starts automatically. If a player can dismiss these with a confirmation, the engine state and the UI state desync: the engine still has an active session, but the frontend has navigated away. The hard block, combined with the forced redirect in D8, ensures the frontend always reflects the true engine state.

**Alternatives considered:**

- Confirmation dialog — rejected. See rationale above; creates a bypass path for triggered adventures.
- Guard inside the play page with `onNavigate` — possible, but a root layout guard is consistent with the MU4 auth guard pattern and is harder to accidentally omit from a new route.

---

### D8: Active adventure forces redirect to play screen

**Decision:** An active adventure takes over the frontend regardless of how the player arrived at their current screen. Two mechanisms enforce this:

**Mechanism 1 — Character-scoped layout load function.** A `+layout.ts` at `routes/characters/[id]/` runs before any character-scoped page renders. It calls `GET /characters/{id}/play/current`. If the response contains a non-null `pending_event`, it throws a SvelteKit `redirect(307, ...)` to `/characters/[id]/play`. This catches:

- A player navigating directly to the character sheet URL while an adventure is in progress.
- A player returning to the app after a session gap, when the character already has an active adventure (e.g., triggered by character creation).
- A triggered adventure racing with a navigation: if the player clicks the character name link at the same time the engine auto-starts a tutorial adventure, the layout load resolves the adventure first.

```typescript
// routes/characters/[id]/+layout.ts
import { redirect } from "@sveltejs/kit";
import { apiFetch } from "$lib/api/client.js";
import type { PendingStateRead } from "$lib/api/types.js";

export async function load({ params }) {
  // apiFetch injects the access token automatically; root layout guard handles unauthenticated.
  const current = await apiFetch<PendingStateRead>(
    `/characters/${params.id}/play/current`,
  );
  if (current.pending_event !== null) {
    throw redirect(307, `/characters/${params.id}/play`);
  }
  return {};
}
```

**Mechanism 2 — Overworld triggered-adventure detection.** While the player is on the overworld screen (`mode === 'overworld'`), the `OverworldView` component polls `GET /characters/{id}/play/current` on a short interval (5 seconds) or listens for a `triggered_adventure` SSE event if the backend emits one. When either signal fires with a non-null `pending_event`, the `gameSession` store transitions to `mode: 'loading'` and `gameSession.begin()` is called — which starts the adventure SSE stream and switches the play screen into adventure mode without any navigation. The overworld components unmount and the adventure screen mounts in their place, because the `+page.svelte` renders conditionally on `$gameSession.mode`.

> **Why polling and not pure SSE for triggered-adventure detection?** The overworld view does not have a persistent SSE connection open — SSE is only used during an active adventure session. An interval check is sufficient for the character-creation use case (the adventure is triggered server-side almost immediately after creation). If real-time push is needed in a future change, the overworld can open a lightweight notification SSE channel.

**What this covers:**

| Scenario                                                            | Mechanism                                |
| ------------------------------------------------------------------- | ---------------------------------------- |
| Player navigates to character sheet while adventure is active       | Layout load redirect (Mechanism 1)       |
| Player opens app fresh; character has a triggered pending adventure | Layout load redirect (Mechanism 1)       |
| Engine auto-starts tutorial adventure while player is on overworld  | Overworld poll / SSE event (Mechanism 2) |
| Player tries to use browser back/forward to escape play screen      | D7 `beforeNavigate` hard cancel          |
| Player types a non-play URL directly into the address bar           | Layout load redirect (Mechanism 1)       |

**Alternatives considered:**

- Rely on D7 `beforeNavigate` alone — does not cover fresh page loads, direct URL entry, or out-of-band triggered adventures.
- Push redirect via SSE — requires a persistent connection on all screens; more complexity than the use case warrants in MU5.
- Check for active adventure only on the character list screen when selecting a character — misses the cases where the player is already inside a character-scoped route when the adventure is triggered.

---

## Component Inventory

### Adventure Screen (`/characters/[id]/play`)

| Component                 | File                                             | Responsibility                                                          |
| ------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------- |
| `NarrativeLog`            | `components/Game/NarrativeLog.svelte`            | Renders accumulated narrative entries with fade-in animation            |
| `ChoiceMenu`              | `components/Game/ChoiceMenu.svelte`              | Grid of option buttons; keyboard shortcuts 1–9                          |
| `AckPrompt`               | `components/Game/AckPrompt.svelte`               | Single button; Enter/Space keyboard shortcut                            |
| `CombatHUD`               | `components/Game/CombatHUD.svelte`               | HP bars, combatant names, round counter; ack required after display     |
| `TextInputForm`           | `components/Game/TextInputForm.svelte`           | Labeled text input and submit button                                    |
| `SkillMenu`               | `components/Game/SkillMenu.svelte`               | Skill cards with name, description, cooldown state; selection or cancel |
| `AdventureCompleteScreen` | `components/Game/AdventureCompleteScreen.svelte` | Outcome banner, summary, "Return to overworld" button                   |
| `SessionConflictModal`    | `components/Game/SessionConflictModal.svelte`    | Lock conflict display with takeover and cancel actions                  |

### Overworld Screen (`/characters/[id]/play` when `mode === "overworld"`)

| Component               | File                                                | Responsibility                                                          |
| ----------------------- | --------------------------------------------------- | ----------------------------------------------------------------------- |
| `OverworldView`         | `components/Overworld/OverworldView.svelte`         | Container; assembles location, adventure list, navigation, sidebar      |
| `LocationInfo`          | `components/Overworld/LocationInfo.svelte`          | Location name, region name, description (from future manifest field)    |
| `AdventureList`         | `components/Overworld/AdventureList.svelte`         | Available adventures; calls `POST /play/begin` on selection             |
| `NavigationPanel`       | `components/Overworld/NavigationPanel.svelte`       | Adjacent location options; calls `POST /navigate`                       |
| `CharacterSidebar`      | `components/Overworld/CharacterSidebar.svelte`      | Compact stats, HP, active buffs, quick-access skills                    |
| `InventoryQuickActions` | `components/Overworld/InventoryQuickActions.svelte` | Equip and use actions for inventory items (calls future item endpoints) |

---

## Architecture

### Component Hierarchy

The play route delivers both the adventure screen and the overworld screen from the same URL (`/characters/[id]/play`). Mode switching is driven entirely by the `gameSession` store's `mode` field — no routing occurs between adventure and overworld.

```
PlayPage (/characters/[id]/play)
├── (when mode === 'adventure' | 'loading' | 'complete')
│   ├── NarrativeLog
│   │   └── NarrativeEntry (×N, fade-in animated)
│   ├── DecisionArea
│   │   ├── ChoiceMenu          (when pendingEvent.type === 'choice')
│   │   ├── AckPrompt           (when pendingEvent.type === 'ack_required')
│   │   ├── CombatHUD           (when pendingEvent.type === 'combat_state')
│   │   ├── TextInputForm       (when pendingEvent.type === 'text_input')
│   │   ├── SkillMenu           (when pendingEvent.type === 'skill_menu')
│   │   ├── LoadingSpinner      (when mode === 'loading')
│   │   └── AdventureCompleteScreen (when mode === 'complete')
│   └── SessionConflictModal    (overlaid on 409 Conflict)
│
└── (when mode === 'overworld')
    └── OverworldView
        ├── LocationInfo
        ├── AdventureList
        ├── NavigationPanel
        └── CharacterSidebar
            └── InventoryQuickActions (read-only in MU5)

NavBar + ErrorBanner are inherited from the root +layout.svelte and always present.
```

### Data Flow — SSE Lifecycle

```
User action (begin | advance)
  │
  ▼
PlayPage handler  (handleChoice / handleAck / handleTextInput / handleSkillChoice)
  │  calls gameSession.begin(characterId, adventureRef) or gameSession.advance(characterId, decision)
  ▼
gameSession store
  │  sets mode: 'loading', clears pendingEvent, cancels any active stream generator
  │  calls play.ts fetchSSE(POST /play/begin or /play/advance)
  ▼
fetchSSE async generator  (api/play.ts)
  │  auth token injected via get(authStore).accessToken
  │  response.body ReadableStream parsed line-by-line via parseSSEBuffer
  ▼
gameSession store  (dispatching each yielded SSEEvent)
  │  type: 'narrative'          → append to narrativeLog
  │  type: 'combat_state'       → set pendingEvent, mode: 'adventure'
  │  type: 'choice'             → set pendingEvent, mode: 'adventure'
  │  type: 'ack_required'       → set pendingEvent, mode: 'adventure'
  │  type: 'text_input'         → set pendingEvent, mode: 'adventure'
  │  type: 'skill_menu'         → set pendingEvent, mode: 'adventure'
  │  type: 'adventure_complete' → set completeEvent, mode: 'complete'
  │  type: 'error'              → set error, mode: 'overworld'
  │  stream ends (done=true)    → close generator, mode stays
  ▼
Components re-render reactively from store state
  (narrative log appends, decision component swaps)
```

### Auth Token Lifecycle (inherited from MU4)

The `gameSession` store is a plain `.ts` module (not a `.svelte.ts` file), so it uses `get(authStore)` from `svelte/store` to read the current access token before each `fetchSSE` call. Token refresh is handled by `client.ts` for standard JSON requests. For SSE streams, the token is read once at stream-open time — mid-stream token expiry is handled at the server side (the server honors the token for the life of the stream; if the token expires during a long stream the server closes it with a `type: 'error'` event, which the store catches and calls `authStore.refreshTokens()` before re-opening the stream).

---

## Key Implementation Details

### `frontend/src/lib/stores/gameSession.ts`

> **Why `writable` store and not Svelte 5 runes?** Same reason as `auth.ts` in MU4: `gameSession` must be readable from `+layout.svelte` (for D7 navigation hard-block) and from `api/play.ts` (for cancelling the active stream generator before beginning a new one). It also must be readable from `routes/characters/[id]/+layout.ts` (for the D8 triggered-adventure detection that calls `gameSession.begin()` from the overworld). Cross-boundary state shared between `.ts` modules and `.svelte` components requires the `writable` store API — runes are only available in `.svelte`/`.svelte.ts` contexts.

```typescript
import { writable, get } from "svelte/store";
import type { OverworldStateRead } from "$lib/api/types";
import { fetchSSE } from "$lib/api/play";

export type SSEEventType =
  | "narrative"
  | "combat_state"
  | "choice"
  | "ack_required"
  | "text_input"
  | "skill_menu"
  | "adventure_complete"
  | "error";

export interface NarrativeEntry {
  id: string; // nanoid; unique key for {#each}
  text: string;
}

export interface SSEEvent {
  type: SSEEventType;
  data: unknown; // narrowed per-type in each component's $props
}

/**
 * Decision payload sent to POST /play/advance.
 * Mirrors the backend AdvanceRequest Pydantic model.
 * Exactly one field should be populated per advance call.
 */
export interface AdvanceDecision {
  choice?: number; // 1-based choice index for 'choice' events
  ack?: boolean; // true for 'ack_required' events
  text_input?: string; // player response for 'text_input' events
  skill_choice?: number; // 1-based skill index for 'skill_menu' events
}

export interface GameSessionState {
  mode: "idle" | "loading" | "adventure" | "overworld" | "complete";
  narrativeLog: NarrativeEntry[];
  pendingEvent: SSEEvent | null;
  completeEvent: SSEEvent | null;
  overworldState: OverworldStateRead | null;
  error: string | null;
}

const INITIAL: GameSessionState = {
  mode: "idle",
  narrativeLog: [],
  pendingEvent: null,
  completeEvent: null,
  overworldState: null,
  error: null,
};

function createGameSession() {
  const { subscribe, set, update } = writable<GameSessionState>(INITIAL);

  let activeGenerator: AsyncGenerator<SSEEvent> | null = null;

  async function runStream(gen: AsyncGenerator<SSEEvent>): Promise<void> {
    update((s) => ({ ...s, mode: "loading", pendingEvent: null, error: null }));
    try {
      for await (const event of gen) {
        if (gen !== activeGenerator) return; // superseded by a newer stream
        update((s) => applyEvent(s, event));
      }
    } catch (e) {
      update((s) => ({
        ...s,
        mode: "overworld",
        error: e instanceof Error ? e.message : "Stream error",
      }));
    }
  }

  return {
    subscribe,

    /** Initialize from crash-recovery data returned by the load function. */
    init(playState: {
      narrativeLog: NarrativeEntry[];
      pendingEvent: SSEEvent | null;
      overworldState: OverworldStateRead | null;
    }): void {
      const mode = playState.pendingEvent ? "adventure" : "overworld";
      set({
        mode,
        narrativeLog: playState.narrativeLog,
        pendingEvent: playState.pendingEvent,
        completeEvent: null,
        overworldState: playState.overworldState,
        error: null,
      });
    },

    async begin(characterId: string, adventureRef: string): Promise<void> {
      const gen = fetchSSE(`/characters/${characterId}/play/begin`, {
        adventure_ref: adventureRef,
      });
      activeGenerator = gen;
      await runStream(gen);
    },

    async advance(
      characterId: string,
      decision: AdvanceDecision,
    ): Promise<void> {
      // Spread the decision fields directly to match the backend AdvanceRequest model.
      const gen = fetchSSE(`/characters/${characterId}/play/advance`, decision);
      activeGenerator = gen;
      await runStream(gen);
    },

    /** Close any active stream (called by in-game abandon action before programmatic navigation; see D7). */
    close(): void {
      activeGenerator = null;
      update((s) => ({ ...s, mode: "idle" }));
    },
  };
}

function applyEvent(s: GameSessionState, event: SSEEvent): GameSessionState {
  switch (event.type) {
    case "narrative":
      return {
        ...s,
        narrativeLog: [
          ...s.narrativeLog,
          {
            id: crypto.randomUUID(),
            text: (event.data as { text: string }).text,
          },
        ],
      };
    case "adventure_complete":
      return { ...s, mode: "complete", completeEvent: event };
    case "error":
      return {
        ...s,
        mode: "overworld",
        error: (event.data as { message: string }).message,
      };
    default:
      // All decision event types
      return { ...s, pendingEvent: event, mode: "adventure" };
  }
}

export const gameSession = createGameSession();
```

### `frontend/src/lib/api/play.ts`

```typescript
import { get } from "svelte/store";
import { authStore } from "$lib/stores/auth";
import { apiFetch, ApiError } from "$lib/api/client.js";
import type {
  SSEEvent,
  NarrativeEntry,
  AdvanceDecision,
} from "$lib/stores/gameSession";
import type { OverworldStateRead, PendingStateRead } from "$lib/api/types.js";

export interface CurrentPlayState {
  narrativeLog: NarrativeEntry[];
  pendingEvent: SSEEvent | null;
  overworldState: OverworldStateRead | null;
}

/**
 * Called from +page.ts load function; returns current session state for crash recovery.
 *
 * Fetches GET /play/current (returns PendingStateRead) and transforms the persisted
 * session_output into a client-side NarrativeEntry[]. When no adventure is in progress,
 * also fetches GET /overworld to populate overworldState for the initial render.
 */
export async function getCurrentPlayState(
  characterId: string,
): Promise<CurrentPlayState> {
  const pending = await apiFetch<PendingStateRead>(
    `/characters/${characterId}/play/current`,
  );

  // Reconstruct the narrative log from the persisted session output.
  const narrativeLog: NarrativeEntry[] = (pending.session_output ?? [])
    .filter((e: Record<string, unknown>) => e["type"] === "narrative")
    .map((e: Record<string, unknown>) => ({
      id: crypto.randomUUID(),
      text: (e["data"] as { text: string }).text,
    }));

  const pendingEvent = pending.pending_event
    ? (pending.pending_event as SSEEvent)
    : null;

  // Fetch overworld state separately when no active adventure is in progress.
  const overworldState = pendingEvent
    ? null
    : await apiFetch<OverworldStateRead>(
        `/characters/${characterId}/overworld`,
      );

  return { narrativeLog, pendingEvent, overworldState };
}

/**
 * Opens a POST SSE stream and yields each parsed event.
 * Auth token is read once before the request. Mid-stream expiry is handled
 * by the server closing the stream with a type:'error' event.
 */
export async function* fetchSSE(
  url: string,
  body: object,
): AsyncGenerator<SSEEvent> {
  const { accessToken } = get(authStore);
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (response.status === 409) {
    throw new ApiError("Session conflict", 409, "session_conflict");
  }
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(`HTTP ${response.status}`, response.status, body);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, remaining } = parseSSEBuffer(buffer);
    for (const event of events) yield event;
    buffer = remaining;
  }
}

function parseSSEBuffer(buffer: string): {
  events: SSEEvent[];
  remaining: string;
} {
  const events: SSEEvent[] = [];
  const blocks = buffer.split("\n\n");
  const remaining = blocks.pop() ?? "";
  for (const block of blocks) {
    let eventType = "message";
    let dataLine = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) eventType = line.slice(7).trim();
      if (line.startsWith("data: ")) dataLine = line.slice(6).trim();
    }
    if (dataLine) {
      try {
        events.push({
          type: eventType as SSEEvent["type"],
          data: JSON.parse(dataLine),
        });
      } catch {
        /* malformed JSON — skip */
      }
    }
  }
  return { events, remaining };
}
```

### `frontend/src/routes/characters/[id]/play/+page.ts`

```typescript
import type { PageLoad } from "./$types";
import { getCurrentPlayState } from "$lib/api/play";
import { getCharacter } from "$lib/api/characters";

// ssr: false is inherited from root +layout.ts — this runs browser-only.
export const load: PageLoad = async ({ params }) => {
  const [character, playState] = await Promise.all([
    getCharacter(params.id),
    getCurrentPlayState(params.id),
  ]);
  return { character, playState };
};
```

Note: `getCharacter` uses `apiFetch`, and `getCurrentPlayState` also uses `apiFetch` (plus a second `apiFetch` call to `/overworld` when there is no active adventure). Neither accepts a SvelteKit `fetch` param — they call `apiFetch` directly, which reads `get(authStore)` at call time. This is correct for a CSR-only app — the auth store is populated before any page load function executes (SvelteKit runs load functions lazily on navigation, after `+layout.svelte`'s `onMount` has fired and initialized the store).

### `frontend/src/routes/characters/[id]/play/+page.svelte` (skeleton)

```svelte
<script lang="ts">
  import { onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { gameSession } from '$lib/stores/gameSession';
  import NarrativeLog from '$lib/components/Game/NarrativeLog.svelte';
  import ChoiceMenu from '$lib/components/Game/ChoiceMenu.svelte';
  import AckPrompt from '$lib/components/Game/AckPrompt.svelte';
  import CombatHUD from '$lib/components/Game/CombatHUD.svelte';
  import TextInputForm from '$lib/components/Game/TextInputForm.svelte';
  import SkillMenu from '$lib/components/Game/SkillMenu.svelte';
  import AdventureCompleteScreen from '$lib/components/Game/AdventureCompleteScreen.svelte';
  import SessionConflictModal from '$lib/components/Game/SessionConflictModal.svelte';
  import OverworldView from '$lib/components/Overworld/OverworldView.svelte';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  // Initialize store from crash-recovery data before first render.
  gameSession.init(data.playState);

  const characterId = data.character.id;

  let showConflictModal = $state(false);

  async function handleChoice(choice: number): Promise<void> { /* ... */ }
  async function handleAck(): Promise<void> { /* ... */ }
  async function handleTextInput(text: string): Promise<void> { /* ... */ }
  async function handleSkillChoice(skillIndex: number): Promise<void> { /* ... */ }
  async function handleAdventureComplete(): Promise<void> {
    await goto(`/characters/${characterId}`);
  }

  onDestroy(() => { gameSession.close(); });
</script>

<svelte:window onkeydown={handleGlobalKey} />

{#if $gameSession.mode === 'overworld'}
  <OverworldView
    characterId={characterId}
    state={$gameSession.overworldState}
    onBeginAdventure={(id) => gameSession.begin(characterId, id)}
  />
{:else}
  <NarrativeLog entries={$gameSession.narrativeLog} />
  <div class="decision-area">
    {#if $gameSession.pendingEvent?.type === 'choice'}
      <ChoiceMenu event={$gameSession.pendingEvent} onSelect={handleChoice} />
    {:else if $gameSession.pendingEvent?.type === 'ack_required'}
      <AckPrompt onAck={handleAck} />
    {:else if $gameSession.pendingEvent?.type === 'combat_state'}
      <CombatHUD event={$gameSession.pendingEvent} onAck={handleAck} />
    {:else if $gameSession.pendingEvent?.type === 'text_input'}
      <TextInputForm event={$gameSession.pendingEvent} onSubmit={handleTextInput} />
    {:else if $gameSession.pendingEvent?.type === 'skill_menu'}
      <SkillMenu event={$gameSession.pendingEvent} onSelect={handleSkillChoice} />
    {:else if $gameSession.mode === 'loading'}
      <LoadingSpinner label="Running adventure..." />
    {:else if $gameSession.mode === 'complete'}
      <AdventureCompleteScreen event={$gameSession.completeEvent} onContinue={handleAdventureComplete} />
    {/if}
  </div>
{/if}

{#if showConflictModal}
  <SessionConflictModal
    onTakeover={handleTakeover}
    onCancel={() => { showConflictModal = false; }}
  />
{/if}
```

### Game-related types (`frontend/src/lib/api/types.ts` additions)

The following interfaces are added to `types.ts` in MU5 (in addition to all MU4 types):

| Interface                    | Fields                                                                                                                                                                                                         |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OverworldStateRead`         | `character_id`, `current_location`, `current_location_name`, `current_region_name`, `available_adventures: AdventureOptionRead[]`, `navigation_options: LocationOptionRead[]`, `region_graph: RegionGraphRead` |
| `AdventureOptionRead`        | `ref`, `display_name`, `description`                                                                                                                                                                           |
| `LocationOptionRead`         | `ref`, `display_name`, `is_current`                                                                                                                                                                            |
| `RegionGraphRead`            | `nodes: RegionGraphNode[]`, `edges: RegionGraphEdge[]`                                                                                                                                                         |
| `RegionGraphNode`            | `id`, `label`, `kind`                                                                                                                                                                                          |
| `RegionGraphEdge`            | `source`, `target`, `label`                                                                                                                                                                                    |
| `PendingStateRead`           | `character_id`, `pending_event: Record<string, unknown> \| null`, `session_output: Record<string, unknown>[]` (raw backend; client transforms to `CurrentPlayState`)                                           |
| `AdvanceDecision`            | `choice?: number` (1-based), `ack?: boolean`, `text_input?: string`, `skill_choice?: number` (1-based) — mirrors backend `AdvanceRequest`                                                                      |
| `NarrativeEventData`         | `text: string`                                                                                                                                                                                                 |
| `ChoiceEventData`            | `prompt: string`, `options: string[]`                                                                                                                                                                          |
| `CombatStateEventData`       | `round: number`, `combatants: CombatantState[]`                                                                                                                                                                |
| `CombatantState`             | `name: string`, `hp: number`, `max_hp: number`, `is_player: boolean`                                                                                                                                           |
| `TextInputEventData`         | `prompt: string`                                                                                                                                                                                               |
| `SkillMenuEventData`         | `skills: SkillMenuEntry[]`                                                                                                                                                                                     |
| `SkillMenuEntry`             | `id: string`, `name: string`, `description: string`, `on_cooldown: boolean`                                                                                                                                    |
| `AdventureCompleteEventData` | `outcome: string`, `narrative: string`                                                                                                                                                                         |

---

## Project Structure

Files added by MU5 within `frontend/src/`:

```
frontend/src/
  lib/
    api/
      play.ts               — fetchSSE generator, getCurrentPlayState, parseSSEBuffer
    stores/
      gameSession.ts        — writable store: mode, narrativeLog, pendingEvent, overworld
    components/
      Game/
        NarrativeLog.svelte
        NarrativeEntry.svelte
        ChoiceMenu.svelte
        AckPrompt.svelte
        CombatHUD.svelte
        TextInputForm.svelte
        SkillMenu.svelte
        AdventureCompleteScreen.svelte
        SessionConflictModal.svelte
      Overworld/
        OverworldView.svelte
        LocationInfo.svelte
        AdventureList.svelte
        NavigationPanel.svelte
        CharacterSidebar.svelte
        InventoryQuickActions.svelte  (read-only in MU5)
  routes/
    app/
      characters/
        [id]/
          play/
            +page.ts         — load function: character + play state (parallelized)
            +page.svelte     — root play page; drives gameSession store

```

The root `+layout.svelte` is modified to add the D7 hard-block navigation guard checking `$gameSession.mode`. The character-scoped layout `routes/characters/[id]/+layout.ts` is added to implement D8 forced redirect when an adventure is active.

`frontend/src/lib/api/types.ts` is extended with the interfaces listed above.

`frontend/src/lib/api/characters.ts` is extended with `navigateLocation(characterId, locationId)`.

---

## Testing Philosophy

| Tier                       | What is tested                                                                                                                                                                                                            | How                                                                      |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| TypeScript type-check      | All `.ts` and `.svelte` files compile; interface contracts between `types.ts`, `gameSession.ts`, and page components are upheld                                                                                           | `make frontend-typecheck` (svelte-check)                                 |
| Python API tests           | All `POST /play/begin`, `/advance`, `/current` server behavior is tested in MU3; no duplication in MU5                                                                                                                    | `make pytest`                                                            |
| Manual browser integration | Full game loop played through Testlandia: begin adventure → narrative → choices → combat → complete → return to overworld; crash recovery tested by refreshing mid-adventure; session conflict tested by opening two tabs | Manual developer run after `make frontend-build` and `docker compose up` |

**No component unit tests are written in MU5.** The game loop components are tightly coupled to `gameSession` store state transitions. Mocking the store for isolated component tests requires significant scaffolding that is premature while the design is stabilizing. The type-checker catches structural errors; manual play validates behavior.

A future change should introduce **Playwright E2E tests** covering:

- Full adventure cycle from overworld → begin → decisions → complete → overworld
- Crash recovery (reload mid-adventure restores narrative log + pending decision)
- Session conflict modal (two-tab test or direct 409 injection)
- Navigation guard hard-blocks leaving mid-adventure (no bypass)
- Triggered adventure forces redirect: player opens character sheet while engine has active adventure
- Triggered adventure detected from overworld: `OverworldView` poll fires, adventure screen takes over without navigation

These tests require a live stack (DB + FastAPI + built frontend) and belong in a dedicated E2E test suite, not the existing `pytest` battery.

---

## Documentation Plan

| Document                              | Audience        | Topics                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docs/dev/frontend.md` (update)       | Developers      | `gameSession` store lifecycle: `begin`, `advance`, `close`; `fetchSSE` async generator and `parseSSEBuffer` in `api/play.ts`; why all adventure SSE uses `fetch` + `ReadableStream` instead of `EventSource` (POST-only requirement); why `writable` not runes; `getCurrentPlayState` dual-fetch design (play/current + overworld); crash recovery via `+page.ts` load function; D7 navigation hard-block and D8 forced redirect (including triggered-adventure detection from overworld polling); decision component callback prop pattern; keyboard shortcut registration with `<svelte:window onkeydown>` |
| `docs/dev/game-engine.md` (update)    | Developers      | Note that `stream-end` SSE event must be emitted by the server after each decision event; document the expected SSE event types and their JSON shapes (already defined in MU3, but now has a TypeScript consumer to stay in sync with)                                                                                                                                                                                                                                                                                                                                                                       |
| `docs/authors/adventures.md` (update) | Content Authors | No content-author-facing changes; add a brief note that the browser interface now renders all adventure decision types including combat, skill menus, and text inputs                                                                                                                                                                                                                                                                                                                                                                                                                                        |

---

## Risks / Trade-offs

| Risk                                                                                                                                                                             | Mitigation                                                                                                                                                                                                                                                                        |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fetch` + `ReadableStream` SSE parsing is more complex than `EventSource`                                                                                                        | `fetchSSE` generator and `parseSSEBuffer` are isolated in `api/play.ts`; all other code reads from the `gameSession` store; complexity is contained and fully typed                                                                                                               |
| `EventSource` reconnect logic fires on network glitches during a GET SSE session                                                                                                 | SSE streams (begin/advance) use `fetch` + `ReadableStream`, not `EventSource`, so there is no auto-reconnect. A glitch surfaces as a `done=true` read, which the store treats as stream end. Crash recovery via `GET /play/current` handles any resulting inconsistency           |
| Scroll anchor fights with typewriter fade — new content pushes earlier content up before it fades out                                                                            | Fade-in animates only `opacity` (no height or margin animation); scroll container height is stable; no layout shift                                                                                                                                                               |
| `gameSession.init()` is called synchronously at module load from `+page.svelte` — if the store was already in `adventure` mode (user navigates away and back) the init resets it | `onDestroy` in the play page calls `gameSession.close()`, ensuring the store is reset to `idle` before the user leaves; a fresh `init()` on next mount always has a clean state                                                                                                   |
| Inventory quick-actions on overworld require new API endpoints not defined in MU2/MU3                                                                                            | MU5 renders inventory as read-only on the overworld; `InventoryQuickActions` is a stubbed placeholder; equip/use endpoints are defined in a future change                                                                                                                         |
| 409 Conflict during `begin` bubbles as an `ApiError` into `fetchSSE` before the generator starts yielding                                                                        | The generator catches `response.status === 409` before entering the read loop and throws `new ApiError("Session conflict", 409, "session_conflict")`; `gameSession.begin` catches this, sets `showConflictModal = true` via a writable sub-store, and does not enter loading mode |
| `get(authStore)` at stream-open time — token may expire during a long stream                                                                                                     | Adventures are short by design (seconds to minutes); token expiry (typically 15–60 min) is not expected mid-stream. If it occurs, the server returns a 401 which appears as a non-OK response before the stream begins, triggering auth refresh via `client.ts` before retry      |
