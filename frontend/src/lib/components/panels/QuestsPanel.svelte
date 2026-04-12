<script lang="ts">
  import type { ActiveQuestRead } from "$lib/api/types.js";

  interface Props {
    active_quests: ActiveQuestRead[];
    completed_quests: string[];
    failed_quests: string[];
  }

  let { active_quests, completed_quests, failed_quests }: Props = $props();
</script>

<section class="panel">
  <h2>Quests</h2>

  <div class="section">
    <h3>Active</h3>
    {#if active_quests.length === 0}
      <p class="empty">No active quests.</p>
    {:else}
      <ul>
        {#each active_quests as quest (quest.ref)}
          <li>{quest.ref} <span>(stage: {quest.current_stage})</span></li>
        {/each}
      </ul>
    {/if}
  </div>

  <div class="section">
    <h3>Completed</h3>
    {#if completed_quests.length === 0}
      <p class="empty">No completed quests.</p>
    {:else}
      <ul>
        {#each completed_quests as questRef (questRef)}
          <li>{questRef}</li>
        {/each}
      </ul>
    {/if}
  </div>

  <div class="section">
    <h3>Failed</h3>
    {#if failed_quests.length === 0}
      <p class="empty">No failed quests.</p>
    {:else}
      <ul>
        {#each failed_quests as questRef (questRef)}
          <li>{questRef}</li>
        {/each}
      </ul>
    {/if}
  </div>
</section>

<style>
  .panel {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    background-color: var(--color-surface);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  h2,
  h3 {
    margin: 0;
  }

  h2 {
    font-size: 1.125rem;
  }

  h3 {
    font-size: 1rem;
    margin-bottom: var(--space-1);
  }

  .section ul {
    margin: 0;
    padding-left: 1rem;
  }

  .section li span {
    color: var(--color-text-muted);
  }

  .empty {
    margin: 0;
    color: var(--color-text-muted);
  }
</style>
