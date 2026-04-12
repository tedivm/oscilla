<script lang="ts">
  import type { CharacterStateRead } from "$lib/api/types.js";

  interface Props {
    character: CharacterStateRead;
  }

  let { character }: Props = $props();

  const locationText = $derived.by(() => {
    if (character.current_location_name && character.current_region_name) {
      return `${character.current_location_name}, ${character.current_region_name}`;
    }
    if (character.current_location_name) {
      return character.current_location_name;
    }
    if (character.current_region_name) {
      return character.current_region_name;
    }
    return null;
  });
</script>

<header class="character-header">
  <h1>{character.name}</h1>
  <div class="meta-grid">
    <span><strong>Game:</strong> {character.game_name}</span>
    <span><strong>Pronouns:</strong> {character.pronoun_set}</span>
    <span><strong>Prestige:</strong> {character.prestige_count}</span>
    {#if locationText}
      <span><strong>Location:</strong> {locationText}</span>
    {/if}
  </div>
</header>

<style>
  .character-header {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background-color: var(--color-surface-raised);
  }

  .character-header h1 {
    margin: 0;
    font-size: 1.5rem;
  }

  .meta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    gap: var(--space-2) var(--space-4);
    font-size: 0.9rem;
    color: var(--color-text-muted);
  }

  .meta-grid strong {
    color: var(--color-text);
  }
</style>
