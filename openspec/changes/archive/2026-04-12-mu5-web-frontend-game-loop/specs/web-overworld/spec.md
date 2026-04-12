# Web Overworld

## Purpose

Specifies the overworld screen rendered at `/characters/[id]/play` when `gameSession.mode === "overworld"`. The overworld is the player's hub between adventures: it shows the current location, available adventures, navigable locations, and a compact character sidebar. It also implements the triggered-adventure detection loop that starts adventures initiated by the server outside of player action.

---

## Requirements

### Requirement: Overworld screen is rendered by the play route, not a separate route

The overworld and adventure screens share the single route `/characters/[id]/play`. Mode switching between `"overworld"` and `"adventure"` is driven by `$gameSession.mode` — no SvelteKit navigation occurs. The `OverworldView` component SHALL be rendered when `$gameSession.mode === "overworld"`. The `NarrativeLog` + decision area SHALL be rendered when `mode` is `"adventure"`, `"loading"`, or `"complete"`.

#### Scenario: navigation to /play renders overworld when no adventure is active

- **GIVEN** `GET /characters/{id}/play/current` returns `{ pending_event: null, session_output: [] }`
- **WHEN** the user navigates to `/characters/{id}/play`
- **THEN** `gameSession.mode` is `"overworld"` and `OverworldView` is rendered
- **AND** no adventure screen components are visible

---

### Requirement: OverworldView fetches and displays location state

`OverworldView.svelte` receives `state: OverworldStateRead | null` and `characterId: string`. When `state` is null it SHALL render a `LoadingSpinner`. When populated it SHALL render `LocationInfo`, `AdventureList`, `NavigationPanel`, and `CharacterSidebar`. The `state` is initialized from `getCurrentPlayState` in the page load function; the component does not fetch it independently on first render.

#### Scenario: overworld renders available adventures for current location

- **GIVEN** `OverworldStateRead.available_adventures` has 2 entries
- **WHEN** `OverworldView` renders
- **THEN** `AdventureList` shows 2 adventure cards, each with `display_name` and `description`

---

### Requirement: AdventureList begins an adventure via gameSession

`AdventureList.svelte` SHALL call `onBeginAdventure(adventure.ref)` when a player selects an adventure. The parent `+page.svelte` handler calls `gameSession.begin(characterId, adventureRef)`. `AdventureList` SHALL NOT call `gameSession` directly.

#### Scenario: selecting an adventure transitions the play screen to loading

- **GIVEN** `AdventureList` shows "SSE Events Showcase"
- **WHEN** the player clicks "Begin" on that adventure
- **THEN** `onBeginAdventure("api-sse-events")` is called
- **AND** `$gameSession.mode` transitions to `"loading"` before the first SSE event
- **AND** `OverworldView` is replaced by `NarrativeLog` + `LoadingSpinner`

---

### Requirement: NavigationPanel navigates to a new location via the API

`NavigationPanel.svelte` SHALL call `navigateLocation(characterId, location.ref)` from `api/characters.ts` when a non-current location button is clicked. On success it SHALL call `onNavigated(newOverworldState)` so the parent can update `$gameSession.overworldState`. The current location button SHALL be visually highlighted and its button disabled. On `ApiError` the panel SHALL render an `ErrorBanner`.

#### Scenario: navigating updates the overworld state

- **GIVEN** the player is at "API Hub" and "API Secondary Location" is listed
- **WHEN** the player clicks "API Secondary Location"
- **THEN** `POST /characters/{id}/navigate` is called with `{ location_ref: "api-secondary" }`
- **AND** on success `onNavigated` is called with the updated `OverworldStateRead`
- **AND** "API Secondary Location" is now highlighted as the current location

---

### Requirement: OverworldView polls for triggered adventures

`OverworldView.svelte` SHALL poll `GET /characters/{id}/overworld` every 5 seconds while rendered. When the polling response indicates a non-null `pending_event` (fetched from `GET /play/current`), the component SHALL call `gameSession.begin(characterId, adventureRef)` to start the adventure stream without navigating. The poll SHALL be stopped when the component is destroyed (use `onDestroy` to clear the interval).

#### Scenario: triggered adventure starts from overworld without navigation

- **GIVEN** the player is on the overworld screen
- **WHEN** the server-side engine starts an adventure and `/play/current` returns a non-null `pending_event`
- **THEN** `gameSession.begin()` is called automatically within one poll interval (≤5 seconds)
- **AND** the URL remains `/characters/{id}/play`
- **AND** the overworld unmounts and the adventure screen mounts in its place
