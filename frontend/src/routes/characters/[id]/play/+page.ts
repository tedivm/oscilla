import type { PageLoad } from "./$types.js";
import { getCharacter } from "$lib/api/characters.js";
import { getCurrentPlayState } from "$lib/api/play.js";

// ssr: false is inherited from root +layout.ts — this runs browser-only.
//
// Neither getCharacter nor getCurrentPlayState accepts a SvelteKit fetch param:
// they call apiFetch directly, which reads get(authStore) at call time.
// This is correct for a CSR-only app — the auth store is populated before any
// page load function executes (SvelteKit runs load lazily after +layout.svelte
// onMount has initialized the store).
export const load: PageLoad = async ({
  params,
}): Promise<ReturnType<PageLoad>> => {
  const [character, playState] = await Promise.all([
    getCharacter(params.id),
    getCurrentPlayState(params.id),
  ]);
  return { character, playState };
};
