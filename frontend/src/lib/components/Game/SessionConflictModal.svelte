<script lang="ts">
  import Button from "$lib/components/Button.svelte";

  interface Props {
    /** ISO 8601 timestamp from SessionConflictRead.acquired_at */
    acquiredAt: string;
    onTakeover: () => void;
    onCancel: () => void;
  }

  let { acquiredAt, onTakeover, onCancel }: Props = $props();

  /** Human-readable relative time, e.g. "3 minutes ago". */
  const relativeTime = $derived((): string => {
    const acquired = new Date(acquiredAt);
    if (isNaN(acquired.getTime())) return "some time ago";
    const diffMs = Date.now() - acquired.getTime();
    const diffMin = Math.floor(diffMs / 60_000);
    if (diffMin < 1) return "moments ago";
    if (diffMin === 1) return "1 minute ago";
    return `${diffMin} minutes ago`;
  });
</script>

<!-- Non-blocking overlay: renders above the page content without obscuring everything -->
<div
  class="conflict-overlay"
  role="dialog"
  aria-modal="true"
  aria-label="Session conflict"
>
  <div class="conflict-modal">
    <h3 class="heading">Another session is active</h3>
    <p class="detail">
      A session for this character was active <strong>{relativeTime()}</strong>.
      You can take over and resume where it left off, or cancel and return to
      the overworld.
    </p>
    <div class="actions">
      <Button variant="primary" onclick={onTakeover}>
        Take over this session
      </Button>
      <Button variant="secondary" onclick={onCancel}>Cancel</Button>
    </div>
  </div>
</div>

<style>
  .conflict-overlay {
    position: fixed;
    /* Anchored to bottom-right so the overworld is still visible */
    bottom: var(--space-6);
    right: var(--space-6);
    z-index: 200;
    max-width: 22rem;
  }

  .conflict-modal {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .heading {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
  }

  .detail {
    margin: 0;
    font-size: 0.875rem;
    color: var(--color-text-muted);
    line-height: 1.5;
  }

  .actions {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
</style>
