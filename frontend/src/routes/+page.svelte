<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { base } from "$app/paths";
  import { authStore } from "$lib/stores/auth.js";
  import { Button } from "$lib/components/index.js";

  onMount(() => {
    // If already authenticated, skip the landing and go straight to games.
    if ($authStore.user) {
      goto(`${base}/games`);
    }
  });
</script>

<section class="landing">
  <h1 class="landing-title">Oscilla</h1>
  <p class="landing-tagline">
    A text-based adventure engine. Your story begins here.
  </p>

  <div class="landing-actions">
    <Button variant="primary" onclick={() => goto(`${base}/login`)}
      >Log In</Button
    >
    <Button variant="secondary" onclick={() => goto(`${base}/register`)}
      >Register</Button
    >
  </div>
</section>

<style>
  .landing {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 60vh;
    text-align: center;
    gap: var(--space-4);
  }

  .landing-title {
    font-size: 3rem;
    font-weight: 700;
    color: var(--color-primary);
    margin: 0;
  }

  .landing-tagline {
    font-size: 1.25rem;
    color: var(--color-text-muted);
    margin: 0;
  }

  .landing-actions {
    display: flex;
    gap: var(--space-3);
    margin-top: var(--space-4);
  }
</style>
