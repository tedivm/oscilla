import { beforeEach, describe, expect, it, vi } from "vitest";
import { get } from "svelte/store";

describe("themeStore", () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
    delete document.documentElement.dataset.theme;
  });

  it("initializes to null when localStorage is empty", async () => {
    const { themeStore } = await import("./theme.js");
    expect(get(themeStore)).toBeNull();
  });

  it("initializes from localStorage value", async () => {
    localStorage.setItem("oscilla:theme", "dark");
    const { themeStore } = await import("./theme.js");
    expect(get(themeStore)).toBe("dark");
  });

  it("toggleTheme switches light to dark and back", async () => {
    const { themeStore, toggleTheme } = await import("./theme.js");

    expect(get(themeStore)).toBeNull();
    toggleTheme();
    const firstToggle = get(themeStore);
    expect(firstToggle === "light" || firstToggle === "dark").toBe(true);
    toggleTheme();
    expect(get(themeStore)).toBe(firstToggle === "light" ? "dark" : "light");
  });

  it("toggleTheme writes to localStorage", async () => {
    const { themeStore, toggleTheme } = await import("./theme.js");

    toggleTheme();
    expect(localStorage.getItem("oscilla:theme")).toBe(get(themeStore));
  });

  it("toggleTheme updates document dataset", async () => {
    const { themeStore, toggleTheme } = await import("./theme.js");

    toggleTheme();
    expect(document.documentElement.dataset.theme).toBe(
      get(themeStore) ?? undefined,
    );
  });

  it("resetTheme clears localStorage and data-theme override", async () => {
    const { themeStore, toggleTheme, resetTheme } = await import("./theme.js");

    toggleTheme();
    expect(localStorage.getItem("oscilla:theme")).toBe(get(themeStore));
    expect(document.documentElement.dataset.theme).toBe(
      get(themeStore) ?? undefined,
    );

    resetTheme();

    expect(localStorage.getItem("oscilla:theme")).toBeNull();
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });
});
