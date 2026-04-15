## Why

The current `GET /characters/{id}/overworld` endpoint returns `available_adventures: List[AdventureOptionRead]`, which exposes the name, description, and internal ref of every adventure in the current location's pool. This leaks content the player has not yet encountered — spoilers — and is architecturally wrong: by design, players navigate to a location and the engine selects an adventure via weighted random, exactly as the TUI implements. The web API was built with the adventure list surfaced so the frontend could let the player pick, but that selection model directly contradicts the intended UX and produces spoilers.

Additionally, there is no server-side pool-selection endpoint: `POST /play/begin` requires an explicit `adventure_ref`, meaning the frontend currently drives the selection rather than the engine — a fundamental inversion of the intended design.

## What Changes

### Backend

- **BREAKING** Remove `available_adventures: List[AdventureOptionRead]` and the `AdventureOptionRead` Pydantic model from `oscilla/routers/overworld.py`.
- **BREAKING** Remove `current_location`, `current_location_name`, and `current_region_name` from `OverworldStateRead` — there is no concept of a player being "at" a location between adventures. `OverworldStateRead` is rebuilt around `accessible_locations: List[LocationOptionRead]` (all locations the character can currently access, each with region name) and `region_graph: RegionGraphRead` (the full accessible world graph, not scoped to a current region).
- **BREAKING** Remove `POST /characters/{id}/navigate` — the endpoint's only purpose was persisting `current_location`, which no longer exists as a concept.
- **BREAKING** Remove `current_location` and `current_location_name` from `CharacterRead`.
- **BREAKING** Remove `current_location: str | None` from `CharacterState` and from the `character_iterations` database table; add an Alembic migration to drop the column.
- **BREAKING** Remove `SetLocationEffect` — the effect set `player.current_location` as an adventure outcome. That concept does not exist. Remove it from `effects.py` and from the adventure model.
- **BREAKING** Remove `POST /play/begin` — the only adventure-start endpoint available on the web API is now `POST /play/go`. There is no mechanism to start a specific adventure by ref from the web API.
- **New endpoint** `POST /characters/{id}/play/go` — takes `{ "location_ref": "..." }` in the request body. The backend validates the location exists and is accessible, evaluates the eligible adventure pool (conditions + repeat controls), selects one via weighted random, and begins the SSE stream. The frontend never learns which adventure was chosen.

### Frontend

- Remove `AdventureList.svelte` entirely.
- Rebuild `OverworldView.svelte`: renders the list of accessible locations by name, each with a "Begin Adventure" button that sends `POST /play/go` with that location's `ref`. No adventure names, counts, descriptions, or availability signals are shown at any point.
- Update `types.ts`: remove `AdventureOptionRead`; replace `OverworldStateRead` with the new schema; remove `NavigateRequest`.
- Update the API client: remove the `navigate()` call; add `beginAdventureGo(characterId, locationRef)`.
- Update the game session store: remove calls to the navigate endpoint; update the begin-adventure flow to use `beginAdventureGo`.

### Documentation and Specs

- Update `web-overworld` spec: new `OverworldStateRead` schema, navigate endpoint removal.
- Update `web-play-go` spec: `POST /play/go` accepts `location_ref` in the request body; 422 on unknown/inaccessible location or empty pool.
- Update `docs/dev/api.md`: remove navigate docs, remove `current_location` fields, document new shapes.

## Capabilities

### New Capabilities

- `web-play-go`: `POST /characters/{id}/play/go` endpoint that performs server-side adventure pool selection and begins the chosen adventure via the existing SSE pipeline.

### Modified Capabilities

- `web-overworld`: Complete schema overhaul — remove `available_adventures`, `current_location`, `current_location_name`, `current_region_name`; replace with `accessible_locations: List[LocationOptionRead]` and a full-world `region_graph`. Navigate endpoint removed. Frontend overworld view loses `AdventureList` selection UI and renders accessible locations directly, each with a Begin Adventure button.

## Impact

- **`oscilla/routers/overworld.py`**: Remove `AdventureOptionRead` and the navigate route handler; rebuild `OverworldStateRead` with `accessible_locations` and `region_graph`; remove all `current_location*` fields; update `_build_overworld_state` to iterate all accessible locations.
- **`oscilla/routers/play.py`**: Remove `begin_adventure` route and `BeginAdventureRequest` model entirely. Add `GoAdventureRequest` with `location_ref` and `go_adventure` route; the pipeline setup logic that was in `begin_adventure` moves directly into `go_adventure`.
- **`oscilla/engine/character.py`**: Remove `current_location: str | None` from `CharacterState`; remove from serialization and deserialization paths.
- **`oscilla/engine/steps/effects.py`**: Remove `SetLocationEffect` handler.
- **`oscilla/engine/models/adventure.py`**: Remove `SetLocationEffect` model class.
- **`oscilla/models/character_iteration.py`**: Remove `current_location: Mapped[str | None]` column.
- **`oscilla/models/api/characters.py`**: Remove `current_location` and `current_location_name` from `CharacterRead`.
- **`oscilla/services/character.py`**: Remove `current_location` references.
- **`db/versions/`**: New Alembic migration to drop `character_iterations.current_location`.
- **`frontend/src/lib/api/types.ts`**: Remove `AdventureOptionRead`; replace `OverworldStateRead` shape; remove `NavigateRequest`.
- **`frontend/src/lib/api/play.ts`** (or equivalent client): Remove navigate; add `beginAdventureGo(characterId, locationRef)`.
- **`frontend/src/lib/components/Overworld/AdventureList.svelte`**: Delete.
- **`frontend/src/lib/components/Overworld/OverworldView.svelte`**: Rebuild for location-list model.
- **`openspec/specs/web-overworld/spec.md`**: New `OverworldStateRead` schema; navigate endpoint removed.
- **`openspec/specs/web-play-go/spec.md`**: `location_ref` in request body; updated scenarios.
- **`docs/dev/api.md`**: Remove navigate section; update `OverworldStateRead` table; document `POST /play/go`.
- **Tests**: Rewrite all existing `tests/routers/test_play.py` tests to use `POST /play/go` with `location_ref` and fixture-based location pools; remove navigate tests from overworld tests; add `/play/go` scenarios covering unknown location, locked location, empty pool, 409, and 404.
- **Testlandia**: Verify `bump-strength` location pool is set up for manual QA of the Begin Adventure flow.
