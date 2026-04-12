<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { base } from "$app/paths";
  import { authStore } from "$lib/stores/auth.js";
  import { NavBar } from "$lib/components/index.js";
  import "$lib/theme/tokens.css";
  import type { Snippet } from "svelte";

  let { children }: { children: Snippet } = $props();

  // Paths that require authentication.
  const PROTECTED_PREFIXES = ["/games", "/characters"];

  onMount(async () => {
    await authStore.init();
  });

  // Auth guard: redirect unauthenticated users away from protected routes.
  $effect(() => {
    const { user } = $authStore;
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
</script>

<NavBar />

<main class="main-container">
  {@render children()}
</main>

<style>
  .main-container {
    max-width: 72rem;
    margin: 0 auto;
    padding: var(--space-6) var(--space-4);
  }
</style>
