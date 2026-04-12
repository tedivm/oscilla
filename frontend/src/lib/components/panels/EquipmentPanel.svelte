<script lang="ts">
  import type { ItemInstanceRead } from "$lib/api/types.js";

  interface Props {
    equipment: Record<string, ItemInstanceRead>;
  }

  let { equipment }: Props = $props();
  const entries = $derived(Object.entries(equipment));
</script>

<section class="panel">
  <h2>Equipment</h2>

  {#if entries.length === 0}
    <p class="empty">No equipment items equipped.</p>
  {:else}
    <table>
      <thead>
        <tr>
          <th>Slot</th>
          <th>Item</th>
          <th>Charges</th>
        </tr>
      </thead>
      <tbody>
        {#each entries as [slot, item]}
          <tr>
            <td>{slot}</td>
            <td>{item.item_ref}</td>
            <td>{item.charges_remaining ?? "—"}</td>
          </tr>
        {/each}
      </tbody>
    </table>
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

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }

  th,
  td {
    text-align: left;
    padding: var(--space-2);
    border-bottom: 1px solid var(--color-border);
  }

  th {
    color: var(--color-text-muted);
    font-weight: 500;
  }

  .empty {
    margin: 0;
    color: var(--color-text-muted);
  }
</style>
