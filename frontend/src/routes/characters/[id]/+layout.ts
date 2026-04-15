import { redirect } from "@sveltejs/kit";
import { apiFetch } from "$lib/api/client.js";
import type { PendingStateRead } from "$lib/api/types.js";
import type { LayoutLoad } from "./$types.js";
import { base } from "$app/paths";

/**
 * D8 forced-redirect guard.
 *
 * Runs before any character-scoped page renders. When the character already has
 * an active adventure, the player is redirected to the play screen regardless of
 * which character sub-route they navigated to.
 *
 * This catches:
 * - Navigating directly to the character sheet while an adventure is in progress.
 * - Returning to the app after a session gap with a pending adventure.
 * - A triggered adventure racing with a navigation (e.g., post-creation tutorial).
 *
 * The guard is skipped when we are already on the play route to prevent an
 * infinite redirect loop.
 */
export const load: LayoutLoad = async ({ params, url }) => {
  // Avoid redirecting when already on the play route.
  if (url.pathname.endsWith("/play")) {
    return {};
  }

  const current = await apiFetch<PendingStateRead>(
    `/api/characters/${encodeURIComponent(params.id)}/play/current`,
  );

  if (current.pending_event !== null) {
    throw redirect(307, `${base}/characters/${params.id}/play`);
  }

  return {};
};
