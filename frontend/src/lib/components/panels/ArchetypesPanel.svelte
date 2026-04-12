<script lang="ts">
  import type { ArchetypeRead } from "$lib/api/types.js";

  interface Props {
    archetypes: ArchetypeRead[];
  }

  let { archetypes }: Props = $props();

  function formatTs(timestamp: number): string {
    return new Date(timestamp * 1000).toLocaleString();
  }
</script>

<section class="panel">
  <h2>Archetypes</h2>

  {#if archetypes.length === 0}
    <p class="empty">No archetypes granted.</p>
  {:else}
    <ul>
      {#each archetypes as archetype (archetype.ref)}
        <li>
          <strong>{archetype.ref}</strong>
          <span>Tick: {archetype.grant_tick}</span>
          <span>Granted: {formatTs(archetype.grant_timestamp)}</span>
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

  .empty {
    margin: 0;
    color: var(--color-text-muted);
  }
</style>
