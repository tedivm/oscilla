<script lang="ts">
  interface Props {
    class?: string;
    children?: import("svelte").Snippet;
  }

  let { class: extraClass = "", children }: Props = $props();
</script>

<div class="card {extraClass}">
  {#if children}
    {@render children()}
  {/if}
</div>

<style>
  .card {
    background-color: var(--color-surface-raised);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-card);
    padding: var(--space-4);
  }
</style>
