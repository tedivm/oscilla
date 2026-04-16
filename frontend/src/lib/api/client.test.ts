import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AuthState } from "$lib/stores/auth.js";

const mockRefresh = vi.fn();
const mockLogout = vi.fn();
let authState: AuthState = {
  user: null,
  accessToken: null,
  loading: false,
  error: null,
  initialized: true,
};

vi.mock("$app/paths", () => ({
  base: "/app",
}));

vi.mock("$lib/stores/auth.js", () => ({
  authStore: {
    subscribe: (run: (value: AuthState) => void) => {
      run(authState);
      return () => {};
    },
    refresh: mockRefresh,
    logout: mockLogout,
  },
}));

describe("apiFetch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState = {
      user: null,
      accessToken: null,
      loading: false,
      error: null,
      initialized: true,
    };
    vi.stubGlobal("fetch", vi.fn());
  });

  it("attaches Authorization header when token exists", async () => {
    authState.accessToken = "access-1";
    const { apiFetch } = await import("./client.js");

    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    await apiFetch<{ ok: boolean }>("/games");

    expect(fetch).toHaveBeenCalledWith(
      "/games",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer access-1" }),
      }),
    );
  });

  it("retries once on 401 after refresh", async () => {
    authState.accessToken = "old-token";
    const { apiFetch } = await import("./client.js");

    mockRefresh.mockImplementationOnce(async () => {
      authState.accessToken = "new-token";
    });

    (fetch as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "expired" }), { status: 401 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
      );

    const result = await apiFetch<{ ok: boolean }>("/games");

    expect(mockRefresh).toHaveBeenCalledTimes(1);
    expect(result.ok).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("logs out and throws after two 401 responses", async () => {
    authState.accessToken = "old-token";
    const { apiFetch, ApiError } = await import("./client.js");

    mockRefresh.mockResolvedValueOnce(undefined);

    (fetch as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "expired" }), { status: 401 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "expired" }), { status: 401 }),
      );

    await expect(apiFetch("/games")).rejects.toBeInstanceOf(ApiError);
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  it("throws ApiError with status for 422 response", async () => {
    const { apiFetch, ApiError } = await import("./client.js");

    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Invalid data" }), { status: 422 }),
    );

    try {
      await apiFetch("/characters");
      throw new Error("Expected apiFetch to throw");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as { status: number }).status).toBe(422);
    }
  });

  it("returns parsed JSON for 200 response", async () => {
    const { apiFetch } = await import("./client.js");

    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(JSON.stringify({ hello: "world" }), { status: 200 }),
    );

    const response = await apiFetch<{ hello: string }>("/games");
    expect(response).toEqual({ hello: "world" });
  });
});
