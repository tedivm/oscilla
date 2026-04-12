<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { base } from "$app/paths";
  import { page } from "$app/stores";
  import { createCharacter } from "$lib/api/characters.js";
  import { getGame, listGames } from "$lib/api/games.js";
  import {
    Button,
    Card,
    ErrorBanner,
    LoadingSpinner,
  } from "$lib/components/index.js";
  import type { GameRead } from "$lib/api/types.js";

  let gameName = $derived($page.url.searchParams.get("game"));

  let loading = $state(true);
  let creating = $state(false);
  let error = $state<string | null>(null);
  let selectedGame = $state<GameRead | null>(null);
  let games = $state<GameRead[]>([]);

  onMount(async () => {
    try {
      if (gameName) {
        selectedGame = await getGame(gameName);
      } else {
        games = await listGames();
      }
    } catch (err) {
      error = err instanceof Error ? err.message : "Failed to load games.";
    } finally {
      loading = false;
    }
  });

  async function handleCreate(targetGame: string): Promise<void> {
    creating = true;
    error = null;
    try {
      const created = await createCharacter(targetGame);
      await goto(`${base}/characters/${created.id}`);
    } catch (err) {
      error =
        err instanceof Error ? err.message : "Failed to create character.";
    } finally {
      creating = false;
    }
  }
</script>

<div class="new-character-page">
  <h1>Create Character</h1>

  {#if loading}
    <div class="loading-state"><LoadingSpinner /></div>
  {:else}
    <ErrorBanner message={error} />

    {#if selectedGame}
      <Card>
        <div class="single-game">
          <h2>{selectedGame.display_name}</h2>
          {#if selectedGame.description}
            <p>{selectedGame.description}</p>
          {/if}
          <Button
            loading={creating}
            disabled={creating}
            onclick={() => {
              if (selectedGame) {
                handleCreate(selectedGame.name);
              }
            }}
          >
            Create Character
          </Button>
        </div>
      </Card>
    {:else if games.length === 0}
      <p class="empty-state">No games available for character creation.</p>
    {:else}
      <div class="games-grid">
        {#each games as game (game.name)}
          <Card>
            <div class="game-option">
              <h2>{game.display_name}</h2>
              {#if game.description}
                <p>{game.description}</p>
              {/if}
              <Button
                loading={creating}
                disabled={creating}
                onclick={() => handleCreate(game.name)}
              >
                Create Character
              </Button>
            </div>
          </Card>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<style>
  .new-character-page h1 {
    margin-top: 0;
  }

  .loading-state {
    display: flex;
    justify-content: center;
    padding: var(--space-8);
  }

  .single-game,
  .game-option {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .single-game h2,
  .game-option h2 {
    margin: 0;
  }

  .single-game p,
  .game-option p {
    margin: 0;
    color: var(--color-text-muted);
  }

  .games-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
    gap: var(--space-4);
  }

  .empty-state {
    color: var(--color-text-muted);
  }
</style>
