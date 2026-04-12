<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { base } from "$app/paths";
  import { authStore } from "$lib/stores/auth.js";
  import { Button, ErrorBanner } from "$lib/components/index.js";

  let email = $state("");
  let password = $state("");
  let confirmPassword = $state("");
  let passwordMismatch = $state(false);
  let registered = $state(false);

  onMount(() => {
    if ($authStore.user) {
      goto(`${base}/games`);
    }
  });

  async function handleSubmit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    passwordMismatch = false;

    if (password !== confirmPassword) {
      passwordMismatch = true;
      return;
    }

    await authStore.register(email, password);
    if (!$authStore.error) {
      registered = true;
    }
  }

  function dismissError(): void {
    authStore.update((s) => ({ ...s, error: null }));
  }
</script>

<div class="register-page">
  <h1>Create Account</h1>

  {#if registered}
    <div class="success-message">
      <p>
        Check your email to verify your account. Once verified,
        <a href="{base}/login">log in here</a>.
      </p>
    </div>
  {:else}
    <ErrorBanner message={$authStore.error} on:dismiss={dismissError} />

    {#if passwordMismatch}
      <div role="alert" class="validation-error">Passwords do not match.</div>
    {/if}

    <form class="register-form" onsubmit={handleSubmit}>
      <div class="field">
        <label for="email">Email</label>
        <input
          id="email"
          type="email"
          bind:value={email}
          required
          autocomplete="email"
        />
      </div>

      <div class="field">
        <label for="password">Password</label>
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
        <label for="confirm-password">Confirm Password</label>
        <input
          id="confirm-password"
          type="password"
          bind:value={confirmPassword}
          required
          autocomplete="new-password"
          aria-describedby={passwordMismatch ? "password-mismatch" : undefined}
        />
      </div>

      <Button
        type="submit"
        loading={$authStore.loading}
        disabled={$authStore.loading}
      >
        Create Account
      </Button>
    </form>

    <div class="register-links">
      <a href="{base}/login">Already have an account? Log in</a>
    </div>
  {/if}
</div>

<style>
  .register-page {
    max-width: 24rem;
    margin: var(--space-8) auto 0;
  }

  h1 {
    margin-top: 0;
    color: var(--color-text);
  }

  .register-form {
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

  .success-message {
    padding: var(--space-4);
    background-color: color-mix(
      in srgb,
      var(--color-success) 10%,
      var(--color-surface)
    );
    border: 1px solid var(--color-success);
    border-radius: var(--radius-md);
    color: var(--color-success);
  }

  .register-links {
    margin-top: var(--space-4);
    font-size: 0.875rem;
  }

  .register-links a {
    color: var(--color-primary);
  }
</style>
