import source from "./+page.svelte?raw";
import { describe, expect, it } from "vitest";

describe("character sheet source contract", () => {
  it("includes loading state with LoadingSpinner", () => {
    expect(source).toContain("{#if loading}");
    expect(source).toContain("<LoadingSpinner />");
  });

  it("renders CharacterHeader on successful load", () => {
    expect(source).toContain("<CharacterHeader {character} />");
  });

  it("gates SkillsPanel on has_skills", () => {
    expect(source).toContain("{#if game.features.has_skills}");
    expect(source).toContain("<SkillsPanel skills={character.skills} />");
  });

  it("renders QuestsPanel when has_quests is true", () => {
    expect(source).toContain("{#if game.features.has_quests}");
    expect(source).toContain("<QuestsPanel");
  });

  it("handles ApiError 404 with not-found state", () => {
    expect(source).toContain("err instanceof ApiError && err.status === 404");
    expect(source).toContain("notFound = true");
  });
});
