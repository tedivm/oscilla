<script lang="ts">
  import type { SSEEvent } from "$lib/stores/gameSession.js";
  import type { SkillMenuEventData } from "$lib/api/types.js";
  import Button from "$lib/components/Button.svelte";

  interface Props {
    event: SSEEvent;
    onSelect: (skillIndex: number) => void;
  }

  let { event, onSelect }: Props = $props();

  const eventData = $derived(event.data as SkillMenuEventData);

  let submitting = $state(false);

  function select(index: number): void {
    if (submitting) return;
    submitting = true;
    onSelect(index);
  }

  function handleKey(e: KeyboardEvent): void {
    if (submitting) return;
    const n = parseInt(e.key, 10);
    if (n >= 1 && n <= 9 && n <= eventData.skills.length) {
      select(n);
    }
  }
</script>

<svelte:window onkeydown={handleKey} />

<div class="skill-menu">
  <p class="heading">Choose a skill:</p>
  <div class="skills">
    {#each eventData.skills as skill, i}
      <div class="skill-card" class:on-cooldown={skill.on_cooldown}>
        <div class="skill-info">
          <span class="skill-name">
            <span class="key-hint">{i + 1}</span>
            {skill.name}
          </span>
          <span class="skill-desc">{skill.description}</span>
          {#if skill.on_cooldown}
            <span class="cooldown-badge">On cooldown</span>
          {/if}
        </div>
        <Button
          variant="secondary"
          disabled={submitting || skill.on_cooldown}
          onclick={() => select(i + 1)}
        >
          Use
        </Button>
      </div>
    {/each}
  </div>
</div>

<style>
  .skill-menu {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .heading {
    margin: 0;
    font-weight: 600;
  }

  .skills {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .skill-card {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
  }

  .skill-card.on-cooldown {
    opacity: 0.6;
  }

  .skill-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .skill-name {
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .skill-desc {
    font-size: 0.875rem;
    color: var(--color-text-muted);
  }

  .cooldown-badge {
    font-size: 0.75rem;
    color: var(--color-warning, #f59e0b);
    font-weight: 500;
  }

  .key-hint {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.25rem;
    height: 1.25rem;
    border-radius: var(--radius-sm);
    background: var(--color-surface-raised);
    font-size: 0.75rem;
    font-weight: 700;
    flex-shrink: 0;
  }
</style>
