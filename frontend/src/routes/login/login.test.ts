import source from "./+page.svelte?raw";
import { describe, expect, it } from "vitest";

describe("login page source contract", () => {
  it("renders email, password, and submit controls", () => {
    expect(source).toContain('label for="email"');
    expect(source).toContain('label for="password"');
    expect(source).toContain("Log In");
  });

  it("submits credentials through authStore.login", () => {
    expect(source).toContain("await authStore.login(email, password);");
  });

  it("uses loading state to disable submit and show spinner", () => {
    expect(source).toContain("loading={$authStore.loading}");
    expect(source).toContain("disabled={$authStore.loading}");
    expect(source).toContain("<LoadingSpinner />");
  });

  it("renders ErrorBanner from authStore.error", () => {
    expect(source).toContain("<ErrorBanner message={$authStore.error}");
  });
});
