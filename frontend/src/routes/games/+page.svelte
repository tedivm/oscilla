<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { base } from "$app/paths";
  import { listGames } from "$lib/api/games.js";
  import {
    Button,
    Card,
    ErrorBanner,
    LoadingSpinner,
  } from "$lib/components/index.js";
  import type { GameRead } from "$lib/api/types.js";

  let games = $state<GameRead[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      games = await listGames();
    } catch (err) {
      error = err instanceof Error ? err.message : "Failed to load games.";
    } finally {
      loading = false;
    }
  });
</script>

<div class="games-page">
  <h1>Choose a Game</h1>

  {#if loading}
    <div class="loading-state"><LoadingSpinner /></div>
  {:else if error}
    <ErrorBanner message={error} />
  {:else if games.length === 0}
    <p class="empty-state">No games are available at this time.</p>
  {:else}
    <div class="games-grid">
      {#each games as game (game.name)}
        <Card>
          <div class="game-card-content">
            <h2 class="game-title">{game.display_name}</h2>
            {#if game.description}
              <p class="game-description">{game.description}</p>
            {/if}
            <Button
              variant="primary"
              onclick={() =>
                goto(
                  `${base}/characters?game=${encodeURIComponent(game.name)}`,
                )}
            >
              Select
            </Button>
          </div>
        </Card>
      {/each}
    </div>
  {/if}
</div>

<style>
  .games-page h1 {
    margin-top: 0;
  }

  .games-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr));
    gap: var(--space-4);
    margin-top: var(--space-4);
  }

  .game-card-content {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .game-title {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
  }

  .game-description {
    margin: 0;
    color: var(--color-text-muted);
    font-size: 0.875rem;
    line-height: 1.6;
  }

  .loading-state {
    display: flex;
    justify-content: center;
    padding: var(--space-8);
  }

  .empty-state {
    color: var(--color-text-muted);
  }
</style>
