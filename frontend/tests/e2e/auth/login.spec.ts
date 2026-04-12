import { expect, test } from "@playwright/test";
import {
  loginUser,
  makeCredentials,
  registerUser,
} from "../helpers/session.js";

test("login and logout flow", async ({ page }) => {
  const credentials = makeCredentials();
  await registerUser(page, credentials);
  await loginUser(page, credentials);

  await expect(page).toHaveURL(/\/app\/games/);

  const logout = page.getByRole("button", { name: /logout/i });
  if (await logout.count()) {
    await logout.click();
    await expect(page).toHaveURL(/\/app\/login/);
  }
});
