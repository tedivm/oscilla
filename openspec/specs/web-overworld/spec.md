# Spec: Web Overworld

## Purpose

Defines the overworld state and navigation endpoints. The overworld is the "between adventures" layer where a player views their current location, available adventures, and reachable locations.

## Requirements

### Requirement: GET /characters/{id}/overworld returns complete overworld state

`GET /characters/{id}/overworld` SHALL be an authenticated endpoint that returns `OverworldStateRead` (HTTP 200). The endpoint SHALL return HTTP 404 for unowned characters.

`OverworldStateRead` SHALL contain:

- `character_id: UUID`
- `current_location: str | None` — location ref from the iteration row
- `current_location_name: str | None` — display name resolved from `registry.locations`
- `current_region_name: str | None` — display name of the location's parent region
- `available_adventures: List[AdventureOptionRead]` — adventures in the current location's pool, with display name and description resolved from `registry.adventures`; empty list if `current_location` is None
- `navigation_options: List[LocationOptionRead]` — all locations in `registry.locations` that share the current region, with `is_current` set for the active one; empty list if `current_location` is None
- `region_graph: RegionGraphRead` — nodes and edges for the current region, derived from `build_world_graph` scoped to the character's region; empty graph if `current_location` is None

`AdventureOptionRead` SHALL contain: `ref: str`, `display_name: str`, `description: str`.

`LocationOptionRead` SHALL contain: `ref: str`, `display_name: str`, `is_current: bool`.

`RegionGraphRead` SHALL contain: `nodes: List[RegionGraphNode]`, `edges: List[RegionGraphEdge]`.

`RegionGraphNode` SHALL contain: `id: str`, `label: str`, `kind: str`.

`RegionGraphEdge` SHALL contain: `source: str`, `target: str`, `label: str`.

#### Scenario: Returns full OverworldStateRead for a character with a current_location

- **GIVEN** a character at location `"easy-fight"` in region `"combat"`
- **WHEN** `GET /overworld` is called
- **THEN** the response contains `current_location = "easy-fight"`, `current_location_name`, `current_region_name`, `available_adventures` matching the location's adventure pool, and `navigation_options` listing all combat-region locations

#### Scenario: Returns null location fields for a character with no current_location

- **GIVEN** a character with `current_location = null`
- **WHEN** `GET /overworld` is called
- **THEN** `current_location`, `current_location_name`, `current_region_name` are all `null`; `available_adventures`, `navigation_options`, and `region_graph` are empty collections

#### Scenario: Returns 404 for an unowned character

- **GIVEN** character `{id}` belongs to user B
- **WHEN** user A calls `GET /overworld`
- **THEN** the response has HTTP 404

---

### Requirement: POST /characters/{id}/navigate moves the character to a new location

`POST /characters/{id}/navigate` SHALL be an authenticated endpoint accepting `NavigateRequest` and returning `OverworldStateRead` (HTTP 200). The endpoint SHALL return HTTP 404 for unowned characters.

`NavigateRequest` SHALL contain:

- `location_ref: str` — the destination location ref

The endpoint SHALL validate that `location_ref` exists in `registry.locations`. If `location_ref` is unknown it SHALL return HTTP 422. If the location's `effective_unlock` condition is not satisfied by the character's current state it SHALL return HTTP 422 with a descriptive detail. On success it SHALL update `current_location` on the iteration row and return the new `OverworldStateRead`.

Navigation is unrestricted between locations within the same region and between regions — region membership is not enforced by this endpoint. Unlock conditions are the sole access control mechanism.

#### Scenario: Successfully navigates to an unlocked location

- **WHEN** the owner calls `POST /navigate` with a valid, unlocked `location_ref`
- **THEN** the response has HTTP 200 with `OverworldStateRead` reflecting the new location
- **AND** `GET /characters/{id}` shows `current_location` equals the new ref

#### Scenario: Returns 422 for an unknown location_ref

- **WHEN** `POST /navigate` is called with `{"location_ref": "nonexistent"}`
- **THEN** the response has HTTP 422

#### Scenario: Returns 422 for a location whose unlock condition is not satisfied

- **GIVEN** location `"locked-area"` requires a stat condition the character does not meet
- **WHEN** `POST /navigate` is called with `{"location_ref": "locked-area"}`
- **THEN** the response has HTTP 422 with a descriptive message

#### Scenario: Returns 404 for an unowned character

- **GIVEN** character `{id}` belongs to user B
- **WHEN** user A calls `POST /navigate`
- **THEN** the response has HTTP 404

---

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
