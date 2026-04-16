<script lang="ts">
  import { onMount } from "svelte";
  import { goto, beforeNavigate } from "$app/navigation";
  import { base } from "$app/paths";
  import { authStore } from "$lib/stores/auth.js";
  import { gameSession } from "$lib/stores/gameSession.js";
  import { NavBar, LoadingSpinner } from "$lib/components/index.js";
  import "$lib/theme/tokens.css";
  import type { Snippet } from "svelte";

  let { children }: { children: Snippet } = $props();

  // Paths that require authentication.
  const PROTECTED_PREFIXES = ["/games", "/characters"];

  onMount(async () => {
    await authStore.init();
  });

  // Auth guard: redirect unauthenticated users away from protected routes.
  // Wait for init() to complete before checking — otherwise a page refresh
  // redirects to /login before the stored refresh token is validated.
  $effect(() => {
    const { user, initialized } = $authStore;
    if (!initialized) return;
    if (!user) {
      // Check if current path (relative to base) is protected.
      const currentPath =
        typeof window !== "undefined" ? window.location.pathname : "";
      // Strip the base prefix to get the route-relative path.
      const basePath = base || "";
      const routePath = currentPath.startsWith(basePath)
        ? currentPath.slice(basePath.length)
        : currentPath;
      const isProtected = PROTECTED_PREFIXES.some((prefix) =>
        routePath.startsWith(prefix),
      );
      if (isProtected) {
        goto(`${base}/login`);
      }
    }
  });

  /**
   * D7: Hard-block navigation away from the play screen mid-adventure.
   *
   * When the player is in an active adventure (mode 'adventure' or 'loading'),
   * any attempt to navigate away from /play is unconditionally cancelled.
   * A confirmation dialog was rejected because it creates a bypass path for
   * triggered adventures (e.g., post-creation tutorials auto-started by the engine).
   * The play screen must provide an explicit abandon action that calls
   * gameSession.close() before programmatically navigating away.
   */
  beforeNavigate(({ cancel, from, to }) => {
    const isLeavingPlay =
      (from?.url.pathname.includes("/play") ?? false) &&
      !(to?.url.pathname.includes("/play") ?? false);
    const mode = $gameSession.mode;
    if (isLeavingPlay && (mode === "adventure" || mode === "loading")) {
      cancel();
    }
  });
</script>

<NavBar />

<main class="main-container">
  {#if !$authStore.initialized}
    <div class="auth-loading">
      <LoadingSpinner />
    </div>
  {:else}
    {@render children()}
  {/if}
</main>

<style>
  .main-container {
    max-width: 72rem;
    margin: 0 auto;
    padding: var(--space-6) var(--space-4);
  }

  .auth-loading {
    display: flex;
    justify-content: center;
    padding: var(--space-8);
  }
</style>
