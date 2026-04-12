<script lang="ts">
  import type { StatValue } from "$lib/api/types.js";

  interface Props {
    stats: Record<string, StatValue>;
  }

  let { stats }: Props = $props();

  const entries = $derived(Object.entries(stats));

  function displayValue(stat: StatValue): string {
    if (stat.value === null) {
      return "—";
    }
    return String(stat.value);
  }
</script>

<section class="panel">
  <h2>Stats</h2>

  {#if entries.length === 0}
    <p class="empty">No stats available.</p>
  {:else}
    <dl class="stats-list">
      {#each entries as [key, stat]}
        <div class="stat-row">
          <dt>{stat.display_name ?? key}</dt>
          <dd>{displayValue(stat)}</dd>
        </div>
      {/each}
    </dl>
  {/if}
</section>

<style>
  .panel {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    background-color: var(--color-surface);
  }

  .panel h2 {
    margin: 0 0 var(--space-3) 0;
    font-size: 1.125rem;
  }

  .stats-list {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    gap: var(--space-3);
    padding-bottom: var(--space-1);
    border-bottom: 1px solid var(--color-border);
  }

  .stat-row:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  dt {
    color: var(--color-text-muted);
  }

  dd {
    margin: 0;
    font-weight: 600;
  }

  .empty {
    margin: 0;
    color: var(--color-text-muted);
  }
</style>
