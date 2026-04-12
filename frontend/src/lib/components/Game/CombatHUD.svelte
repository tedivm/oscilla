<script lang="ts">
  import type { SSEEvent } from "$lib/stores/gameSession.js";
  import type { CombatStateEventData } from "$lib/api/types.js";
  import Button from "$lib/components/Button.svelte";

  interface Props {
    event: SSEEvent;
    onAck: () => void;
  }

  let { event, onAck }: Props = $props();

  const eventData = $derived(event.data as CombatStateEventData);

  let submitting = $state(false);

  function ack(): void {
    if (submitting) return;
    submitting = true;
    onAck();
  }

  function handleKey(e: KeyboardEvent): void {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      ack();
    }
  }
</script>

<svelte:window onkeydown={handleKey} />

<div class="combat-hud">
  <p class="round-counter">Round {eventData.round}</p>
  <div class="combatants">
    {#each eventData.combatants as c}
      <div class="combatant" class:player={c.is_player}>
        <span class="name">{c.name}</span>
        <progress
          class="hp-bar"
          value={c.hp}
          max={c.max_hp}
          aria-label="{c.name} HP: {c.hp}/{c.max_hp}"
        ></progress>
        <span class="hp-text">{c.hp}/{c.max_hp}</span>
      </div>
    {/each}
  </div>
  <Button variant="primary" disabled={submitting} onclick={ack}>
    Continue
  </Button>
</div>

<style>
  .combat-hud {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .round-counter {
    margin: 0;
    font-weight: 700;
    font-size: 0.875rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .combatants {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .combatant {
    display: grid;
    grid-template-columns: 8rem 1fr auto;
    align-items: center;
    gap: var(--space-3);
  }

  .combatant.player .name {
    font-weight: 600;
  }

  .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .hp-bar {
    width: 100%;
    height: 0.5rem;
    accent-color: var(--color-success, #22c55e);
  }

  .combatant.player .hp-bar {
    accent-color: var(--color-primary);
  }

  .hp-text {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    white-space: nowrap;
  }
</style>
