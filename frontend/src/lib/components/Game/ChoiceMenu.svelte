<script lang="ts">
  import type { SSEEvent } from "$lib/stores/gameSession.js";
  import type { ChoiceEventData } from "$lib/api/types.js";
  import Button from "$lib/components/Button.svelte";

  interface Props {
    event: SSEEvent;
    onSelect: (choice: number) => void;
  }

  let { event, onSelect }: Props = $props();

  const eventData = $derived(event.data as ChoiceEventData);

  // True after the player has submitted a choice; prevents double-submission.
  let submitting = $state(false);

  function select(index: number): void {
    if (submitting) return;
    submitting = true;
    onSelect(index);
  }

  function handleKey(e: KeyboardEvent): void {
    if (submitting) return;
    const n = parseInt(e.key, 10);
    if (n >= 1 && n <= 9 && n <= eventData.options.length) {
      select(n);
    }
  }
</script>

<svelte:window onkeydown={handleKey} />

<div class="choice-menu">
  {#if eventData.prompt}
    <p class="prompt">{eventData.prompt}</p>
  {/if}
  <div class="options">
    {#each eventData.options as option, i}
      <Button
        variant="secondary"
        disabled={submitting}
        onclick={() => select(i + 1)}
      >
        <span class="key-hint">{i + 1}</span>
        {option}
      </Button>
    {/each}
  </div>
</div>

<style>
  .choice-menu {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .prompt {
    margin: 0;
    font-weight: 500;
  }

  .options {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .key-hint {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.25rem;
    height: 1.25rem;
    border-radius: var(--radius-sm);
    background: var(--color-surface-raised);
    font-size: 0.75rem;
    font-weight: 700;
    flex-shrink: 0;
  }
</style>
