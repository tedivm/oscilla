import { writable, get } from "svelte/store";
import type { OverworldStateRead } from "$lib/api/types.js";
import { fetchSSE, beginAdventureGo } from "$lib/api/play.js";
import type { CurrentPlayState } from "$lib/api/play.js";

// ── Types ─────────────────────────────────────────────────────────────────────

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
  /** Stable unique key used as the {#each} key to prevent re-animation. */
  id: string;
  text: string;
}

export interface SSEEvent {
  type: SSEEventType;
  /** Narrowed per-type inside each component via $props(). */
  data: unknown;
}

export interface GameSessionState {
  mode: "idle" | "loading" | "adventure" | "overworld" | "complete";
  narrativeLog: NarrativeEntry[];
  pendingEvent: SSEEvent | null;
  completeEvent: SSEEvent | null;
  overworldState: OverworldStateRead | null;
  error: string | null;
}

// ── applyEvent (pure) ─────────────────────────────────────────────────────────

/**
 * Pure reducer: takes the current state and an SSE event and returns the next state.
 * Exported so it can be tested independently of the store.
 */
export function applyEvent(
  s: GameSessionState,
  event: SSEEvent,
): GameSessionState {
  switch (event.type) {
    case "narrative":
      return {
        ...s,
        narrativeLog: [
          ...s.narrativeLog,
          {
            id: crypto.randomUUID(),
            text: ((event.data as Record<string, unknown>)["text"] ??
              "") as string,
          },
        ],
      };
    case "adventure_complete":
      return { ...s, mode: "complete", completeEvent: event };
    case "error":
      return {
        ...s,
        mode: "overworld",
        error: ((event.data as Record<string, unknown>)["message"] ??
          "Unknown error") as string,
      };
    default:
      // All decision event types: combat_state, choice, ack_required, text_input, skill_menu
      return { ...s, pendingEvent: event, mode: "adventure" };
  }
}

// ── createGameSession ──────────────────────────────────────────────────────────

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

  /**
   * Reference to the active async generator so that a superseded stream
   * (e.g., when the player submits a new decision before the previous stream
   * completes) can be detected and abandoned inside runStream.
   */
  let activeGenerator: AsyncGenerator<SSEEvent> | null = null;

  async function runStream(gen: AsyncGenerator<SSEEvent>): Promise<void> {
    update((s) => ({ ...s, mode: "loading", pendingEvent: null, error: null }));
    try {
      for await (const event of gen) {
        // Abort if a newer stream has been started since this one began.
        if (gen !== activeGenerator) return;
        update((s) => applyEvent(s, event));
      }
      // Stream exhausted: if we're still in loading mode (no adventure_complete event
      // was received), fall back to overworld so the player isn't stuck.
      update((s) => (s.mode === "loading" ? { ...s, mode: "overworld" } : s));
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
    init(playState: CurrentPlayState): void {
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

    /** Transition to overworld with the given state (used by OverworldView after navigation). */
    setOverworld(overworldState: OverworldStateRead): void {
      update((s) => ({ ...s, mode: "overworld", overworldState }));
    },

    async go(characterId: string, locationRef: string): Promise<void> {
      const gen = beginAdventureGo(characterId, locationRef);
      activeGenerator = gen;
      await runStream(gen);
    },

    async advance(
      characterId: string,
      // Spread the decision fields directly to match the backend AdvanceRequest model.
      decision: import("$lib/api/play.js").AdvanceDecision,
    ): Promise<void> {
      const gen = fetchSSE(
        `/api/characters/${encodeURIComponent(characterId)}/play/advance`,
        decision,
      );
      activeGenerator = gen;
      await runStream(gen);
    },

    /**
     * Close any active stream.
     * Must be called before programmatic navigation away from the play page (D7).
     */
    close(): void {
      activeGenerator = null;
      update((s) => ({ ...s, mode: "idle" }));
    },
  };
}

export const gameSession = createGameSession();
