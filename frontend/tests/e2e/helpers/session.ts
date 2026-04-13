import { expect, type Page } from "@playwright/test";

export type E2ECredentials = {
  email: string;
  password: string;
};

export function makeCredentials(): E2ECredentials {
  return {
    email: `e2e-${crypto.randomUUID()}@example.com`,
    password: "securepass123",
  };
}

export async function registerUser(
  page: Page,
  credentials: E2ECredentials,
): Promise<void> {
  await page.goto("/app/register");
  await page.getByLabel("Email").fill(credentials.email);
  await page.getByLabel("Password", { exact: true }).fill(credentials.password);
  await page.getByLabel("Confirm Password").fill(credentials.password);
  await page.getByRole("button", { name: /create account/i }).click();

  await expect(
    page.getByText(/check your email to verify your account/i),
  ).toBeVisible();
}

export async function loginUser(
  page: Page,
  credentials: E2ECredentials,
): Promise<void> {
  await page.goto("/app/login");
  await page.getByLabel("Email").fill(credentials.email);
  await page.getByLabel("Password", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: /log in/i }).click();

  await expect(page).toHaveURL(/\/app\/games/);
}
