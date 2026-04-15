<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { base } from "$app/paths";
  import { page } from "$app/stores";
  import { listCharacters } from "$lib/api/characters.js";
  import {
    Button,
    Card,
    ErrorBanner,
    LoadingSpinner,
  } from "$lib/components/index.js";
  import type { CharacterSummaryRead } from "$lib/api/types.js";

  let characters = $state<CharacterSummaryRead[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Read the ?game= query param reactively
  let gameName = $derived($page.url.searchParams.get("game") ?? undefined);

  onMount(async () => {
    try {
      characters = await listCharacters(gameName);
    } catch (err) {
      error = err instanceof Error ? err.message : "Failed to load characters.";
    } finally {
      loading = false;
    }
  });

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString();
  }
</script>

<div class="characters-page">
  <div class="characters-header">
    <h1>{gameName ? `Characters — ${gameName}` : "Your Characters"}</h1>
    <Button
      variant="primary"
      onclick={() =>
        goto(
          gameName
            ? `${base}/characters/new?game=${encodeURIComponent(gameName)}`
            : `${base}/characters/new`,
        )}
    >
      New Character
    </Button>
  </div>

  {#if loading}
    <div class="loading-state"><LoadingSpinner /></div>
  {:else if error}
    <ErrorBanner message={error} />
  {:else if characters.length === 0}
    <p class="empty-state">
      No characters yet.
      <a
        href={gameName
          ? `${base}/characters/new?game=${encodeURIComponent(gameName)}`
          : `${base}/characters/new`}
      >
        Create your first character.
      </a>
    </p>
  {:else}
    <div class="characters-grid">
      {#each characters as character (character.id)}
        <Card>
          <div class="character-card-content">
            <div class="character-info">
              <h2 class="character-name">{character.name}</h2>
              <span class="character-meta">{character.game_name}</span>
              {#if character.prestige_count > 0}
                <span class="character-prestige"
                  >Prestige {character.prestige_count}</span
                >
              {/if}
              <span class="character-date"
                >Created {formatDate(character.created_at)}</span
              >
            </div>
            <Button
              variant="primary"
              onclick={() => goto(`${base}/characters/${character.id}/play`)}
            >
              Play
            </Button>
            <Button
              variant="secondary"
              onclick={() => goto(`${base}/characters/${character.id}`)}
            >
              View
            </Button>
          </div>
        </Card>
      {/each}
    </div>
  {/if}
</div>

<style>
  .characters-page h1 {
    margin-top: 0;
  }

  .characters-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }

  .characters-header h1 {
    margin-bottom: 0;
  }

  .characters-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
    gap: var(--space-4);
  }

  .character-card-content {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .character-info {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .character-name {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
  }

  .character-meta,
  .character-prestige,
  .character-date {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  .character-prestige {
    color: var(--color-primary);
  }

  .loading-state {
    display: flex;
    justify-content: center;
    padding: var(--space-8);
  }

  .empty-state {
    color: var(--color-text-muted);
  }

  .empty-state a {
    color: var(--color-primary);
  }
</style>
