<script lang="ts">
  import type { ItemInstanceRead, StackedItemRead } from "$lib/api/types.js";

  interface Props {
    instances: ItemInstanceRead[];
    stacks: Record<string, StackedItemRead>;
  }

  let { instances, stacks }: Props = $props();

  const equippedRefs = $derived(instances.map((i) => i.item_ref));
  const stackRefs = $derived(Object.keys(stacks));
</script>

<div class="inventory-quick-actions">
  <h4 class="heading">Inventory</h4>
  {#if equippedRefs.length === 0 && stackRefs.length === 0}
    <p class="empty-state">Nothing in inventory.</p>
  {:else}
    <ul class="item-list">
      {#each equippedRefs as ref}
        <li class="item-row">{ref}</li>
      {/each}
      {#each stackRefs as ref}
        <li class="item-row">{ref} ×{stacks[ref].quantity}</li>
      {/each}
    </ul>
  {/if}
  <!-- TODO MU6: equip/use actions -->
</div>

<style>
  .inventory-quick-actions {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .heading {
    margin: 0;
    font-size: 0.875rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .empty-state {
    margin: 0;
    font-size: 0.875rem;
    color: var(--color-text-muted);
  }

  .item-list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .item-row {
    font-size: 0.875rem;
  }
</style>
