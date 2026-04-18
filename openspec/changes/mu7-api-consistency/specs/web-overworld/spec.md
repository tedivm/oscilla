## MODIFIED Requirements

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

#### Scenario: Returns 404 for an unowned character

- **GIVEN** character `{id}` belongs to user B
- **WHEN** user A calls `GET /characters/{id}/overworld`
- **THEN** the response has HTTP 404
