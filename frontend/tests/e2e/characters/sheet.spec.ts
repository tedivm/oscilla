import { expect, test } from "@playwright/test";
import {
  loginUser,
  makeCredentials,
  registerUser,
} from "../helpers/session.js";

/**
 * E2E stubs for the active-adventure guard on the character sheet.
 *
 * The guard applies only to PATCH /characters/{id} (rename/update). DELETE is
 * intentionally ungarded — players may always delete a character they own.
 *
 * These tests require a character that has an active web session lock
 * (i.e., an adventure in progress that holds session_token). That state can
 * only be established by driving a full adventure through the game engine.
 * They are skipped pending the infrastructure introduced in the game-loop
 * play screen milestone.
 *
 * TODO (MU7+): Implement each scenario below against a running dev stack
 * that can start an adventure and hold the session lock open.
 */

test.skip("active_adventure_guard_rename: rename during active adventure redirects to play screen", async ({
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  page,
}) => {
  // 1. Log in, navigate to a character that has a live adventure session lock.
  // 2. Navigate to the character sheet (/characters/{id}).
  // 3. Trigger the rename action (open rename input/dialog, submit a new name).
  // 4. Expect the rename to not take effect (mutation is blocked by the 409 guard).
  // 5. Expect the page to navigate to /characters/{id}/play.
  // 6. Verify the play screen is visible and no error toast/message is shown.
});

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
