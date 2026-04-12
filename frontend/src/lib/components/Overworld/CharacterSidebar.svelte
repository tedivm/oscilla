<script lang="ts">
  import type { CharacterStateRead } from "$lib/api/types.js";

  interface Props {
    character: CharacterStateRead;
  }

  let { character }: Props = $props();

  /** Display only stats that have a display_name, plus hp/max_hp by convention. */
  const displayStats = $derived(
    Object.values(character.stats).filter((s) => s.display_name !== null),
  );
</script>

<aside class="character-sidebar">
  <h3 class="char-name">{character.name}</h3>

  {#if displayStats.length > 0}
    <dl class="stat-list">
      {#each displayStats as stat}
        <div class="stat-row">
          <dt class="stat-label">{stat.display_name ?? stat.ref}</dt>
          <dd class="stat-value">{stat.value ?? "—"}</dd>
        </div>
      {/each}
    </dl>
  {/if}

  <dl class="meta-list">
    {#if character.active_buffs.length > 0}
      <div class="stat-row">
        <dt class="stat-label">Active buffs</dt>
        <dd class="stat-value">{character.active_buffs.length}</dd>
      </div>
    {/if}
    {#if character.prestige_count > 0}
      <div class="stat-row">
        <dt class="stat-label">Prestige</dt>
        <dd class="stat-value">{character.prestige_count}</dd>
      </div>
    {/if}
  </dl>
</aside>

<style>
  .character-sidebar {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
  }

  .char-name {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
  }

  .stat-list,
  .meta-list {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: var(--space-2);
  }

  .stat-label {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  .stat-value {
    font-size: 0.875rem;
    font-weight: 600;
    margin: 0;
  }
</style>
