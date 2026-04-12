<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { base } from "$app/paths";
  import { resetPassword } from "$lib/api/auth.js";
  import { Button, ErrorBanner } from "$lib/components/index.js";

  let token = $state("");
  let password = $state("");
  let confirmPassword = $state("");
  let passwordMismatch = $state(false);
  let loading = $state(false);
  let error = $state<string | null>(null);

  onMount(() => {
    token = $page.url.searchParams.get("token") ?? "";
  });

  async function handleSubmit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    passwordMismatch = false;

    if (password !== confirmPassword) {
      passwordMismatch = true;
      return;
    }

    loading = true;
    error = null;

    try {
      await resetPassword(token, password);
      // Navigate to login with a success flag so the login page can show a toast.
      goto(`${base}/login?reset=1`);
    } catch (err) {
      error = err instanceof Error ? err.message : "Password reset failed.";
    } finally {
      loading = false;
    }
  }
</script>

<div class="reset-page">
  <h1>Reset Password</h1>

  <ErrorBanner message={error} />

  {#if passwordMismatch}
    <div role="alert" id="password-mismatch" class="validation-error">
      Passwords do not match.
    </div>
  {/if}

  <form class="reset-form" onsubmit={handleSubmit}>
    <div class="field">
      <label for="password">New Password</label>
      <input
        id="password"
        type="password"
        bind:value={password}
        required
        minlength="8"
        autocomplete="new-password"
        aria-describedby={passwordMismatch ? "password-mismatch" : undefined}
      />
    </div>

    <div class="field">
      <label for="confirm-password">Confirm New Password</label>
      <input
        id="confirm-password"
        type="password"
        bind:value={confirmPassword}
        required
        autocomplete="new-password"
        aria-describedby={passwordMismatch ? "password-mismatch" : undefined}
      />
    </div>

    <Button type="submit" {loading} disabled={loading || !token}
      >Reset Password</Button
    >
  </form>
</div>

<style>
  .reset-page {
    max-width: 24rem;
    margin: var(--space-8) auto 0;
  }

  h1 {
    margin-top: 0;
    color: var(--color-text);
  }

  .reset-form {
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

  .validation-error {
    padding: var(--space-2) var(--space-3);
    background-color: color-mix(
      in srgb,
      var(--color-danger) 10%,
      var(--color-surface)
    );
    border: 1px solid var(--color-danger);
    border-radius: var(--radius-md);
    color: var(--color-danger);
    font-size: 0.875rem;
    margin-bottom: var(--space-2);
  }
</style>
