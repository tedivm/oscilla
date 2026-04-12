<script lang="ts">
  import type { ItemInstanceRead, StackedItemRead } from "$lib/api/types.js";

  interface Props {
    stacks: Record<string, StackedItemRead>;
    instances: ItemInstanceRead[];
  }

  let { stacks, instances }: Props = $props();

  let tab = $state<"stacked" | "instances">("stacked");
  const stackedEntries = $derived(Object.entries(stacks));
</script>

<section class="panel">
  <h2>Inventory</h2>

  <div class="tabs" role="tablist" aria-label="Inventory views">
    <button
      type="button"
      role="tab"
      aria-selected={tab === "stacked"}
      class:active={tab === "stacked"}
      onclick={() => (tab = "stacked")}>Stacked Items</button
    >
    <button
      type="button"
      role="tab"
      aria-selected={tab === "instances"}
      class:active={tab === "instances"}
      onclick={() => (tab = "instances")}>Item Instances</button
    >
  </div>

  {#if tab === "stacked"}
    {#if stackedEntries.length === 0}
      <p class="empty">No stacked items.</p>
    {:else}
      <ul class="list">
        {#each stackedEntries as [key, item]}
          <li>
            <span>{item.ref ?? key}</span><strong>x{item.quantity}</strong>
          </li>
        {/each}
      </ul>
    {/if}
  {:else if instances.length === 0}
    <p class="empty">No item instances.</p>
  {:else}
    <ul class="list detailed">
      {#each instances as item (item.instance_id)}
        <li>
          <div>
            <strong>{item.item_ref}</strong>
            <span>ID: {item.instance_id.slice(0, 8)}</span>
            {#if item.charges_remaining !== null}
              <span>Charges: {item.charges_remaining}</span>
            {/if}
          </div>
          {#if Object.keys(item.modifiers).length > 0}
            <small>
              {Object.entries(item.modifiers)
                .map(([k, v]) => `${k}: ${v}`)
                .join(", ")}
            </small>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .panel {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    background-color: var(--color-surface);
  }

  h2 {
    margin: 0 0 var(--space-3) 0;
    font-size: 1.125rem;
  }

  .tabs {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }

  .tabs button {
    border: 1px solid var(--color-border);
    background: transparent;
    color: var(--color-text);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    cursor: pointer;
  }

  .tabs button.active {
    background: var(--color-primary);
    border-color: var(--color-primary);
    color: #fff;
  }

  .list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .list > li {
    display: flex;
    justify-content: space-between;
    gap: var(--space-2);
    border-bottom: 1px solid var(--color-border);
    padding-bottom: var(--space-1);
  }

  .list > li:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  .detailed li {
    display: block;
  }

  .detailed div {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    color: var(--color-text-muted);
  }

  small {
    display: block;
    margin-top: var(--space-1);
    color: var(--color-text-muted);
  }

  .empty {
    margin: 0;
    color: var(--color-text-muted);
  }
</style>
