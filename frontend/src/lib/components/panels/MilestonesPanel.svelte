<script lang="ts">
  import type { MilestoneRead } from "$lib/api/types.js";

  interface Props {
    milestones: Record<string, MilestoneRead>;
  }

  let { milestones }: Props = $props();
  const entries = $derived(Object.entries(milestones));

  function formatTs(timestamp: number): string {
    return new Date(timestamp * 1000).toLocaleString();
  }
</script>

{#if entries.length > 0}
  <section class="panel">
    <h2>Milestones</h2>
    <ul>
      {#each entries as [key, milestone]}
        <li>
          <strong>{milestone.ref ?? key}</strong>
          <span>Tick: {milestone.grant_tick}</span>
          <span>Granted: {formatTs(milestone.grant_timestamp)}</span>
        </li>
      {/each}
    </ul>
  </section>
{/if}

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

  ul {
    margin: 0;
    padding-left: 1rem;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  li {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  li span {
    color: var(--color-text-muted);
    font-size: 0.875rem;
  }
</style>
