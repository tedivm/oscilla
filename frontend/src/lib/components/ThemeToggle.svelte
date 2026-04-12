<script lang="ts">
  import { themeStore, toggleTheme } from "$lib/stores/theme.js";

  function nextThemeLabel(theme: "light" | "dark" | null): "Light" | "Dark" {
    if (theme === "dark") {
      return "Light";
    }
    if (theme === "light") {
      return "Dark";
    }
    const prefersDark =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches;
    return prefersDark ? "Light" : "Dark";
  }
</script>

<button
  type="button"
  class="theme-toggle"
  aria-label="Toggle theme"
  onclick={toggleTheme}
>
  {nextThemeLabel($themeStore)}
</button>

<style>
  .theme-toggle {
    background: none;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    color: var(--color-text);
    cursor: pointer;
    font-family: var(--font-body);
    font-size: 0.875rem;
    padding: var(--space-1) var(--space-2);
    transition: background-color 0.15s;
  }

  .theme-toggle:hover {
    background-color: var(--color-surface-raised);
  }
</style>
