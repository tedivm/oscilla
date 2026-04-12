<script lang="ts">
  import type { SkillRead } from "$lib/api/types.js";

  interface Props {
    skills: SkillRead[];
  }

  let { skills }: Props = $props();
</script>

<section class="panel">
  <h2>Skills</h2>

  {#if skills.length === 0}
    <p class="empty">No skills unlocked.</p>
  {:else}
    <ul>
      {#each skills as skill (skill.ref)}
        <li>{skill.display_name ?? skill.ref}</li>
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
    gap: var(--space-1);
  }

  .empty {
    margin: 0;
    color: var(--color-text-muted);
  }
</style>
