<div class="spinner" role="status" aria-label="Loading"></div>

<style>
  .spinner {
    display: inline-block;
    width: var(--space-4);
    height: var(--space-4);
    border: 2px solid color-mix(in srgb, var(--color-primary) 30%, transparent);
    border-top-color: var(--color-primary);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    flex-shrink: 0;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
