# Spec: Web Overworld

## Purpose

Defines the overworld state and hierarchical region navigation. The overworld is the "between adventures" layer where a player browses the world map, navigates through regions, and begins adventures from accessible locations.

## Requirements

### Requirement: GET /characters/{id}/overworld returns complete overworld state

`GET /characters/{id}/overworld` SHALL be an authenticated endpoint that returns `OverworldStateRead` (HTTP 200). The endpoint SHALL return HTTP 404 for unowned characters.

`OverworldStateRead` SHALL contain:

- `character_id: UUID`
- `accessible_locations: List[LocationOptionRead]` — all locations in the registry whose unlock conditions the character currently meets
- `region_graph: RegionGraphRead` — nodes and edges for the complete world graph (all regions and locations in the registry, not filtered to accessible locations; the frontend hides inaccessible location rows using `accessible_locations` as the filter)

`OverworldStateRead` SHALL NOT contain any field that reveals adventure names, descriptions, refs, or counts. There is no `current_location`, `current_location_name`, `current_region_name`, `available_adventures`, or `navigation_options` field.

`LocationOptionRead` SHALL contain:

- `ref: str`
- `display_name: str`
- `description: str | None` — location description; `None` when the manifest has an empty description
- `region_ref: str` — the ref of the region this location belongs to
- `region_name: str` — the display name of that region
- `adventures_available: bool` — `true` if at least one adventure in the location's pool is currently eligible for this character; `false` otherwise

`adventures_available` SHALL NOT reveal what adventures are available, how many, or by what names. It SHALL only indicate whether a Begin Adventure action is currently possible.

`RegionGraphRead` SHALL contain: `nodes: List[RegionGraphNode]`, `edges: List[RegionGraphEdge]`.

`RegionGraphNode` SHALL contain:

- `id: str`
- `label: str`
- `kind: str` (either `"region"` or `"location"`)
- `description: str | None` — region description for `kind="region"` nodes; `None` for location nodes and for regions with an empty description

`RegionGraphEdge` SHALL contain: `source: str`, `target: str`, `label: str`.

`AdventureOptionRead` is REMOVED from this endpoint. No adventure names, descriptions, or refs SHALL be exposed in this response.

#### Scenario: LocationOptionRead carries description when manifest has one

- **GIVEN** a location manifest with `description: "A dark forest clearing"`
- **WHEN** `GET /overworld` is called for a character who can access that location
- **THEN** the corresponding `LocationOptionRead` has `description: "A dark forest clearing"`

#### Scenario: LocationOptionRead description is null for empty manifest description

- **GIVEN** a location manifest with `description: ""`
- **WHEN** `GET /overworld` is called
- **THEN** the corresponding `LocationOptionRead` has `description: null`

#### Scenario: RegionGraphNode carries description for region nodes

- **GIVEN** a region manifest with `description: "The Northern Reaches"`
- **WHEN** `GET /overworld` is called
- **THEN** the `RegionGraphNode` for that region has `description: "The Northern Reaches"`

#### Scenario: RegionGraphNode description is null for location nodes

- **GIVEN** a location node in the region graph
- **WHEN** `GET /overworld` is called
- **THEN** the location `RegionGraphNode` has `description: null`

#### Scenario: returns accessible_locations with adventures_available

- **GIVEN** a character who meets the unlock conditions for `"test-location"` which has eligible adventures, and `"test-location-empty"` which has no eligible adventures, but NOT `"test-location-locked"`
- **WHEN** `GET /overworld` is called
- **THEN** the response contains `accessible_locations` with an entry for `"test-location"` where `adventures_available` is `true`
- **AND** an entry for `"test-location-empty"` where `adventures_available` is `false`
- **AND** `"test-location-locked"` is NOT in `accessible_locations`
- **AND** the response does NOT contain any adventure names, descriptions, or refs

#### Scenario: returns empty accessible_locations for a character with no unlocked locations

- **GIVEN** a newly created character with no unlocked locations
- **WHEN** `GET /overworld` is called
- **THEN** `accessible_locations` is an empty list

#### Scenario: Returns 404 for an unowned character

- **GIVEN** character `{id}` belongs to user B
- **WHEN** user A calls `GET /overworld`
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

### Requirement: OverworldView implements hierarchical region navigation

`OverworldView.svelte` receives `overworldState: OverworldStateRead | null`, `characterId: string`, and `onBeginAdventure: (locationRef: string) => void`. When `state` is null it SHALL render a `LoadingSpinner`.

The component SHALL store `currentRegion: string | null` in local Svelte `$state`. This value SHALL NOT be sent to the server.

When `currentRegion` is `null`, the component SHALL render root-level regions (region nodes in `region_graph` with no incoming edges from other region nodes).

When `currentRegion` is set, the component SHALL render the direct children of that region using `region_graph` edges:

- Region-kind children SHALL be rendered as navigation buttons that update `currentRegion`.
- Location-kind children that appear in `accessible_locations` SHALL be rendered as location rows with a Begin Adventure button. The button SHALL be **disabled** when `loc.adventures_available === false`.

A back button SHALL be present (and functional) whenever `currentRegion` is not null.

The component SHALL NOT display adventure names, descriptions, counts, or eligibility explanations.

`AdventureList.svelte` is REMOVED.

#### Scenario: shows all root regions on initial render

- **GIVEN** a `region_graph` with two disconnected root regions (no edges between them), each with child locations
- **WHEN** `OverworldView` renders with `currentRegion` = null (the initial world map state)
- **THEN** both root regions are shown as navigation buttons simultaneously
- **AND** no location rows or Begin Adventure buttons are visible
- **AND** no back button is shown

#### Scenario: back button from root region returns to world map

- **GIVEN** the player has navigated into a root region
- **WHEN** they click the back button
- **THEN** `currentRegion` returns to `null`
- **AND** all root regions are displayed again

#### Scenario: entering a region shows its children

- **GIVEN** the player clicks a root region button
- **WHEN** `currentRegion` is updated to that region's id
- **THEN** the children of that region are rendered (sub-regions as buttons, locations as location rows)
- **AND** a back button is shown

#### Scenario: Begin Adventure button is disabled when adventures_available is false

- **GIVEN** a location row where `loc.adventures_available === false`
- **WHEN** `OverworldView` renders
- **THEN** the Begin Adventure button is in a disabled state
- **AND** clicking it does NOT call `onBeginAdventure`

#### Scenario: clicking Begin Adventure passes the location ref

- **GIVEN** a location with ref `"test-location"` and `adventures_available === true`
- **WHEN** the player clicks its Begin Adventure button
- **THEN** `onBeginAdventure("test-location")` is called
- **AND** `$gameSession.mode` transitions to `"loading"` before the first SSE event

---

### Requirement: OverworldView polls for triggered adventures

`OverworldView.svelte` SHALL poll `GET /characters/{id}/overworld` every 5 seconds while rendered. When the polling response indicates a non-null `pending_event` (fetched from `GET /play/current`), the component SHALL call `gameSession.begin(characterId, adventureRef)` to start the adventure stream without navigating. The poll SHALL be stopped when the component is destroyed (use `onDestroy` to clear the interval).

#### Scenario: triggered adventure starts from overworld without navigation

- **GIVEN** the player is on the overworld screen
- **WHEN** the server-side engine starts an adventure and `/play/current` returns a non-null `pending_event`
- **THEN** `gameSession.begin()` is called automatically within one poll interval (≤5 seconds)
- **AND** the URL remains `/characters/{id}/play`
- **AND** the overworld unmounts and the adventure screen mounts in its place
