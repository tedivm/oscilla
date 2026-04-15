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

  /**
   * Overworld a11y stubs — require an authenticated session and a running dev
   * stack. Skipped until auth helpers are available in the test harness.
   *
   * TODO (MU6+): Implement once session.ts helpers support login flow.
   */

  test.skip("overworld region buttons have accessible labels", async ({
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    page,
  }) => {
    // 1. Log in and navigate to /characters/{id}/play (overworld shows root regions).
    // 2. Assert every region navigation button has visible text (not icon-only).
    // 3. Run axe; expect no violations on the overworld view.
  });

  test.skip("disabled Begin Adventure button uses the disabled HTML attribute", async ({
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    page,
  }) => {
    // 1. Navigate to a location whose adventure pool is empty (all adventures on cooldown).
    // 2. Assert the Begin Adventure button element has the `disabled` attribute set.
    // 3. Confirm axe does not report it as a focus/interaction violation.
  });

  test.skip("back button in overworld has a descriptive accessible label", async ({
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    page,
  }) => {
    // 1. Enter a region in the overworld so the back button is visible.
    // 2. Assert the back button element has accessible text (visible label or aria-label).
    // 3. Run axe; expect no violations.
  });

  test.skip("LoadingSpinner in overworld has role=status or aria-label", async ({
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    page,
  }) => {
    // 1. Navigate to the play page while the overworld is loading.
    // 2. Assert the spinner element has role="status" or an aria-label.
    // 3. Run axe; expect no violations.
  });
});
