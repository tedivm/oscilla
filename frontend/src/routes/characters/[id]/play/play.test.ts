import source from "./+page.svelte?raw";
import { describe, expect, it } from "vitest";

describe("play page source contract", () => {
  it("imports gameSession store", () => {
    expect(source).toContain('from "$lib/stores/gameSession.js"');
    expect(source).toContain("gameSession");
  });

  it("calls gameSession.init with playState on startup", () => {
    expect(source).toContain("gameSession.init(playState)");
  });

  it("handleChoice calls gameSession.advance with choice decision", () => {
    expect(source).toContain("gameSession.advance(");
    expect(source).toContain("{ choice }");
  });

  it("handleAck calls gameSession.advance with ack decision", () => {
    expect(source).toContain("{ ack: true }");
  });

  it("handleTextInput calls gameSession.advance with text_input", () => {
    expect(source).toContain("{ text_input: text }");
  });

  it("handleSkillChoice calls gameSession.advance with skill_choice", () => {
    expect(source).toContain("{ skill_choice: skillIndex }");
  });

  it("closes the session in onDestroy", () => {
    expect(source).toContain("onDestroy(");
    expect(source).toContain("gameSession.close()");
  });

  it("renders OverworldView when mode is overworld", () => {
    expect(source).toContain('mode === "overworld"');
    expect(source).toContain("<OverworldView");
  });

  it("renders NarrativeLog with entries from the store", () => {
    expect(source).toContain("<NarrativeLog");
    expect(source).toContain("$gameSession.narrativeLog");
  });

  it("renders ChoiceMenu for choice events", () => {
    expect(source).toContain("<ChoiceMenu");
    expect(source).toContain('"choice"');
  });

  it("renders AckPrompt for ack_required events", () => {
    expect(source).toContain("<AckPrompt");
    expect(source).toContain('"ack_required"');
  });

  it("renders CombatHUD for combat_state events", () => {
    expect(source).toContain("<CombatHUD");
    expect(source).toContain('"combat_state"');
  });

  it("renders TextInputForm for text_input events", () => {
    expect(source).toContain("<TextInputForm");
    expect(source).toContain('"text_input"');
  });

  it("renders SkillMenu for skill_menu events", () => {
    expect(source).toContain("<SkillMenu");
    expect(source).toContain('"skill_menu"');
  });

  it("renders AdventureCompleteScreen when mode is complete", () => {
    expect(source).toContain("<AdventureCompleteScreen");
    expect(source).toContain('"complete"');
  });

  it("renders SessionConflictModal overlay when showConflictModal is true", () => {
    expect(source).toContain("<SessionConflictModal");
    expect(source).toContain("showConflictModal");
  });

  it("handles 409 errors from gameSession.advance", () => {
    expect(source).toContain("handle409(err)");
    expect(source).toContain("err.status === 409");
  });

  it("takeover POSTs to /play/takeover endpoint", () => {
    expect(source).toContain("/play/takeover");
    expect(source).toContain('method: "POST"');
  });
});
