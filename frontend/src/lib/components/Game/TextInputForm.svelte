<script lang="ts">
  import type { SSEEvent } from "$lib/stores/gameSession.js";
  import type { TextInputEventData } from "$lib/api/types.js";
  import Button from "$lib/components/Button.svelte";

  interface Props {
    event: SSEEvent;
    onSubmit: (text: string) => void;
  }

  let { event, onSubmit }: Props = $props();

  const eventData = $derived(event.data as TextInputEventData);

  let inputValue = $state("");
  let submitting = $state(false);
  let validationError = $state<string | null>(null);

  function submit(): void {
    const trimmed = inputValue.trim();
    if (!trimmed) {
      validationError = "Please enter some text before submitting.";
      return;
    }
    validationError = null;
    submitting = true;
    onSubmit(trimmed);
  }

  function handleFormSubmit(e: SubmitEvent): void {
    e.preventDefault();
    submit();
  }
</script>

<form class="text-input-form" onsubmit={handleFormSubmit}>
  {#if eventData.prompt}
    <label class="prompt" for="text-input">{eventData.prompt}</label>
  {/if}
  <div class="input-row">
    <input
      id="text-input"
      type="text"
      class="text-input"
      bind:value={inputValue}
      disabled={submitting}
      placeholder="Type your response…"
      autocomplete="off"
    />
    <Button
      type="submit"
      variant="primary"
      disabled={submitting || !inputValue.trim()}
    >
      Submit
    </Button>
  </div>
  {#if validationError}
    <p class="validation-error" role="alert">{validationError}</p>
  {/if}
</form>

<style>
  .text-input-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .prompt {
    font-weight: 500;
  }

  .input-row {
    display: flex;
    gap: var(--space-2);
  }

  .text-input {
    flex: 1;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    font-family: var(--font-body);
    font-size: 0.875rem;
    background: var(--color-surface);
    color: var(--color-text);
  }

  .text-input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .validation-error {
    margin: 0;
    font-size: 0.75rem;
    color: var(--color-danger, #ef4444);
  }
</style>
