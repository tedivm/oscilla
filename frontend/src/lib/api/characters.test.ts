import { describe, expect, it, vi } from "vitest";

// ── Mocks ─────────────────────────────────────────────────────────────────────

vi.mock("$lib/api/client.js", () => ({
  apiFetch: vi.fn(),
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

vi.mock("$app/paths", () => ({
  base: "",
}));

// ── isActiveAdventureConflict ─────────────────────────────────────────────────

describe("isActiveAdventureConflict", () => {
  it("returns false for non-Error values", async () => {
    const { isActiveAdventureConflict } = await import("./characters.js");
    expect(isActiveAdventureConflict(null)).toBe(false);
    expect(isActiveAdventureConflict("string error")).toBe(false);
    expect(isActiveAdventureConflict(42)).toBe(false);
  });

  it("returns false for a non-409 ApiError", async () => {
    const { ApiError } = await import("./client.js");
    const { isActiveAdventureConflict } = await import("./characters.js");
    const err = new ApiError("Not Found", 404, { detail: "not found" });
    expect(isActiveAdventureConflict(err)).toBe(false);
  });

  it("returns false for a 409 ApiError with unrelated detail", async () => {
    const { ApiError } = await import("./client.js");
    const { isActiveAdventureConflict } = await import("./characters.js");
    const err = new ApiError("Conflict", 409, {
      detail: { code: "other_conflict" },
    });
    expect(isActiveAdventureConflict(err)).toBe(false);
  });

  it("returns true for a 409 ApiError with active_adventure detail", async () => {
    const { ApiError } = await import("./client.js");
    const { isActiveAdventureConflict } = await import("./characters.js");
    const err = new ApiError("Conflict", 409, {
      detail: { code: "active_adventure", character_id: "abc-123" },
    });
    expect(isActiveAdventureConflict(err)).toBe(true);
  });
});
