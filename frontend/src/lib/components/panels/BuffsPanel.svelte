<script lang="ts">
  import type { BuffRead } from "$lib/api/types.js";

  interface Props {
    active_buffs: BuffRead[];
  }

  let { active_buffs }: Props = $props();
</script>

<section class="panel">
  <h2>Buffs</h2>

  {#if active_buffs.length === 0}
    <p class="empty">No active buffs.</p>
  {:else}
    <ul class="list">
      {#each active_buffs as buff (buff.ref)}
        <li>
          <strong>{buff.ref}</strong>
          {#if buff.remaining_turns !== null}
            <span>Turns: {buff.remaining_turns}</span>
          {/if}
          {#if buff.tick_expiry !== null}
            <span>Tick expiry: {buff.tick_expiry}</span>
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

  .list {
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
