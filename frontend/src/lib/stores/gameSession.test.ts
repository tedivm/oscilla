import { beforeEach, describe, expect, it, vi } from "vitest";
import { get } from "svelte/store";

// ── Mocks ─────────────────────────────────────────────────────────────────────

const mockFetchSSE = vi.fn();
const mockBeginAdventureGo = vi.fn();

vi.mock("$lib/api/play.js", () => ({
  fetchSSE: mockFetchSSE,
  beginAdventureGo: mockBeginAdventureGo,
}));

vi.mock("$app/paths", () => ({
  base: "",
}));

// ── Source-contract: module exports ───────────────────────────────────────────

describe("gameSession module exports", () => {
  it("exports createGameSession factory via gameSession singleton", async () => {
    const mod = await import("./gameSession.js");
    expect(typeof mod.gameSession).toBe("object");
    expect(typeof mod.gameSession.subscribe).toBe("function");
    expect(typeof mod.gameSession.init).toBe("function");
    expect(typeof mod.gameSession.go).toBe("function");
    expect(typeof mod.gameSession.advance).toBe("function");
    expect(typeof mod.gameSession.close).toBe("function");
  });

  it("exports applyEvent as a named function", async () => {
    const mod = await import("./gameSession.js");
    expect(typeof mod.applyEvent).toBe("function");
  });
});

// ── applyEvent pure reducer ───────────────────────────────────────────────────

describe("applyEvent", () => {
  const base = () => ({
    mode: "idle" as const,
    narrativeLog: [],
    pendingEvent: null,
    completeEvent: null,
    overworldState: null,
    error: null,
  });

  it("narrative event appends an entry with non-empty id and correct text", async () => {
    const { applyEvent } = await import("./gameSession.js");
    const result = applyEvent(base(), {
      type: "narrative",
      data: { text: "You enter the dungeon." },
    });
    expect(result.narrativeLog).toHaveLength(1);
    expect(result.narrativeLog[0].text).toBe("You enter the dungeon.");
    expect(typeof result.narrativeLog[0].id).toBe("string");
    expect(result.narrativeLog[0].id.length).toBeGreaterThan(0);
  });

  it("narrative event preserves existing entries", async () => {
    const { applyEvent } = await import("./gameSession.js");
    const s1 = applyEvent(base(), {
      type: "narrative",
      data: { text: "First." },
    });
    const s2 = applyEvent(s1, { type: "narrative", data: { text: "Second." } });
    expect(s2.narrativeLog).toHaveLength(2);
    expect(s2.narrativeLog[1].text).toBe("Second.");
  });

  it("choice event sets mode:'adventure' and pendingEvent", async () => {
    const { applyEvent } = await import("./gameSession.js");
    const event = {
      type: "choice" as const,
      data: { prompt: "Do what?", options: [] },
    };
    const result = applyEvent(base(), event);
    expect(result.mode).toBe("adventure");
    expect(result.pendingEvent).toStrictEqual(event);
  });

  it("ack_required event sets mode:'adventure' and pendingEvent", async () => {
    const { applyEvent } = await import("./gameSession.js");
    const event = { type: "ack_required" as const, data: {} };
    const result = applyEvent(base(), event);
    expect(result.mode).toBe("adventure");
    expect(result.pendingEvent).toStrictEqual(event);
  });

  it("combat_state event sets mode:'adventure' and pendingEvent", async () => {
    const { applyEvent } = await import("./gameSession.js");
    const event = {
      type: "combat_state" as const,
      data: { round: 1, combatants: [] },
    };
    const result = applyEvent(base(), event);
    expect(result.mode).toBe("adventure");
    expect(result.pendingEvent).toStrictEqual(event);
  });

  it("adventure_complete sets mode:'complete' and completeEvent", async () => {
    const { applyEvent } = await import("./gameSession.js");
    const event = {
      type: "adventure_complete" as const,
      data: { outcome: "win" },
    };
    const result = applyEvent(base(), event);
    expect(result.mode).toBe("complete");
    expect(result.completeEvent).toStrictEqual(event);
  });

  it("error event sets mode:'overworld' and error message", async () => {
    const { applyEvent } = await import("./gameSession.js");
    const event = {
      type: "error" as const,
      data: { message: "Something went wrong." },
    };
    const result = applyEvent(base(), event);
    expect(result.mode).toBe("overworld");
    expect(result.error).toBe("Something went wrong.");
  });

  it("applyEvent does not mutate the input state", async () => {
    const { applyEvent } = await import("./gameSession.js");
    const s = base();
    applyEvent(s, { type: "narrative", data: { text: "Test." } });
    expect(s.narrativeLog).toHaveLength(0);
  });
});

// ── gameSession store ─────────────────────────────────────────────────────────

describe("gameSession store", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    // Reset the store to a known state before each test via init() with empty state.
    const { gameSession } = await import("./gameSession.js");
    gameSession.init({
      narrativeLog: [],
      pendingEvent: null,
      overworldState: null,
    });
    gameSession.close();
  });

  it("initial state has mode:'idle' and empty narrativeLog", async () => {
    const { gameSession } = await import("./gameSession.js");
    const s = get(gameSession);
    // After close() the mode is 'idle', which matches initial state.
    expect(s.mode).toBe("idle");
    expect(s.narrativeLog).toHaveLength(0);
    expect(s.pendingEvent).toBeNull();
  });

  it("init with no pendingEvent sets mode:'overworld'", async () => {
    const { gameSession } = await import("./gameSession.js");
    gameSession.init({
      narrativeLog: [],
      pendingEvent: null,
      overworldState: null,
    });
    const s = get(gameSession);
    expect(s.mode).toBe("overworld");
  });

  it("init with pendingEvent sets mode:'adventure'", async () => {
    const { gameSession } = await import("./gameSession.js");
    const pendingEvent = { type: "choice" as const, data: {} };
    gameSession.init({
      narrativeLog: [{ id: "1", text: "You arrived." }],
      pendingEvent: pendingEvent as never,
      overworldState: null,
    });
    const s = get(gameSession);
    expect(s.mode).toBe("adventure");
    expect(s.narrativeLog).toHaveLength(1);
    expect(s.pendingEvent).toStrictEqual(pendingEvent);
  });

  it("setOverworld sets mode:'overworld' and overworldState", async () => {
    const { gameSession } = await import("./gameSession.js");
    const owState = {
      character_id: "char-1",
      accessible_locations: [],
      region_graph: { nodes: [], edges: [] },
    } as never;
    gameSession.setOverworld(owState);
    const s = get(gameSession);
    expect(s.mode).toBe("overworld");
    expect(s.overworldState).toStrictEqual(owState);
  });

  it("close sets mode:'idle' and clears activeGenerator reference", async () => {
    const { gameSession } = await import("./gameSession.js");
    gameSession.setOverworld({
      character_id: "char-1",
      accessible_locations: [],
      region_graph: { nodes: [], edges: [] },
    } as never);
    expect(get(gameSession).mode).toBe("overworld");
    gameSession.close();
    expect(get(gameSession).mode).toBe("idle");
  });

  it("go calls beginAdventureGo with correct characterId and locationRef", async () => {
    const { gameSession } = await import("./gameSession.js");

    // Make beginAdventureGo return an empty async generator so runStream completes immediately.
    async function* emptyGen() {}
    mockBeginAdventureGo.mockReturnValueOnce(emptyGen());

    await gameSession.go("char-1", "loc:hub");

    expect(mockBeginAdventureGo).toHaveBeenCalledWith("char-1", "loc:hub");
  });

  it("go applies events yielded by the generator", async () => {
    const { gameSession } = await import("./gameSession.js");

    async function* gen() {
      yield { type: "narrative" as const, data: { text: "You start." } };
      yield {
        type: "choice" as const,
        data: { prompt: "Choose?", options: [] },
      };
    }
    mockBeginAdventureGo.mockReturnValueOnce(gen());

    await gameSession.go("char-1", "loc:hub");

    const s = get(gameSession);
    expect(s.narrativeLog).toHaveLength(1);
    expect(s.narrativeLog[0].text).toBe("You start.");
    expect(s.mode).toBe("adventure");
    expect(s.pendingEvent?.type).toBe("choice");
  });

  it("stream error sets mode:'overworld' and error message", async () => {
    const { gameSession } = await import("./gameSession.js");

    async function* failingGen() {
      yield { type: "narrative" as const, data: { text: "Start." } };
      throw new Error("Network failed");
    }
    mockBeginAdventureGo.mockReturnValueOnce(failingGen());

    await gameSession.go("char-1", "loc:fail");

    const s = get(gameSession);
    expect(s.mode).toBe("overworld");
    expect(s.error).toBe("Network failed");
  });
});
