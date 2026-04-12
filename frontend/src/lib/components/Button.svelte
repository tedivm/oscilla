<script lang="ts">
  import LoadingSpinner from "./LoadingSpinner.svelte";

  interface Props {
    variant?: "primary" | "secondary" | "danger";
    disabled?: boolean;
    type?: "button" | "submit" | "reset";
    loading?: boolean;
    onclick?: () => void;
    children?: import("svelte").Snippet;
  }

  let {
    variant = "primary",
    disabled = false,
    type = "button",
    loading = false,
    onclick,
    children,
  }: Props = $props();
</script>

<button
  {type}
  class="btn btn-{variant}"
  disabled={disabled || loading}
  aria-busy={loading}
  {onclick}
>
  {#if loading}
    <LoadingSpinner />
  {/if}
  {#if children}
    {@render children()}
  {/if}
</button>

<style>
  .btn {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-md);
    border: 1px solid transparent;
    font-family: var(--font-body);
    font-size: 0.875rem;
    font-weight: 500;
    line-height: 1.5;
    cursor: pointer;
    transition:
      background-color 0.15s,
      opacity 0.15s;
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-primary {
    background-color: var(--color-primary);
    color: #fff;
    border-color: var(--color-primary);
  }

  .btn-primary:not(:disabled):hover {
    background-color: var(--color-primary-hover);
    border-color: var(--color-primary-hover);
  }

  .btn-secondary {
    background-color: transparent;
    color: var(--color-text);
    border-color: var(--color-border);
  }

  .btn-secondary:not(:disabled):hover {
    background-color: var(--color-surface-raised);
  }

  .btn-danger {
    background-color: var(--color-danger);
    color: #fff;
    border-color: var(--color-danger);
  }

  .btn-danger:not(:disabled):hover {
    background-color: var(--color-danger-hover);
    border-color: var(--color-danger-hover);
  }
</style>
