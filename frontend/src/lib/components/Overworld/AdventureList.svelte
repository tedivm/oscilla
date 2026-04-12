<script lang="ts">
  import type { AdventureOptionRead } from "$lib/api/types.js";
  import Button from "$lib/components/Button.svelte";

  interface Props {
    adventures: AdventureOptionRead[];
    onSelect: (adventureRef: string) => void;
  }

  let { adventures, onSelect }: Props = $props();
</script>

<div class="adventure-list">
  <h3 class="heading">Available Adventures</h3>
  {#if adventures.length === 0}
    <p class="empty-state">No adventures available here.</p>
  {:else}
    <div class="cards">
      {#each adventures as adventure}
        <div class="adventure-card">
          <div class="card-info">
            <span class="card-title">{adventure.display_name}</span>
            {#if adventure.description}
              <span class="card-desc">{adventure.description}</span>
            {/if}
          </div>
          <Button variant="primary" onclick={() => onSelect(adventure.ref)}>
            Begin
          </Button>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .adventure-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .heading {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
  }

  .empty-state {
    margin: 0;
    color: var(--color-text-muted);
    font-size: 0.875rem;
  }

  .cards {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .adventure-card {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
  }

  .card-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .card-title {
    font-weight: 600;
  }

  .card-desc {
    font-size: 0.875rem;
    color: var(--color-text-muted);
  }
</style>
