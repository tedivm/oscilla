<script lang="ts">
  import { base } from "$app/paths";
  import { authStore } from "$lib/stores/auth.js";
  import { ThemeToggle } from "$lib/components/index.js";

  function handleLogout(): void {
    authStore.logout();
  }
</script>

<nav class="navbar">
  <div class="navbar-brand">
    <a href="{base}/" class="brand-link">Oscilla</a>
  </div>

  <div class="navbar-links">
    {#if $authStore.user}
      <a href="{base}/games" class="nav-link">Games</a>
      <a href="{base}/characters" class="nav-link">Characters</a>
      <button type="button" class="nav-btn" onclick={handleLogout}
        >Logout</button
      >
    {:else}
      <a href="{base}/login" class="nav-link">Login</a>
      <a href="{base}/register" class="nav-link">Register</a>
    {/if}
    <ThemeToggle />
  </div>
</nav>

<style>
  .navbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-3) var(--space-6);
    background-color: var(--color-surface);
    border-bottom: 1px solid var(--color-border);
    box-shadow: var(--shadow-card);
  }

  .brand-link {
    font-weight: 700;
    font-size: 1.125rem;
    color: var(--color-primary);
    text-decoration: none;
  }

  .brand-link:hover {
    color: var(--color-primary-hover);
  }

  .navbar-links {
    display: flex;
    align-items: center;
    gap: var(--space-4);
  }

  .nav-link {
    color: var(--color-text);
    text-decoration: none;
    font-size: 0.875rem;
  }

  .nav-link:hover {
    color: var(--color-primary);
  }

  .nav-btn {
    background: none;
    border: none;
    color: var(--color-text);
    cursor: pointer;
    font-family: var(--font-body);
    font-size: 0.875rem;
    padding: 0;
  }

  .nav-btn:hover {
    color: var(--color-primary);
  }
</style>
