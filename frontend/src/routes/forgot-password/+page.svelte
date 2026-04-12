<script lang="ts">
  import { base } from "$app/paths";
  import { requestPasswordReset } from "$lib/api/auth.js";
  import { Button, ErrorBanner } from "$lib/components/index.js";

  let email = $state("");
  let loading = $state(false);
  let error = $state<string | null>(null);
  let submitted = $state(false);

  async function handleSubmit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    loading = true;
    error = null;

    try {
      await requestPasswordReset(email);
      // Always show success regardless of whether the email exists — prevents
      // user enumeration.
      submitted = true;
    } catch (err) {
      // Only surface 5xx server errors, not 404 (per spec).
      const status =
        err instanceof Error && "status" in err
          ? (err as { status: number }).status
          : 0;
      if (status >= 500) {
        error = "A server error occurred. Please try again later.";
      } else {
        // Treat all non-500 errors as "quiet success" to prevent enumeration.
        submitted = true;
      }
    } finally {
      loading = false;
    }
  }
</script>

<div class="forgot-page">
  <h1>Forgot Password</h1>

  {#if submitted}
    <div class="info-message">
      If that email is registered, you will receive a reset link shortly.
    </div>
    <p class="back-link"><a href="{base}/login">Back to Login</a></p>
  {:else}
    <ErrorBanner message={error} />

    <form class="forgot-form" onsubmit={handleSubmit}>
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

      <Button type="submit" {loading} disabled={loading}>Send Reset Link</Button
      >
    </form>

    <p class="back-link"><a href="{base}/login">Back to Login</a></p>
  {/if}
</div>

<style>
  .forgot-page {
    max-width: 24rem;
    margin: var(--space-8) auto 0;
  }

  h1 {
    margin-top: 0;
    color: var(--color-text);
  }

  .forgot-form {
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

  .info-message {
    padding: var(--space-4);
    background-color: color-mix(
      in srgb,
      var(--color-primary) 10%,
      var(--color-surface)
    );
    border: 1px solid var(--color-primary);
    border-radius: var(--radius-md);
    color: var(--color-text);
    font-size: 0.875rem;
  }

  .back-link {
    margin-top: var(--space-4);
    font-size: 0.875rem;
  }

  .back-link a {
    color: var(--color-primary);
  }
</style>
