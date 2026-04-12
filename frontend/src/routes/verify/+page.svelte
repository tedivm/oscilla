<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { base } from "$app/paths";
  import { verifyEmail } from "$lib/api/auth.js";
  import { ErrorBanner } from "$lib/components/index.js";

  let verified = $state(false);
  let error = $state<string | null>(null);
  let loading = $state(true);

  onMount(async () => {
    const token = $page.url.searchParams.get("token");
    if (!token) {
      error = "No verification token found in the URL.";
      loading = false;
      return;
    }

    try {
      await verifyEmail(token);
      verified = true;
    } catch (err) {
      error = err instanceof Error ? err.message : "Verification failed.";
    } finally {
      loading = false;
    }
  });
</script>

<div class="verify-page">
  <h1>Email Verification</h1>

  {#if loading}
    <p>Verifying your email…</p>
  {:else if verified}
    <div class="success-message">
      <p>Email verified! You can now <a href="{base}/login">log in</a>.</p>
    </div>
  {:else}
    <ErrorBanner message={error} />
    <p class="help-text">
      <a href="{base}/register">Request a new verification email</a>
    </p>
  {/if}
</div>

<style>
  .verify-page {
    max-width: 24rem;
    margin: var(--space-8) auto 0;
  }

  h1 {
    margin-top: 0;
    color: var(--color-text);
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

  .success-message a,
  .help-text a {
    color: var(--color-primary);
  }

  .help-text {
    font-size: 0.875rem;
    margin-top: var(--space-4);
  }
</style>
