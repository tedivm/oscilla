import { writable } from "svelte/store";
import type { Writable } from "svelte/store";

const STORAGE_KEY = "oscilla:theme";

type Theme = "light" | "dark";

function getInitialTheme(): Theme | null {
  // Guard for SSR; no manual override outside browser contexts.
  if (typeof localStorage === "undefined") {
    return null;
  }
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  return null;
}

/** Persistent theme store. Null means "follow system preference". */
export const themeStore: Writable<Theme | null> = writable<Theme | null>(
  getInitialTheme(),
);

function getPreferredTheme(): Theme {
  if (
    typeof window === "undefined" ||
    typeof window.matchMedia !== "function"
  ) {
    return "light";
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

// Apply theme to the document and persist only manual overrides.
themeStore.subscribe((theme) => {
  if (typeof document !== "undefined") {
    if (theme) {
      document.documentElement.dataset.theme = theme;
    } else {
      delete document.documentElement.dataset.theme;
    }
  }
  if (typeof localStorage !== "undefined") {
    if (theme) {
      localStorage.setItem(STORAGE_KEY, theme);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }
});

/** Toggle between light and dark themes. */
export function toggleTheme(): void {
  themeStore.update((current) => {
    const effective = current ?? getPreferredTheme();
    return effective === "light" ? "dark" : "light";
  });
}

/** Clear manual override and return to system-preference mode. */
export function resetTheme(): void {
  themeStore.set(null);
}
