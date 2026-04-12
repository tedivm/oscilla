<script lang="ts">
  import { tick } from "svelte";
  import type { NarrativeEntry } from "$lib/stores/gameSession.js";
  import NarrativeEntryComponent from "./NarrativeEntry.svelte";
  import Button from "$lib/components/Button.svelte";

  interface Props {
    entries: NarrativeEntry[];
  }

  let { entries }: Props = $props();

  let container = $state<HTMLDivElement | undefined>(undefined);
  let isAtBottom = $state(true);

  function scrollToBottom(): void {
    if (container) {
      container.scrollTop = container.scrollHeight;
      isAtBottom = true;
    }
  }

  function onScroll(): void {
    if (!container) return;
    const threshold = 40; // px tolerance
    isAtBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight <
      threshold;
  }

  // Auto-scroll to bottom when new entries arrive, unless player has scrolled up.
  $effect(() => {
    // Access entries.length to track changes.
    const _len = entries.length;
    if (isAtBottom) {
      tick().then(() => scrollToBottom());
    }
  });
</script>

<div class="narrative-log-wrapper">
  <div
    class="narrative-log"
    bind:this={container}
    onscroll={onScroll}
    role="log"
    aria-live="polite"
    aria-label="Adventure narrative"
  >
    {#each entries as entry (entry.id)}
      <NarrativeEntryComponent {entry} />
    {/each}
  </div>

  {#if !isAtBottom}
    <div class="scroll-anchor">
      <Button variant="secondary" onclick={scrollToBottom}>
        Scroll to bottom ↓
      </Button>
    </div>
  {/if}
</div>

<style>
  .narrative-log-wrapper {
    position: relative;
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
  }

  .narrative-log {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .scroll-anchor {
    position: absolute;
    bottom: var(--space-3);
    left: 50%;
    transform: translateX(-50%);
  }
</style>
