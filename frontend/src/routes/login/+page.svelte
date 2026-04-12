<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { base } from "$app/paths";
  import { authStore } from "$lib/stores/auth.js";
  import {
    Button,
    ErrorBanner,
    LoadingSpinner,
  } from "$lib/components/index.js";

  let email = $state("");
  let password = $state("");

  onMount(() => {
    if ($authStore.user) {
      goto(`${base}/games`);
    }
  });

  async function handleSubmit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    await authStore.login(email, password);
    if ($authStore.user) {
      goto(`${base}/games`);
    }
  }

  function dismissError(): void {
    authStore.update((s) => ({ ...s, error: null }));
  }
</script>

<div class="login-page">
  <h1>Log In</h1>

  <ErrorBanner message={$authStore.error} on:dismiss={dismissError} />

  <form class="login-form" onsubmit={handleSubmit}>
    <div class="field">
      <label for="email">Email</label>
      <input
        id="email"
        type="email"
        bind:value={email}
        required
        autocomplete="email"
        aria-describedby={$authStore.error ? "form-error" : undefined}
      />
    </div>

    <div class="field">
      <label for="password">Password</label>
      <input
        id="password"
        type="password"
        bind:value={password}
        required
        autocomplete="current-password"
      />
    </div>

    <Button
      type="submit"
      loading={$authStore.loading}
      disabled={$authStore.loading}
    >
      {#if $authStore.loading}
        <LoadingSpinner />
      {/if}
      Log In
    </Button>
  </form>

  <div class="login-links">
    <a href="{base}/register">Create an account</a>
    <a href="{base}/forgot-password">Forgot password?</a>
  </div>
</div>

<style>
  .login-page {
    max-width: 24rem;
    margin: var(--space-8) auto 0;
  }

  h1 {
    margin-top: 0;
    color: var(--color-text);
  }

  .login-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    margin-top: var(--space-4);
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  label {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-text);
  }

  input {
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background-color: var(--color-surface);
    color: var(--color-text);
    font-family: var(--font-body);
    font-size: 0.875rem;
  }

  input:focus {
    outline: 2px solid var(--color-primary);
    outline-offset: 1px;
  }

  .login-links {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin-top: var(--space-4);
    font-size: 0.875rem;
  }

  .login-links a {
    color: var(--color-primary);
  }
</style>
