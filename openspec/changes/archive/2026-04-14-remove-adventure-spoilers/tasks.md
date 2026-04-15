# Tasks: Remove Adventure Spoilers

## 1. Backend — Remove `current_location` from the engine

- [x] 1.1 Remove `current_location: str | None` field from `CharacterState` in `oscilla/engine/character.py`
- [x] 1.2 Remove `current_location` from `create_initial_state()`, `to_save_dict()`, and `from_save_dict()` in `oscilla/engine/character.py`
- [x] 1.3 Remove `SetLocationEffect` model class (with `type: Literal["set_location"]` and `location: str | None`) from `oscilla/engine/models/adventure.py`, and remove it from the `Effect` union type alias
- [x] 1.4 Remove the `SetLocationEffect` handler block from `oscilla/engine/steps/effects.py`

## 2. Backend — Remove `current_location` from persistence

- [x] 2.1 Remove `current_location: Mapped[str | None]` from `CharacterIteration` in `oscilla/models/character_iteration.py`
- [x] 2.2 Remove all three fields — `current_location`, `current_location_name`, and `current_region_name` — from `CharacterRead` in `oscilla/models/api/characters.py`; remove the helper block that resolves these names from the registry (lines that call `registry.locations.get(state.current_location)` and `registry.regions.get(...)` to populate them)
- [x] 2.3 Remove all `current_location` references from `oscilla/services/character.py` (save path and load path)
- [x] 2.4 Create an Alembic migration: `make create_migration MESSAGE="remove_current_location_from_character_iterations"` and verify it generates `op.drop_column("character_iterations", "current_location")` in `upgrade()` with a matching `op.add_column(...)` `downgrade()`

## 3. Backend — Overworld Router

- [x] 3.1 Remove `AdventureOptionRead` and `NavigateRequest` Pydantic models from `oscilla/routers/overworld.py`
- [x] 3.2 Replace `LocationOptionRead` fields: remove `is_current`; add `region_ref: str`, `region_name: str`, and `adventures_available: bool`
- [x] 3.3 Rebuild `OverworldStateRead`: remove `current_location`, `current_location_name`, `current_region_name`, `available_adventures`, `navigation_options`; add `accessible_locations: List[LocationOptionRead]`; retain `region_graph: RegionGraphRead` unchanged
- [x] 3.4 Add `_is_any_adventure_eligible(loc, state, registry, now_ts) -> bool` private helper that returns `True` if any entry in `loc.spec.adventures` passes both `evaluate(entry.requires, state, registry)` and `state.is_adventure_eligible(...)`
- [x] 3.5 Rewrite `_build_overworld_state` to iterate `registry.locations.all()`, filter by `evaluate(loc.spec.effective_unlock, state, registry)`, build `LocationOptionRead` with `region_ref=loc.spec.region`, `region_name` resolved from the registry, and `adventures_available` from the new helper; remove all adventure-listing and `current_location`-resolution logic
- [x] 3.6 Delete the `POST /navigate` route handler from `oscilla/routers/overworld.py`

## 4. Backend — Play Router

- [x] 4.1 Delete `BeginAdventureRequest` and the `begin_adventure` route handler (`POST /characters/{character_id}/play/begin`) from `oscilla/routers/play.py`
- [x] 4.2 Add `GoAdventureRequest(location_ref: str)` and `go_adventure` route handler at `POST /characters/{character_id}/play/go` in `oscilla/routers/play.py`; explicit step order: (1) validate location exists in registry → 422 if not; (2) load character state → 404 if not found; (3) validate location accessible by evaluating `loc.spec.effective_unlock` against loaded character state → 422 if conditions fail; (4) build eligible pool (`evaluate(entry.requires, state, registry)` + `state.is_adventure_eligible(...)`) → 422 if empty; (5) `random.choices` weighted selection; (6) acquire lock → 409 if held; (7) stream SSE
- [x] 4.3 Verify that `loc.spec.effective_unlock` is the correct attribute for the location's unlock condition, matching the TUI's accessibility logic; adjust attribute name if needed

## 5. Backend — Content Audit

- [x] 5.1 Search all YAML files under `content/` for `set_location` effect usage: `grep -r "set_location" content/`; remove `SetLocationEffect` entries from any manifests that contain them

## 6. Frontend — Types and API Client

- [x] 6.1 Remove `AdventureOptionRead`, `NavigateRequest` interfaces from `frontend/src/lib/api/types.ts`
- [x] 6.2 Remove `current_location`, `current_location_name`, `current_region_name`, `available_adventures`, `navigation_options` from `OverworldStateRead`; add `accessible_locations: LocationOptionRead[]`
- [x] 6.3 Update `LocationOptionRead` in `frontend/src/lib/api/types.ts`: remove `is_current`; add `region_ref: string`, `region_name: string`, `adventures_available: boolean`
- [x] 6.4 Remove `current_location`, `current_location_name`, and `current_region_name` from `CharacterRead` in `frontend/src/lib/api/types.ts` (if present)
- [x] 6.5 Remove the `navigate(characterId, locationRef)` API function from `frontend/src/lib/api/` (wherever it lives)
- [x] 6.6 Add `beginAdventureGo(characterId: string, locationRef: string): AsyncGenerator<SSEEvent>` to `frontend/src/lib/api/play.ts`; calls `fetchSSE` on `POST /characters/{id}/play/go` with `{ location_ref: locationRef }` as JSON body

## 7. Frontend — Component Changes

- [x] 7.1 Delete `frontend/src/lib/components/Overworld/AdventureList.svelte`
- [x] 7.2 Rebuild `OverworldView.svelte` with hierarchical region navigation:
  - Add `let currentRegion = $state<string | null>(null)` — null means world map (all root regions visible)
  - Derive `childrenOf: Map<string, string[]>` from `region_graph.edges`
  - Derive `rootRegions` as region-kind nodes with no incoming edges (the graph may have multiple disconnected roots)
  - When `currentRegion` is null, render all root regions as navigation buttons simultaneously
  - When `currentRegion` is set, render its direct region children as navigation buttons and its location children (filtered to `accessible_locations`) as location rows
  - Each location row has a Begin Adventure button: enabled when `loc.adventures_available`, disabled otherwise
  - Back button always present when `currentRegion !== null`; from a root region, back returns to null
  - Remove `AdventureList` import; update `onBeginAdventure` prop type to `(locationRef: string) => void`
- [x] 7.3 Update the `onBeginAdventure` caller in the play route page (`frontend/src/routes/play/[id]/+page.svelte` or equivalent): pass `locationRef` from the button click through to `gameSession.go(characterId, locationRef)` (or equivalent calling `beginAdventureGo(characterId, locationRef)`)
- [x] 7.4 Remove all `navigate`-related calls and imports from the play route page; delete `gameSession.navigate(...)` or equivalent if it exists in the session store

## 8. Backend Tests

- [x] 8.1 Update `tests/routers/test_overworld.py`: remove all tests calling `POST /navigate`; remove all assertions referencing `available_adventures`, `current_location*`, `navigation_options`; add assertions that `accessible_locations` is a list; add assertions that `LocationOptionRead` contains all five fields: `ref`, `display_name`, `region_ref`, `region_name`, `adventures_available` (and no `is_current`)
- [x] 8.2 Add test `test_overworld_adventures_available_accuracy`: configure a location with at least one eligible adventure and a location with an empty pool (conditions always fail); call `GET /overworld`; assert the first location has `adventures_available: true` and the second has `adventures_available: false`
- [x] 8.3 Update or rewrite all tests in `tests/routers/test_play.py` that call `POST /play/begin`: replace with calls to `POST /play/go` with a `location_ref` body; configure test location fixtures so the pool has the needed adventures
- [x] 8.4 Add test `test_go_adventure_422_unknown_location`: unknown `location_ref` → 422
- [x] 8.5 Add test `test_go_adventure_422_locked_location`: location with failing unlock condition → 422
- [x] 8.6 Add test `test_go_adventure_422_empty_pool`: location with no eligible adventures (conditions fail for current state) → 422
- [x] 8.7 Add test `test_go_adventure_streams_sse`: valid location with adventures in pool → 200, `Content-Type: text/event-stream`, at least one SSE event
- [x] 8.8 Add test `test_go_adventure_409_lock_held`: insert a live lock row for the iteration, call `POST /play/go` → 409
- [x] 8.9 Add test `test_go_adventure_404_other_user`: call with another user's `character_id` → 404
- [x] 8.10 Run `uv run pytest tests/routers/ -q` and confirm all tests pass

## 9. Frontend Tests

- [x] 9.1 Delete `frontend/src/lib/components/Overworld/AdventureList.test.ts` if it exists
- [x] 9.2 Update `OverworldView.test.ts` if it exists:
  - Add test: two disconnected root regions in `region_graph` with no edges between them → both rendered as navigation buttons in the initial (null) state, no back button shown
  - Add test: entering a region → its child locations appear; back button returns to world map
  - Add test: location with `adventures_available: false` → Begin Adventure button is disabled
  - Add test: location with `adventures_available: true` → clicking calls `onBeginAdventure(loc.ref)`
  - Remove any existing adventure-card or `AdventureList` assertions
- [x] 9.3 Run `make frontend_test` and confirm all frontend tests pass

## 10. End-to-End Tests (Playwright)

- [x] 10.1 Update the E2E test that previously navigated to a location and selected an adventure from a list: replace with a flow that navigates through region buttons on the overworld to reach a location and clicks the Begin Adventure button
- [x] 10.2 Add E2E scenario `overworld_region_navigation`: from the world map, click a region navigation button → its child locations are visible; click the back button → root regions are shown again
- [x] 10.3 Add E2E scenario `begin_adventure_from_overworld`: navigate to a location with an eligible adventure, click Begin Adventure, verify the play view loads and the adventure stream begins (no adventure name or ref visible at any point)
- [x] 10.4 Add E2E scenario `disabled_begin_adventure`: for a location whose adventure pool is empty (all adventures on cooldown or conditions failing), verify the Begin Adventure button is present but has the `disabled` attribute and cannot be activated
- [x] 10.5 Run `make frontend_e2e` and confirm all E2E tests pass

## 11. Accessibility Tests (Playwright a11y)

- [x] 11.1 Verify that all region navigation buttons have accessible labels (region display names rendered as visible text or `aria-label`) — no unlabeled `<button>` elements in the overworld view
- [x] 11.2 Verify that a disabled Begin Adventure button uses the `disabled` HTML attribute (not only CSS opacity/pointer-events), so screen readers announce it as unavailable
- [x] 11.3 Verify the back button has a descriptive accessible label (`← Back` text is sufficient; must not be icon-only with no label)
- [x] 11.4 Verify the `LoadingSpinner` in the overworld has an appropriate `aria-label` or `role="status"` so assistive technology announces the loading state
- [x] 11.5 Run `make frontend_a11y` and confirm all accessibility checks pass

## 12. Documentation

- [x] 12.1 Update `docs/dev/api.md` Overworld section: replace the `OverworldStateRead` table to show `accessible_locations: List[LocationOptionRead]` and `region_graph`; remove `available_adventures`, `current_location*`, `navigation_options`, `AdventureOptionRead` sub-table; update `LocationOptionRead` table to show `ref`, `display_name`, `region_name`; remove `POST /navigate` section entirely
- [x] 12.2 Add `POST /play/go` section to `docs/dev/api.md` under Play Endpoints: document `{ "location_ref": "<ref>" }` request body; 200 SSE stream; 422 variants (unknown location, locked location, empty pool); 409 lock held; 404 not found; note that adventure selection is server-side and never exposed to the client
- [x] 12.3 Remove `POST /play/begin` section from `docs/dev/api.md`

## 13. Testlandia QA

- [x] 13.1 Confirm at least one testlandia location has adventures in its pool; run `make validate` to verify all content is valid after removing `SetLocationEffect` from any YAML
- [x] 13.2 Manually start a local server (`docker compose up -d`), open the overworld for a testlandia character, and verify: the world map shows root region(s) as navigation buttons; clicking a region shows its child locations; each location shows a Begin Adventure button (disabled if pool is empty); clicking it starts an adventure immediately without showing any adventure name or description
- [x] 13.3 If testlandia has multiple root regions, verify both appear in the initial world map view and each is independently navigable

## 14. Final Validation

- [x] 14.1 Run `make tests` and confirm all checks pass (pytest, ruff, mypy, frontend checks)
- [x] 14.2 Confirm `SetLocationEffect`, `BeginAdventureRequest`, `begin_adventure`, `NavigateRequest`, `AdventureOptionRead`, `available_adventures`, `navigation_options`, `current_location` no longer appear in backend source files
- [x] 14.3 Confirm `AdventureOptionRead`, `available_adventures`, `navigate(`, `current_location`, `adventures_available` (as a top-level field — the per-location field is intentional) no longer appear as top-level schema fields in frontend source files
