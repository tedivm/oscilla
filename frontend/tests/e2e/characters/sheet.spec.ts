import { expect, test } from "@playwright/test";
import {
  loginUser,
  makeCredentials,
  registerUser,
} from "../helpers/session.js";

test("character sheet renders header and at least one panel", async ({
  page,
}) => {
  const credentials = makeCredentials();
  await registerUser(page, credentials);
  await loginUser(page, credentials);
  await page.getByRole("link", { name: /^characters$/i }).click();

  const firstViewButton = page.getByRole("button", { name: /view/i }).first();
  if (await firstViewButton.isVisible()) {
    await firstViewButton.click();
  } else {
    await page.getByRole("button", { name: /new character/i }).click();
    const createButton = page.getByRole("button", {
      name: /create character/i,
    });
    await expect(createButton.first()).toBeVisible();
    await createButton.first().click();
  }

  await expect(page).toHaveURL(/\/app\/characters\//);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(
    page
      .getByRole("heading", { name: /stats|inventory|quests|buffs|skills/i })
      .first(),
  ).toBeVisible();
});
