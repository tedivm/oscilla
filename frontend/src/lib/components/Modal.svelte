<script lang="ts">
  import { createEventDispatcher } from "svelte";

  interface Props {
    open: boolean;
    title: string;
    children?: import("svelte").Snippet;
    actions?: import("svelte").Snippet;
  }

  let { open, title, children, actions }: Props = $props();

  const dispatch = createEventDispatcher<{ close: void }>();

  function close(): void {
    dispatch("close");
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === "Escape") {
      close();
    }
  }

  function onBackdropClick(event: MouseEvent): void {
    // Close only when clicking directly on the backdrop (not on dialog content).
    if ((event.target as HTMLElement).classList.contains("modal-backdrop")) {
      close();
    }
  }
</script>

<svelte:window onkeydown={onKeydown} />

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="modal-backdrop" onclick={onBackdropClick}>
    <dialog {open} aria-labelledby="modal-title" class="modal-dialog">
      <header class="modal-header">
        <h2 id="modal-title" class="modal-title">{title}</h2>
        <button
          type="button"
          class="modal-close"
          aria-label="Close dialog"
          onclick={close}
        >
          ✕
        </button>
      </header>
      <div class="modal-body">
        {#if children}
          {@render children()}
        {/if}
      </div>
      {#if actions}
        <div class="modal-actions">
          {@render actions()}
        </div>
      {/if}
    </dialog>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background-color: rgb(0 0 0 / 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }

  .modal-dialog {
    background-color: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-card);
    min-width: 20rem;
    max-width: 40rem;
    width: 90%;
    padding: 0;
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-4) var(--space-6);
    border-bottom: 1px solid var(--color-border);
  }

  .modal-title {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--color-text);
  }

  .modal-close {
    background: none;
    border: none;
    color: var(--color-text-muted);
    cursor: pointer;
    font-size: 1rem;
    padding: var(--space-1);
    line-height: 1;
  }

  .modal-close:hover {
    color: var(--color-text);
  }

  .modal-body {
    padding: var(--space-4) var(--space-6);
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-2);
    padding: var(--space-4) var(--space-6);
    border-top: 1px solid var(--color-border);
  }
</style>
