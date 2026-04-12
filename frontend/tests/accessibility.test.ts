import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

test.describe("accessibility", () => {
  async function expectReadyForA11y(
    page: Page,
    path: string,
    pageNamePattern: RegExp,
  ): Promise<void> {
    await page.goto(path);
    await expect(page.getByRole("main")).toBeVisible();
    await expect(
      page.getByRole("heading", { level: 1, name: pageNamePattern }),
    ).toBeVisible();
  }

  test("login page has no automatically detectable WCAG 2.1 AA violations", async ({
    page,
  }) => {
    await expectReadyForA11y(page, "/app/login", /log in/i);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });

  test("register page has no automatically detectable WCAG 2.1 AA violations", async ({
    page,
  }) => {
    await expectReadyForA11y(page, "/app/register", /create account/i);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });

  test("landing page has no automatically detectable WCAG 2.1 AA violations", async ({
    page,
  }) => {
    await expectReadyForA11y(page, "/app/", /oscilla/i);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
});
