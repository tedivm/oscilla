<script lang="ts">
  import { createEventDispatcher } from "svelte";

  interface Props {
    message: string | null;
  }

  let { message }: Props = $props();

  const dispatch = createEventDispatcher<{ dismiss: void }>();

  function dismiss(): void {
    dispatch("dismiss");
  }
</script>

{#if message !== null}
  <div role="alert" aria-live="polite" class="error-banner">
    <span class="error-message">{message}</span>
    <button
      class="dismiss-btn"
      type="button"
      aria-label="Dismiss error"
      onclick={dismiss}
    >
      ✕
    </button>
  </div>
{/if}

<style>
  .error-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    background-color: color-mix(
      in srgb,
      var(--color-danger) 10%,
      var(--color-surface)
    );
    border: 1px solid var(--color-danger);
    border-radius: var(--radius-md);
    color: var(--color-danger);
    font-size: 0.875rem;
  }

  .error-message {
    flex: 1;
  }

  .dismiss-btn {
    background: none;
    border: none;
    color: var(--color-danger);
    cursor: pointer;
    font-size: 0.875rem;
    padding: 0 var(--space-1);
    line-height: 1;
  }

  .dismiss-btn:hover {
    opacity: 0.75;
  }
</style>
