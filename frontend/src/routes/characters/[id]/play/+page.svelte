<script lang="ts">
  import { onDestroy } from "svelte";
  import { goto } from "$app/navigation";
  import { base } from "$app/paths";
  import { gameSession } from "$lib/stores/gameSession.js";
  import { apiFetch, ApiError } from "$lib/api/client.js";
  import type { PendingStateRead } from "$lib/api/types.js";
  import type { AdvanceDecision } from "$lib/api/play.js";
  import NarrativeLog from "$lib/components/Game/NarrativeLog.svelte";
  import ChoiceMenu from "$lib/components/Game/ChoiceMenu.svelte";
  import AckPrompt from "$lib/components/Game/AckPrompt.svelte";
  import CombatHUD from "$lib/components/Game/CombatHUD.svelte";
  import TextInputForm from "$lib/components/Game/TextInputForm.svelte";
  import SkillMenu from "$lib/components/Game/SkillMenu.svelte";
  import AdventureCompleteScreen from "$lib/components/Game/AdventureCompleteScreen.svelte";
  import SessionConflictModal from "$lib/components/Game/SessionConflictModal.svelte";
  import OverworldView from "$lib/components/Overworld/OverworldView.svelte";
  import { LoadingSpinner } from "$lib/components/index.js";
  import type { PageData } from "./$types.js";

  let { data }: { data: PageData } = $props();

  // Initialize store from crash-recovery data before first render (D6).
  // Destructure first so Svelte 5 doesn't warn about capturing a reactive prop reference.
  const { character, playState } = data;
  gameSession.init(playState);

  const characterId = $derived(character.id);

  let showConflictModal = $state(false);
  let conflictAcquiredAt = $state<string>("");

  // ── 409 handling ──────────────────────────────────────────────────────────

  function handle409(err: unknown): boolean {
    if (err instanceof ApiError && err.status === 409) {
      // Extract acquired_at from the 409 body (SessionConflictRead).
      const body = err.body as Record<string, unknown> | string | null;
      if (body && typeof body === "object" && "acquired_at" in body) {
        conflictAcquiredAt =
          (body as Record<string, string>)["acquired_at"] ?? "";
      }
      showConflictModal = true;
      return true;
    }
    return false;
  }

  // ── Decision handlers ─────────────────────────────────────────────────────

  async function handleChoice(choice: number): Promise<void> {
    try {
      await gameSession.advance(character.id, { choice });
    } catch (err) {
      if (!handle409(err)) throw err;
    }
  }

  async function handleAck(): Promise<void> {
    try {
      await gameSession.advance(character.id, { ack: true });
    } catch (err) {
      if (!handle409(err)) throw err;
    }
  }

  async function handleTextInput(text: string): Promise<void> {
    try {
      await gameSession.advance(character.id, { text_input: text });
    } catch (err) {
      if (!handle409(err)) throw err;
    }
  }

  async function handleSkillChoice(skillIndex: number): Promise<void> {
    try {
      await gameSession.advance(character.id, { skill_choice: skillIndex });
    } catch (err) {
      if (!handle409(err)) throw err;
    }
  }

  async function handleAdventureComplete(): Promise<void> {
    gameSession.close();
    await goto(`${base}/characters/${character.id}`);
  }

  // ── Session takeover ──────────────────────────────────────────────────────

  async function handleTakeover(): Promise<void> {
    try {
      // Acquire the session lock.
      const result = await apiFetch<PendingStateRead>(
        `/characters/${encodeURIComponent(character.id)}/play/takeover`,
        { method: "POST" },
      );
      showConflictModal = false;
      // Re-initialize the store from the takeover result, then resume the stream.
      // The pending_event from takeover tells us whether to advance or wait.
      if (result.pending_event) {
        // There is an outstanding decision awaiting the player — restore state.
        const { getCurrentPlayState } = await import("$lib/api/play.js");
        const playState = await getCurrentPlayState(character.id);
        gameSession.init(playState);
      } else {
        // Session taken over but no active decision — go to overworld.
        const { getOverworld } = await import("$lib/api/characters.js");
        const overworldState = await getOverworld(character.id);
        gameSession.setOverworld(overworldState);
      }
    } catch (err) {
      // Takeover failed — leave modal open, surface error in modal (future: show inline error).
      console.error("Takeover failed:", err);
    }
  }

  onDestroy(() => {
    // D7: ensure stream is cancelled if the component is destroyed before adventure ends.
    gameSession.close();
  });
</script>

<div class="play-page">
  {#if $gameSession.mode === "overworld"}
    <OverworldView
      {characterId}
      overworldState={$gameSession.overworldState}
      {character}
      onBeginAdventure={(ref) => gameSession.begin(character.id, ref)}
    />
  {:else}
    <div class="adventure-layout">
      <NarrativeLog entries={$gameSession.narrativeLog} />
      <div class="decision-area">
        {#if $gameSession.pendingEvent?.type === "choice"}
          <ChoiceMenu
            event={$gameSession.pendingEvent}
            onSelect={handleChoice}
          />
        {:else if $gameSession.pendingEvent?.type === "ack_required"}
          <AckPrompt onAck={handleAck} />
        {:else if $gameSession.pendingEvent?.type === "combat_state"}
          <CombatHUD event={$gameSession.pendingEvent} onAck={handleAck} />
        {:else if $gameSession.pendingEvent?.type === "text_input"}
          <TextInputForm
            event={$gameSession.pendingEvent}
            onSubmit={handleTextInput}
          />
        {:else if $gameSession.pendingEvent?.type === "skill_menu"}
          <SkillMenu
            event={$gameSession.pendingEvent}
            onSelect={handleSkillChoice}
          />
        {:else if $gameSession.mode === "loading"}
          <LoadingSpinner />
        {:else if $gameSession.mode === "complete"}
          <AdventureCompleteScreen
            event={$gameSession.completeEvent}
            onContinue={handleAdventureComplete}
          />
        {/if}
      </div>
    </div>
  {/if}

  {#if showConflictModal}
    <SessionConflictModal
      acquiredAt={conflictAcquiredAt}
      onTakeover={handleTakeover}
      onCancel={() => {
        showConflictModal = false;
      }}
    />
  {/if}
</div>

<style>
  .play-page {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 4rem); /* subtract NavBar height */
  }

  .adventure-layout {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    gap: var(--space-4);
  }

  .decision-area {
    padding: var(--space-4);
    border-top: 1px solid var(--color-border);
  }
</style>
