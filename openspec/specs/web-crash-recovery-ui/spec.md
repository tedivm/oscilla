# Web Crash Recovery UI

## Purpose

Specifies the frontend behavior when a player navigates directly to the play route or reloads the page mid-adventure. Because the `gameSession` store is in-memory and is reset on page load, the play route MUST re-hydrate state from the backend before first render. This spec also covers the D8 character layout guard that redirects players who navigate to the character sheet while an adventure is in progress.

---

## Requirements

### Requirement: +page.ts load function fetches current play state before render

The SvelteKit `+page.ts` load function SHALL call `getCurrentPlayState(characterId)` and return the result as page data. This function SHALL call `GET /characters/{id}/play/current` via `apiFetch<PendingStateRead>`. If the response contains a `pending_event` the page data SHALL include `pendingState: PendingStateRead`. If the endpoint returns a 204 or otherwise indicates no active adventure, the function SHALL call `GET /characters/{id}/overworld` and return `overworldState: OverworldStateRead`. This guarantees UI never shows an empty state on hard refresh.

The `+page.svelte` `onMount` (or reactive `$effect`) SHALL call `gameSession.init(data.pendingState)` or `gameSession.initOverworld(data.overworldState)` based on which key is present, before any interaction is possible.

#### Scenario: page reload with active adventure restores game state

- **GIVEN** a player is mid-adventure and reloads the browser
- **WHEN** the `+page.ts` load function runs
- **THEN** `GET /characters/{id}/play/current` returns a `PendingStateRead`
- **AND** `pendingState` is passed to `gameSession.init()`
- **AND** the play page renders the correct decision component for `pending_event.type`
- **AND** `NarrativeLog` shows the entries reconstructed from `session_output`

#### Scenario: page reload with no adventure shows overworld

- **GIVEN** a player navigates directly to `/characters/{id}/play` with no active adventure
- **WHEN** the `+page.ts` load function runs
- **THEN** `GET /characters/{id}/play/current` returns 204 or empty body
- **AND** `GET /characters/{id}/overworld` is called
- **AND** `overworldState` is passed to `gameSession.initOverworld()`
- **AND** `OverworldView` is shown

---

### Requirement: NarrativeLog is reconstructed from session_output on recovery

`PendingStateRead.session_output` is a `List[str]` of narrative lines emitted during the current session. On recovery, `gameSession.init()` SHALL convert each string in `session_output` into a `NarrativeEntry` and set `store.narrativeLog` so that the `NarrativeLog` component shows the history from the recovered session. The reconstructed entries SHALL NOT play the fade-in animation — they appear immediately as static text since they represent already-seen content.

#### Scenario: narrative log shows previous output on hard refresh

- **GIVEN** a player received 3 paragraphs of narrative before reloading
- **WHEN** `gameSession.init()` is called with a `PendingStateRead` where `session_output` contains those 3 entries
- **THEN** `NarrativeLog` shows all 3 entries without animation
- **AND** new entries appended during the resumed session DO play the fade-in animation

---

### Requirement: D8 character layout redirects to play route when adventure is active

The character-scoped `+layout.ts` (D8) SHALL run before rendering any character sub-route (character sheet, inventory, etc.). It SHALL call `GET /characters/{id}/play/current` and, if an active adventure is found (`pending_event` is present), SHALL redirect to `/characters/{id}/play`. This prevents a player from accidentally viewing a stale character sheet while mid-adventure.

The redirect SHALL use SvelteKit's `redirect(307, ...)` so that navigating back from the play route does not loop. The redirect SHALL only fire for character sub-routes other than `/play` — it SHALL NOT create an infinite redirect loop when already on the play route.

#### Scenario: navigating to character sheet mid-adventure redirects to play

- **GIVEN** a player has an active adventure session
- **WHEN** the player navigates to `/characters/{id}/sheet`
- **THEN** the D8 `+layout.ts` load function detects the active adventure
- **AND** SvelteKit redirects the player to `/characters/{id}/play`
- **AND** the play page re-hydrates the active adventure state

#### Scenario: no active adventure allows normal character sheet navigation

- **GIVEN** a player has no active adventure
- **WHEN** the player navigates to `/characters/{id}/sheet`
- **THEN** the D8 `+layout.ts` load function receives 204 or empty body
- **AND** no redirect occurs
- **AND** the character sheet renders normally

#### Scenario: already on play route does not redirect

- **GIVEN** a player is on `/characters/{id}/play` with an active adventure
- **WHEN** the D8 `+layout.ts` re-runs (e.g., during client-side navigation within the character scope)
- **THEN** the redirect guard checks the current path and does NOT redirect if it is already `/characters/{id}/play`
- **AND** no redirect loop occurs

---

### Requirement: load function errors surface as page-level error state

If `getCurrentPlayState` throws an `ApiError` (other than 404/204), the `+page.ts` load function SHALL allow the error to propagate so that SvelteKit renders its `+error.svelte` boundary. The D8 layout guard SHALL also propagate non-404 errors so that broken auth or server errors are visible to the player rather than silently swallowed.
