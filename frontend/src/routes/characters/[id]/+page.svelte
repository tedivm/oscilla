<script lang="ts">
  import { goto } from "$app/navigation";
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { base } from "$app/paths";
  import { getCharacter } from "$lib/api/characters.js";
  import { ApiError } from "$lib/api/client.js";
  import { getGame } from "$lib/api/games.js";
  import type { CharacterStateRead, GameRead } from "$lib/api/types.js";
  import {
    Button,
    CharacterHeader,
    ErrorBanner,
    LoadingSpinner,
  } from "$lib/components/index.js";
  import ArchetypesPanel from "$lib/components/panels/ArchetypesPanel.svelte";
  import BuffsPanel from "$lib/components/panels/BuffsPanel.svelte";
  import EquipmentPanel from "$lib/components/panels/EquipmentPanel.svelte";
  import InventoryPanel from "$lib/components/panels/InventoryPanel.svelte";
  import MilestonesPanel from "$lib/components/panels/MilestonesPanel.svelte";
  import QuestsPanel from "$lib/components/panels/QuestsPanel.svelte";
  import SkillsPanel from "$lib/components/panels/SkillsPanel.svelte";
  import StatsPanel from "$lib/components/panels/StatsPanel.svelte";

  let id = $derived($page.params.id ?? "");

  let loading = $state(true);
  let notFound = $state(false);
  let error = $state<string | null>(null);
  let character = $state<CharacterStateRead | null>(null);
  let game = $state<GameRead | null>(null);

  onMount(async () => {
    try {
      const foundCharacter = await getCharacter(id);
      character = foundCharacter;
      game = await getGame(foundCharacter.game_name);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        notFound = true;
      } else {
        error =
          err instanceof Error ? err.message : "Failed to load character.";
      }
    } finally {
      loading = false;
    }
  });
</script>

<div class="character-sheet">
  <div class="sheet-nav">
    <a class="back-link" href={`${base}/characters`}>Back to characters</a>
    {#if character}
      <Button
        variant="primary"
        onclick={() => goto(`${base}/characters/${id}/play`)}
      >
        Play
      </Button>
    {/if}
  </div>

  {#if loading}
    <div class="loading-state"><LoadingSpinner /></div>
  {:else if notFound}
    <section class="not-found">
      <h1>Character Not Found</h1>
      <ErrorBanner
        message="The requested character does not exist or is unavailable."
      />
      <p>The requested character does not exist or is unavailable.</p>
    </section>
  {:else if error}
    <ErrorBanner message={error} />
  {:else if character && game}
    <div class="sheet-grid">
      <CharacterHeader {character} />
      <StatsPanel stats={character.stats} />
      <InventoryPanel
        stacks={character.stacks}
        instances={character.instances}
      />

      <EquipmentPanel equipment={character.equipment} />

      {#if game.features.has_skills}
        <SkillsPanel skills={character.skills} />
      {/if}

      <BuffsPanel active_buffs={character.active_buffs} />

      {#if game.features.has_quests}
        <QuestsPanel
          active_quests={character.active_quests}
          completed_quests={character.completed_quests}
          failed_quests={character.failed_quests}
        />
      {/if}

      <MilestonesPanel milestones={character.milestones} />

      {#if game.features.has_archetypes}
        <ArchetypesPanel archetypes={character.archetypes} />
      {/if}
    </div>
  {/if}
</div>

<style>
  .character-sheet {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .sheet-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .back-link {
    align-self: flex-start;
    color: var(--color-primary);
    text-decoration: none;
  }

  .sheet-grid {
    display: grid;
    gap: var(--space-4);
  }

  .loading-state {
    display: flex;
    justify-content: center;
    padding: var(--space-8);
  }

  .not-found {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    background-color: var(--color-surface);
  }

  .not-found h1 {
    margin-top: 0;
  }
</style>
