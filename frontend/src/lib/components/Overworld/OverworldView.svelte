<script lang="ts">
  import { onDestroy } from "svelte";
  import type {
    OverworldStateRead,
    CharacterStateRead,
    LocationOptionRead,
  } from "$lib/api/types.js";
  import { getOverworld } from "$lib/api/characters.js";
  import { getCurrentPlayState } from "$lib/api/play.js";
  import { gameSession } from "$lib/stores/gameSession.js";
  import LoadingSpinner from "$lib/components/LoadingSpinner.svelte";
  import CharacterSidebar from "./CharacterSidebar.svelte";
  import InventoryQuickActions from "./InventoryQuickActions.svelte";
  import Button from "$lib/components/Button.svelte";

  interface Props {
    characterId: string;
    overworldState: OverworldStateRead | null;
    character: CharacterStateRead;
    onBeginAdventure: (locationRef: string) => void;
  }

  let { characterId, overworldState, character, onBeginAdventure }: Props =
    $props();

  let localState: OverworldStateRead | null = $state(null);

  // currentRegion: null = world map (show root regions); set = show that region's children.
  let currentRegion: string | null = $state(null);

  // Keep localState in sync when the parent passes new state.
  $effect(() => {
    localState = overworldState;
  });

  /** Direct sub-region children of currentRegion. */
  const subRegions = $derived.by<string[]>(() => {
    if (!localState || currentRegion === null) return [];
    // Build child list from edges where source is currentRegion (prefixed id).
    const children = localState.region_graph.edges
      .filter((e) => e.source === currentRegion)
      .map((e) => e.target);
    return children.filter((id) => {
      const node = localState!.region_graph.nodes.find((n) => n.id === id);
      return node?.kind === "region";
    });
  });

  /**
   * Root regions: region-kind nodes with no incoming edges from another region node.
   * Edges from game:root nodes are excluded — those edges connect the root game node
   * to all top-level regions but are not region-to-region parent links.
   * Multiple disconnected roots are all shown on the world map.
   */
  const rootRegions = $derived.by<string[]>(() => {
    if (!localState) return [];
    // Only consider edges whose source is also a region node as "has parent" edges.
    const regionIds = new Set(
      localState.region_graph.nodes
        .filter((n) => n.kind === "region")
        .map((n) => n.id),
    );
    const hasRegionParent = new Set(
      localState.region_graph.edges
        .filter((e) => regionIds.has(e.source))
        .map((e) => e.target),
    );
    return localState.region_graph.nodes
      .filter((n) => n.kind === "region" && !hasRegionParent.has(n.id))
      .map((n) => n.id);
  });

  /** Label for a node id from the region_graph. */
  function nodeLabel(id: string): string {
    if (!localState) return id;
    return localState.region_graph.nodes.find((n) => n.id === id)?.label ?? id;
  }

  /** Accessible location children of currentRegion. */
  const regionLocations = $derived.by<LocationOptionRead[]>(() => {
    if (!localState || currentRegion === null) return [];
    // currentRegion is a node id like "region:combat"; strip the prefix for comparison
    // with loc.region_ref which is the plain name "combat".
    const regionName = currentRegion.replace(/^region:/, "");
    return localState.accessible_locations.filter(
      (loc) => loc.region_ref === regionName,
    );
  });

  /**
   * Poll for triggered adventures every 5 seconds.
   * When the server has auto-started an adventure, getCurrentPlayState returns
   * a non-null pendingEvent and we transition to adventure mode without interaction.
   */
  const pollInterval = setInterval(async () => {
    try {
      const playState = await getCurrentPlayState(characterId);
      if (playState.pendingEvent !== null) {
        gameSession.init(playState);
      } else if (playState.overworldState) {
        localState = playState.overworldState;
        gameSession.setOverworld(playState.overworldState);
      }
    } catch {
      // Polling errors are silently swallowed — the player can still act manually.
    }
  }, 5_000);

  onDestroy(() => {
    clearInterval(pollInterval);
  });
</script>

{#if localState === null}
  <div class="loading-state">
    <LoadingSpinner />
  </div>
{:else}
  <div class="overworld-layout">
    <div class="main-column">
      <div class="region-nav">
        {#if currentRegion !== null}
          <div class="breadcrumb">
            <button class="back-btn" onclick={() => (currentRegion = null)}>
              &larr; World Map
            </button>
            <span class="crumb-label">{nodeLabel(currentRegion)}</span>
          </div>
        {:else}
          <h2 class="map-heading">World Map</h2>
        {/if}

        {#if currentRegion === null}
          <!-- World map: show all root regions -->
          <div class="region-list">
            {#each rootRegions as regionId}
              <button
                class="region-btn"
                onclick={() => (currentRegion = regionId)}
              >
                {nodeLabel(regionId)}
              </button>
            {/each}
            {#if rootRegions.length === 0}
              <p class="empty-state">No regions available.</p>
            {/if}
          </div>
        {:else}
          <!-- Region view: sub-regions + accessible locations -->
          {#if subRegions.length > 0}
            <div class="sub-region-list">
              <h3 class="section-heading">Areas</h3>
              {#each subRegions as subId}
                <button
                  class="region-btn"
                  onclick={() => (currentRegion = subId)}
                >
                  {nodeLabel(subId)}
                </button>
              {/each}
            </div>
          {/if}

          <div class="location-list">
            <h3 class="section-heading">Locations</h3>
            {#if regionLocations.length === 0}
              <p class="empty-state">No accessible locations here.</p>
            {:else}
              {#each regionLocations as loc}
                <div class="location-row">
                  <div class="loc-info">
                    <span class="loc-name">{loc.display_name}</span>
                  </div>
                  <Button
                    variant="primary"
                    disabled={!loc.adventures_available}
                    onclick={() => onBeginAdventure(loc.ref)}
                  >
                    Begin Adventure
                  </Button>
                </div>
              {/each}
            {/if}
          </div>
        {/if}
      </div>
    </div>
    <div class="sidebar-column">
      <CharacterSidebar {character} />
      <InventoryQuickActions
        instances={character.instances}
        stacks={character.stacks}
      />
    </div>
  </div>
{/if}

<style>
  .loading-state {
    display: flex;
    justify-content: center;
    padding: var(--space-8);
  }

  .overworld-layout {
    display: grid;
    grid-template-columns: 1fr 18rem;
    gap: var(--space-6);
    align-items: start;
  }

  .main-column {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .sidebar-column {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .region-nav {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .map-heading {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .back-btn {
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    color: var(--color-primary);
    font-size: 0.9375rem;
  }

  .back-btn:hover {
    text-decoration: underline;
  }

  .crumb-label {
    font-size: 1.125rem;
    font-weight: 700;
  }

  .section-heading {
    margin: 0 0 var(--space-2);
    font-size: 0.875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .region-list,
  .sub-region-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .region-btn {
    padding: var(--space-3) var(--space-4);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 1rem;
    text-align: left;
    color: var(--color-text);
    transition: border-color 0.15s;
  }

  .region-btn:hover {
    border-color: var(--color-primary);
  }

  .location-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .location-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
  }

  .loc-info {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .loc-name {
    font-size: 0.9375rem;
    font-weight: 500;
  }

  .empty-state {
    margin: 0;
    color: var(--color-text-muted);
    font-size: 0.875rem;
  }

  @media (max-width: 768px) {
    .overworld-layout {
      grid-template-columns: 1fr;
    }
  }
</style>
