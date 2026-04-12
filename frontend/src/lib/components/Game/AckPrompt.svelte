<script lang="ts">
  import Button from "$lib/components/Button.svelte";

  interface Props {
    onAck: () => void;
  }

  let { onAck }: Props = $props();

  let submitting = $state(false);

  function ack(): void {
    if (submitting) return;
    submitting = true;
    onAck();
  }

  function handleKey(e: KeyboardEvent): void {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      ack();
    }
  }
</script>

<svelte:window onkeydown={handleKey} />

<div class="ack-prompt">
  <Button variant="primary" disabled={submitting} onclick={ack}>
    Press Enter to continue
  </Button>
</div>

<style>
  .ack-prompt {
    display: flex;
    justify-content: flex-start;
  }
</style>
