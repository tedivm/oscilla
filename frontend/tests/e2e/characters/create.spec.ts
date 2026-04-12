import { expect, test } from "@playwright/test";
import {
  loginUser,
  makeCredentials,
  registerUser,
} from "../helpers/session.js";

test("character creation end-to-end", async ({ page }) => {
  const credentials = makeCredentials();
  await registerUser(page, credentials);
  await loginUser(page, credentials);
  await page.getByRole("link", { name: /^characters$/i }).click();

  await page.getByRole("button", { name: /new character/i }).click();

  const createButton = page.getByRole("button", { name: /create character/i });
  await expect(createButton.first()).toBeVisible();
  await createButton.first().click();

  await expect(page).toHaveURL(/\/app\/characters\//);
});
