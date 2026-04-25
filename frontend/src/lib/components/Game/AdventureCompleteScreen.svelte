<script lang="ts">
  import type { SSEEvent } from "$lib/stores/gameSession.js";
  import type { AdventureCompleteEventData } from "$lib/api/types.js";
  import { renderMarkup } from "$lib/utils/markup.js";
  import Button from "$lib/components/Button.svelte";

  interface Props {
    event: SSEEvent | null;
    onContinue: () => void;
  }

  let { event, onContinue }: Props = $props();

  const eventData = $derived(
    event ? (event.data as AdventureCompleteEventData) : null,
  );
</script>

<div class="adventure-complete">
  <div class="outcome-banner">
    <h2 class="outcome-heading">Adventure Complete</h2>
    {#if eventData?.outcome}
      <p class="outcome">{@html renderMarkup(eventData.outcome)}</p>
    {/if}
  </div>
  {#if eventData?.narrative}
    <p class="summary">{@html renderMarkup(eventData.narrative)}</p>
  {/if}
  <Button variant="primary" onclick={onContinue}>Return to Overworld</Button>
</div>

<style>
  .adventure-complete {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-6) var(--space-4);
    text-align: center;
  }

  .outcome-banner {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .outcome-heading {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
  }

  .outcome {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--color-primary);
  }

  .summary {
    margin: 0;
    color: var(--color-text-muted);
    max-width: 480px;
    align-self: center;
  }
</style>
