import { writable, get } from "svelte/store";
import type { Writable } from "svelte/store";
// Circular import: client.ts imports authStore, authStore imports apiFetch.
// This is safe because both values are used only inside function bodies, not
// at module initialization time. JavaScript resolves this correctly.
import { apiFetch } from "$lib/api/client.js";
import type { TokenPairRead, UserRead } from "$lib/api/types.js";

const REFRESH_TOKEN_KEY = "oscilla:refresh_token";

export interface AuthState {
  user: UserRead | null;
  accessToken: string | null;
  loading: boolean;
  error: string | null;
  // True once init() has completed (success or failure). The route guard
  // must not redirect until this is set, otherwise a page refresh causes an
  // immediate redirect to /login before the stored refresh token is checked.
  initialized: boolean;
}

const initialState: AuthState = {
  user: null,
  accessToken: null,
  loading: false,
  error: null,
  initialized: false,
};

function createAuthStore(): Writable<AuthState> & {
  login(email: string, password: string): Promise<void>;
  register(email: string, password: string): Promise<void>;
  logout(): Promise<void>;
  refresh(): Promise<void>;
  init(): Promise<void>;
} {
  const { subscribe, set, update } = writable<AuthState>(initialState);

  function getStoredRefreshToken(): string | null {
    if (typeof sessionStorage === "undefined") return null;
    return sessionStorage.getItem(REFRESH_TOKEN_KEY);
  }

  function storeRefreshToken(token: string): void {
    if (typeof sessionStorage !== "undefined") {
      sessionStorage.setItem(REFRESH_TOKEN_KEY, token);
    }
  }

  function clearRefreshToken(): void {
    if (typeof sessionStorage !== "undefined") {
      sessionStorage.removeItem(REFRESH_TOKEN_KEY);
    }
  }

  async function login(email: string, password: string): Promise<void> {
    update((s) => ({ ...s, loading: true, error: null }));
    try {
      const pair = await apiFetch<TokenPairRead>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      storeRefreshToken(pair.refresh_token);
      // Access token is kept in memory only — not localStorage — to reduce XSS surface.
      update((s) => ({ ...s, accessToken: pair.access_token }));

      const user = await apiFetch<UserRead>("/api/auth/me");
      set({
        user,
        accessToken: pair.access_token,
        loading: false,
        error: null,
        initialized: true,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed.";
      update((s) => ({
        ...s,
        loading: false,
        error: message,
        user: null,
        accessToken: null,
      }));
      clearRefreshToken();
    }
  }

  async function register(email: string, password: string): Promise<void> {
    update((s) => ({ ...s, loading: true, error: null }));
    try {
      await apiFetch<UserRead>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      update((s) => ({ ...s, loading: false }));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Registration failed.";
      update((s) => ({ ...s, loading: false, error: message }));
    }
  }

  async function logout(): Promise<void> {
    const refreshToken = getStoredRefreshToken();
    // Always clear local state regardless of whether the server call succeeds.
    clearRefreshToken();
    set({ ...initialState, initialized: true });

    if (refreshToken) {
      try {
        await apiFetch<void>("/api/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      } catch {
        // Server-side revocation failed — token will expire on its own. Local
        // state is already cleared so the user is effectively logged out.
      }
    }
  }

  async function refresh(): Promise<void> {
    const refreshToken = getStoredRefreshToken();
    if (!refreshToken) {
      throw new Error("No refresh token available.");
    }

    try {
      const pair = await apiFetch<TokenPairRead>("/api/auth/refresh", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      storeRefreshToken(pair.refresh_token);
      update((s) => ({ ...s, accessToken: pair.access_token }));
    } catch (error) {
      await logout();
      throw error;
    }
  }

  async function init(): Promise<void> {
    const refreshToken = getStoredRefreshToken();
    if (!refreshToken) {
      update((s) => ({ ...s, initialized: true }));
      return;
    }

    try {
      await refresh();
      const user = await apiFetch<UserRead>("/api/auth/me");
      update((s) => ({ ...s, user, initialized: true }));
    } catch {
      // Refresh failed — clear stale tokens and return as unauthenticated.
      clearRefreshToken();
      set({ ...initialState, initialized: true });
    }
  }

  return { subscribe, set, update, login, register, logout, refresh, init };
}

export const authStore = createAuthStore();

/** Derived helper — true when a user is authenticated. */
export function isAuthenticated(): boolean {
  return get(authStore).user !== null;
}
