import { expect, test } from "@playwright/test";

test("register flow shows verification message", async ({ page }) => {
  const email = `e2e-${crypto.randomUUID()}@example.com`;
  const password = "securepass123";

  await page.goto("/app/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: /create account/i }).click();

  await expect(
    page.getByText(/check your email to verify your account/i),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /log in here/i })).toBeVisible();
});
