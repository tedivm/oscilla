<script lang="ts">
  import type {
    LocationOptionRead,
    OverworldStateRead,
  } from "$lib/api/types.js";
  import { navigateLocation } from "$lib/api/characters.js";
  import { ApiError } from "$lib/api/client.js";
  import Button from "$lib/components/Button.svelte";
  import { ErrorBanner } from "$lib/components/index.js";
  import LoadingSpinner from "$lib/components/LoadingSpinner.svelte";

  interface Props {
    characterId: string;
    locations: LocationOptionRead[];
    onNavigated: (newState: OverworldStateRead) => void;
  }

  let { characterId, locations, onNavigated }: Props = $props();

  let navigating = $state<string | null>(null); // ref of the location currently loading
  let error = $state<string | null>(null);

  async function navigate(locationRef: string): Promise<void> {
    if (navigating) return;
    error = null;
    navigating = locationRef;
    try {
      const newState = await navigateLocation(characterId, locationRef);
      onNavigated(newState);
    } catch (e) {
      error = e instanceof Error ? e.message : "Navigation failed.";
    } finally {
      navigating = null;
    }
  }
</script>

<div class="navigation-panel">
  <h3 class="heading">Navigate</h3>
  {#if error}
    <ErrorBanner message={error} />
  {/if}
  <div class="locations">
    {#each locations as loc}
      <div class="location-row" class:current={loc.is_current}>
        <span class="loc-name">{loc.display_name}</span>
        {#if loc.is_current}
          <span class="current-badge">Current</span>
        {:else}
          <Button
            variant="secondary"
            disabled={navigating !== null}
            onclick={() => navigate(loc.ref)}
          >
            {#if navigating === loc.ref}
              <LoadingSpinner />
            {:else}
              Go
            {/if}
          </Button>
        {/if}
      </div>
    {/each}
  </div>
</div>

<style>
  .navigation-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .heading {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
  }

  .locations {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .location-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
  }

  .location-row.current {
    border-color: var(--color-primary);
    background: var(--color-surface-raised);
  }

  .loc-name {
    font-size: 0.9375rem;
  }

  .current-badge {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-primary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
</style>
