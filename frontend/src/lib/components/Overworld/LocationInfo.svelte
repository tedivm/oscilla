<script lang="ts">
  interface Props {
    locationName: string | null;
    regionName: string | null;
    description: string | null;
  }

  let { locationName, regionName, description }: Props = $props();
</script>

<div class="location-info">
  <h2 class="location-name">{locationName ?? "Unknown location"}</h2>
  {#if regionName}
    <p class="region-name">{regionName}</p>
  {/if}
  {#if description}
    <p class="description">{description}</p>
  {/if}
</div>

<style>
  .location-info {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .location-name {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
  }

  .region-name {
    margin: 0;
    font-size: 0.875rem;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .description {
    margin: 0;
    font-size: 0.9375rem;
    line-height: 1.6;
  }
</style>
