import { get } from "svelte/store";
import { authStore } from "$lib/stores/auth.js";
import { apiFetch, ApiError } from "$lib/api/client.js";
import { getOverworld } from "$lib/api/characters.js";
import type { OverworldStateRead, PendingStateRead } from "$lib/api/types.js";
import type { NarrativeEntry, SSEEvent } from "$lib/stores/gameSession.js";

// ── Types ─────────────────────────────────────────────────────────────────────

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

export interface CurrentPlayState {
  narrativeLog: NarrativeEntry[];
  pendingEvent: SSEEvent | null;
  overworldState: OverworldStateRead | null;
}

// ── getCurrentPlayState ────────────────────────────────────────────────────────

/**
 * Called from +page.ts load function; returns current session state for crash recovery.
 *
 * Fetches GET /play/current (returns PendingStateRead) and transforms the persisted
 * session_output into a client-side NarrativeEntry[]. When no adventure is in progress,
 * also fetches GET /overworld to populate overworldState for initial render.
 */
export async function getCurrentPlayState(
  characterId: string,
): Promise<CurrentPlayState> {
  const pending = await apiFetch<PendingStateRead>(
    `/api/characters/${encodeURIComponent(characterId)}/play/current`,
  );

  // Reconstruct the narrative log from the persisted session output.
  const narrativeLog: NarrativeEntry[] = (pending.session_output ?? [])
    .filter(
      (e: Record<string, unknown>) =>
        (e["event"] as string | undefined) === "narrative" ||
        (e["type"] as string | undefined) === "narrative",
    )
    .map((e: Record<string, unknown>) => ({
      id: crypto.randomUUID(),
      text: ((e["data"] as Record<string, unknown> | undefined)?.["text"] ??
        "") as string,
    }));

  const pendingEvent = pending.pending_event
    ? (pending.pending_event as unknown as SSEEvent)
    : null;

  // Fetch overworld state separately when no active adventure is in progress.
  const overworldState = pendingEvent ? null : await getOverworld(characterId);

  return { narrativeLog, pendingEvent, overworldState };
}

// ── fetchSSE ──────────────────────────────────────────────────────────────────

/**
 * Opens a POST SSE stream and yields each parsed event.
 *
 * Uses fetch + ReadableStream rather than EventSource because EventSource only
 * supports GET requests. Auth token is read once before the request. Mid-stream
 * token expiry is handled by the server closing the stream with a type:'error' event.
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
    const rawBody = await response.text();
    throw new ApiError("Session conflict", 409, rawBody);
  }
  if (!response.ok) {
    const rawBody = await response.text();
    throw new ApiError(`HTTP ${response.status}`, response.status, rawBody);
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

// ── parseSSEBuffer ────────────────────────────────────────────────────────────

/**
 * Parses a raw SSE buffer string into typed events.
 *
 * Splits on double-newline block boundaries. Incomplete trailing blocks (no
 * trailing \n\n) are returned as `remaining` for the next iteration.
 */
export function parseSSEBuffer(buffer: string): {
  events: SSEEvent[];
  remaining: string;
} {
  const events: SSEEvent[] = [];
  const blocks = buffer.split("\n\n");
  // Last element is either empty (clean split) or an incomplete block.
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
          data: JSON.parse(dataLine) as unknown,
        });
      } catch {
        // Malformed JSON — skip the block rather than crashing the stream.
      }
    }
  }

  return { events, remaining };
}
