import { beforeEach, describe, expect, it, vi } from "vitest";

// ── Mocks ─────────────────────────────────────────────────────────────────────

const mockApiFetch = vi.fn();
const mockGetOverworld = vi.fn();
let authState = { accessToken: null as string | null };

vi.mock("$lib/api/client.js", () => ({
  apiFetch: mockApiFetch,
  ApiError: class ApiError extends Error {
    status: number;
    body: unknown;
    constructor(message: string, status: number, body: unknown) {
      super(message);
      this.status = status;
      this.body = body;
    }
  },
}));

vi.mock("$lib/api/characters.js", () => ({
  getOverworld: mockGetOverworld,
}));

vi.mock("$lib/stores/auth.js", () => ({
  authStore: {
    subscribe: (run: (v: typeof authState) => void) => {
      run(authState);
      return () => {};
    },
  },
}));

vi.mock("$lib/stores/gameSession.js", () => ({
  // Provide minimal type stubs — play.test.ts only imports the types, not values.
}));

vi.mock("$app/paths", () => ({
  base: "",
}));

// ── Source-contract: module exports ───────────────────────────────────────────

describe("play module exports", () => {
  it("exports getCurrentPlayState, fetchSSE, parseSSEBuffer", async () => {
    const mod = await import("./play.js");
    expect(typeof mod.getCurrentPlayState).toBe("function");
    expect(typeof mod.fetchSSE).toBe("function");
    expect(typeof mod.parseSSEBuffer).toBe("function");
  });
});

// ── parseSSEBuffer ────────────────────────────────────────────────────────────

describe("parseSSEBuffer", () => {
  it("returns empty events and full input as remaining when buffer has no complete block", async () => {
    const { parseSSEBuffer } = await import("./play.js");
    const result = parseSSEBuffer('event: narrative\ndata: {"text":"Hello"}');
    expect(result.events).toHaveLength(0);
    expect(result.remaining).toBe('event: narrative\ndata: {"text":"Hello"}');
  });

  it("parses one complete block", async () => {
    const { parseSSEBuffer } = await import("./play.js");
    const raw = 'event: narrative\ndata: {"text":"Hello"}\n\n';
    const result = parseSSEBuffer(raw);
    expect(result.events).toHaveLength(1);
    expect(result.events[0].type).toBe("narrative");
    expect((result.events[0].data as Record<string, unknown>)["text"]).toBe(
      "Hello",
    );
    expect(result.remaining).toBe("");
  });

  it("parses two complete blocks and returns empty remaining", async () => {
    const { parseSSEBuffer } = await import("./play.js");
    const raw = [
      'event: narrative\ndata: {"text":"One"}\n\n',
      'event: choice\ndata: {"prompt":"Choose"}\n\n',
    ].join("");
    const result = parseSSEBuffer(raw);
    expect(result.events).toHaveLength(2);
    expect(result.events[0].type).toBe("narrative");
    expect(result.events[1].type).toBe("choice");
    expect(result.remaining).toBe("");
  });

  it("returns incomplete tail as remaining when two complete + one partial block", async () => {
    const { parseSSEBuffer } = await import("./play.js");
    const raw =
      'event: narrative\ndata: {"text":"A"}\n\nevent: choice\ndata: {"prompt":"B"}';
    const result = parseSSEBuffer(raw);
    expect(result.events).toHaveLength(1);
    expect(result.remaining).toBe('event: choice\ndata: {"prompt":"B"}');
  });

  it("skips blocks with malformed JSON without throwing", async () => {
    const { parseSSEBuffer } = await import("./play.js");
    const raw =
      'event: narrative\ndata: NOT_JSON\n\nevent: choice\ndata: {"ok":true}\n\n';
    const result = parseSSEBuffer(raw);
    expect(result.events).toHaveLength(1);
    expect(result.events[0].type).toBe("choice");
  });

  it("skips blocks with no data line", async () => {
    const { parseSSEBuffer } = await import("./play.js");
    const raw = "event: ping\n\n";
    const result = parseSSEBuffer(raw);
    expect(result.events).toHaveLength(0);
  });
});

// ── getCurrentPlayState ───────────────────────────────────────────────────────

describe("getCurrentPlayState", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState = { accessToken: null };
  });

  it("reconstructs narrative log from session_output", async () => {
    const { getCurrentPlayState } = await import("./play.js");

    mockApiFetch.mockResolvedValueOnce({
      pending_event: null,
      session_output: [
        { event: "narrative", data: { text: "You entered." } },
        { event: "combat_state", data: { round: 1 } },
        { event: "narrative", data: { text: "You swung." } },
      ],
    });
    mockGetOverworld.mockResolvedValueOnce({
      current_location: { ref: "loc:hub", name: "Hub" },
      adjacent_locations: [],
      available_adventures: [],
    });

    const result = await getCurrentPlayState("char-1");

    expect(result.narrativeLog).toHaveLength(2);
    expect(result.narrativeLog[0].text).toBe("You entered.");
    expect(result.narrativeLog[1].text).toBe("You swung.");
  });

  it("fetches overworld when no pending_event", async () => {
    const { getCurrentPlayState } = await import("./play.js");

    const owState = {
      current_location: { ref: "loc:hub", name: "Hub" },
      adjacent_locations: [],
      available_adventures: [],
    };
    mockApiFetch.mockResolvedValueOnce({
      pending_event: null,
      session_output: [],
    });
    mockGetOverworld.mockResolvedValueOnce(owState);

    const result = await getCurrentPlayState("char-1");

    expect(mockGetOverworld).toHaveBeenCalledWith("char-1");
    expect(result.overworldState).toStrictEqual(owState);
  });

  it("does not fetch overworld when pending_event is present", async () => {
    const { getCurrentPlayState } = await import("./play.js");

    mockApiFetch.mockResolvedValueOnce({
      pending_event: { type: "choice", data: {} },
      session_output: [],
    });

    const result = await getCurrentPlayState("char-1");

    expect(mockGetOverworld).not.toHaveBeenCalled();
    expect(result.overworldState).toBeNull();
    expect(result.pendingEvent).not.toBeNull();
  });
});

// ── fetchSSE ──────────────────────────────────────────────────────────────────

describe("fetchSSE", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState = { accessToken: null };
    vi.stubGlobal("fetch", vi.fn());
  });

  it("uses raw fetch (not apiFetch) for streaming", async () => {
    // The fact that fetchSSE calls global fetch() means apiFetch should not be called.
    const { fetchSSE } = await import("./play.js");

    const sseBody = 'event: narrative\ndata: {"text":"Hi"}\n\n';
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(sseBody));
        controller.close();
      },
    });

    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(stream, { status: 200 }),
    );

    const gen = fetchSSE("/characters/char-1/play/begin", {
      adventure_ref: "adv:test",
    });
    const results = [];
    for await (const event of gen) results.push(event);

    expect(mockApiFetch).not.toHaveBeenCalled();
    expect(fetch).toHaveBeenCalledWith(
      "/characters/char-1/play/begin",
      expect.objectContaining({ method: "POST" }),
    );
    expect(results).toHaveLength(1);
    expect(results[0].type).toBe("narrative");
  });

  it("throws ApiError with status 409 on conflict response", async () => {
    const { fetchSSE } = await import("./play.js");
    const { ApiError } = await import("$lib/api/client.js");

    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(JSON.stringify({ acquired_at: "2025-01-01T00:00:00Z" }), {
        status: 409,
      }),
    );

    const gen = fetchSSE("/characters/char-1/play/begin", {
      adventure_ref: "adv:test",
    });

    await expect(async () => {
      for await (const _ of gen) {
        /* consume */
      }
    }).rejects.toBeInstanceOf(ApiError);
  });

  it("attaches Authorization header when access token is set", async () => {
    authState = { accessToken: "tok-1" };
    const { fetchSSE } = await import("./play.js");

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.close();
      },
    });
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(stream, { status: 200 }),
    );

    const gen = fetchSSE("/characters/char-1/play/advance", { ack: true });
    for await (const _ of gen) {
      /* drain */
    }

    expect(fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer tok-1" }),
      }),
    );
  });
});
