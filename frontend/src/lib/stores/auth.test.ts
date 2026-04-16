import { beforeEach, describe, expect, it, vi } from "vitest";
import { get } from "svelte/store";

const mockApiFetch = vi.fn();

vi.mock("$lib/api/client.js", () => ({
  apiFetch: mockApiFetch,
}));

describe("authStore", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    sessionStorage.clear();
    const { authStore } = await import("./auth.js");
    authStore.set({
      user: null,
      accessToken: null,
      loading: false,
      error: null,
      initialized: true,
    });
  });

  it("login stores user and access token", async () => {
    const { authStore } = await import("./auth.js");

    mockApiFetch
      .mockResolvedValueOnce({
        access_token: "access-1",
        refresh_token: "refresh-1",
        token_type: "bearer",
      })
      .mockResolvedValueOnce({
        id: "user-1",
        email: "user@example.com",
        display_name: null,
        is_email_verified: true,
        is_active: true,
        created_at: "2025-01-01T00:00:00Z",
      });

    await authStore.login("user@example.com", "password123");

    expect(mockApiFetch).toHaveBeenNthCalledWith(
      1,
      "/api/auth/login",
      expect.objectContaining({ method: "POST" }),
    );
    expect(mockApiFetch).toHaveBeenNthCalledWith(2, "/api/auth/me");

    const state = get(authStore);
    expect(state.user?.id).toBe("user-1");
    expect(state.accessToken).toBe("access-1");
    expect(sessionStorage.getItem("oscilla:refresh_token")).toBe("refresh-1");
  });

  it("logout clears user and access token", async () => {
    const { authStore } = await import("./auth.js");

    authStore.set({
      user: {
        id: "user-1",
        email: "user@example.com",
        display_name: null,
        is_email_verified: true,
        is_active: true,
        created_at: "2025-01-01T00:00:00Z",
      },
      accessToken: "access-1",
      loading: false,
      error: null,
      initialized: true,
    });
    sessionStorage.setItem("oscilla:refresh_token", "refresh-1");

    mockApiFetch.mockResolvedValueOnce(undefined);
    await authStore.logout();

    const state = get(authStore);
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(sessionStorage.getItem("oscilla:refresh_token")).toBeNull();
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/auth/logout",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("login sets error and leaves user null on 401", async () => {
    const { authStore } = await import("./auth.js");

    mockApiFetch.mockRejectedValueOnce(new Error("Unauthorized"));

    await authStore.login("user@example.com", "wrong-password");

    const state = get(authStore);
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(state.error).toBe("Unauthorized");
  });

  it("refresh updates access token on success", async () => {
    const { authStore } = await import("./auth.js");

    sessionStorage.setItem("oscilla:refresh_token", "refresh-1");
    mockApiFetch.mockResolvedValueOnce({
      access_token: "access-2",
      refresh_token: "refresh-2",
      token_type: "bearer",
    });

    await authStore.refresh();

    const state = get(authStore);
    expect(state.accessToken).toBe("access-2");
    expect(sessionStorage.getItem("oscilla:refresh_token")).toBe("refresh-2");
  });

  it("refresh logs out on 401", async () => {
    const { authStore } = await import("./auth.js");

    authStore.set({
      user: {
        id: "user-1",
        email: "user@example.com",
        display_name: null,
        is_email_verified: true,
        is_active: true,
        created_at: "2025-01-01T00:00:00Z",
      },
      accessToken: "access-1",
      loading: false,
      error: null,
      initialized: true,
    });
    sessionStorage.setItem("oscilla:refresh_token", "refresh-1");

    mockApiFetch
      .mockRejectedValueOnce(
        Object.assign(new Error("Unauthorized"), { status: 401 }),
      )
      .mockResolvedValueOnce(undefined);

    await expect(authStore.refresh()).rejects.toThrow();

    const state = get(authStore);
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(sessionStorage.getItem("oscilla:refresh_token")).toBeNull();
  });
});
