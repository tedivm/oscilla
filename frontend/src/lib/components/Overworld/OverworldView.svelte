<script lang="ts">
  import { onDestroy } from "svelte";
  import type {
    OverworldStateRead,
    CharacterStateRead,
  } from "$lib/api/types.js";
  import { getOverworld } from "$lib/api/characters.js";
  import { getCurrentPlayState } from "$lib/api/play.js";
  import { gameSession } from "$lib/stores/gameSession.js";
  import LoadingSpinner from "$lib/components/LoadingSpinner.svelte";
  import LocationInfo from "./LocationInfo.svelte";
  import AdventureList from "./AdventureList.svelte";
  import NavigationPanel from "./NavigationPanel.svelte";
  import CharacterSidebar from "./CharacterSidebar.svelte";
  import InventoryQuickActions from "./InventoryQuickActions.svelte";

  interface Props {
    characterId: string;
    overworldState: OverworldStateRead | null;
    character: CharacterStateRead;
    onBeginAdventure: (adventureRef: string) => void;
  }

  let { characterId, overworldState, character, onBeginAdventure }: Props =
    $props();

  let localState: OverworldStateRead | null = $state(null);

  // Keep localState in sync when the parent passes new state (e.g., after navigation).
  $effect(() => {
    localState = overworldState;
  });

  function handleNavigated(newState: OverworldStateRead): void {
    localState = newState;
    gameSession.setOverworld(newState);
  }

  /**
   * Poll for triggered adventures every 5 seconds (D8 Mechanism 2).
   * When the server has auto-started an adventure, getCurrentPlayState returns
   * a non-null pendingEvent and we transition to adventure mode without navigation.
   */
  const pollInterval = setInterval(async () => {
    try {
      const playState = await getCurrentPlayState(characterId);
      if (playState.pendingEvent !== null) {
        // Triggered adventure detected — let gameSession.init handle the state transition.
        // The pendingEvent is already set so init will derive mode:"adventure".
        gameSession.init(playState);
      } else if (playState.overworldState) {
        // Refresh overworld state (new adventures may have become available).
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
      <LocationInfo
        locationName={localState.current_location_name}
        regionName={localState.current_region_name}
        description={null}
      />
      <AdventureList
        adventures={localState.available_adventures}
        onSelect={onBeginAdventure}
      />
      <NavigationPanel
        {characterId}
        locations={localState.navigation_options}
        onNavigated={handleNavigated}
      />
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

  @media (max-width: 768px) {
    .overworld-layout {
      grid-template-columns: 1fr;
    }
  }
</style>
