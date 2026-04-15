# Design: Remove Adventure Spoilers

## Context

The current `GET /characters/{id}/overworld` endpoint exposes two fundamental problems:

1. **`available_adventures`** — a list of `AdventureOptionRead` objects, each containing `ref`, `display_name`, and `description` for every adventure in the current location's pool. This is spoiler data: players see every adventure title and description before experiencing any of them.

2. **`current_location`** — a persisted field representing which location the character is "currently at" between adventures. This concept does not exist in the game design. In the TUI (`oscilla/engine/tui.py` L893–964), the player selects a region, selects a location, and the engine immediately begins a weighted-random adventure. There is no state between navigation and adventure start. The web API invented this state to support the `POST /navigate` endpoint, which was only needed because the frontend was doing client-side adventure selection.

Additionally, `POST /play/begin` requires an explicit `adventure_ref`, giving the frontend control over which adventure starts. This is the direct opposite of the intended model.

`SetLocationEffect` also follows from the same mistake: it wrote to `player.current_location` as an adventure outcome, treating location-persistence as a game mechanic. It is not.

The web API changes required:

- Remove `current_location` entirely: from `CharacterState`, `character_iterations`, `CharacterRead`, `OverworldStateRead`, and the navigate endpoint.
- Remove `SetLocationEffect` and its model class.
- Remove `POST /play/begin`.
- Replace `OverworldStateRead` with a schema that lists accessible locations (for the UI to render navigation) without any adventure-related data.
- Add `POST /play/go` which takes a `location_ref`, evaluates the eligible pool, selects an adventure via weighted random, and streams the result. The frontend never learns what was selected.

---

## Goals / Non-Goals

**Goals:**

- Remove all adventure-related data from `OverworldStateRead`.
- Remove `current_location` as a persistent concept everywhere it appears.
- Remove `SetLocationEffect`, `POST /navigate`, and `POST /play/begin`.
- Add `POST /play/go` with `location_ref` in the request body as the sole adventure-start endpoint.
- Rebuild `OverworldView.svelte` as a list of accessible locations, each with a Begin Adventure button.
- Update all tests, specs, and docs.

**Non-Goals:**

- Adding a "preview" mode that reveals adventure details after completion.
- Changing the TUI.
- Any adventure-ref exposure anywhere in the web API, even as an admin or test convenience.

---

## Decisions

### D1: There is no concept of a player being "at" a location

**Decision:** `current_location` is removed from `CharacterState`, the `character_iterations` DB column, `CharacterRead`, and all Pydantic response models. The navigate endpoint is removed.

**Why:** It was invented to support the wrong client-side selection model. Removing it eliminates the source of the spoiler leak and correctly models the game: a player picks a location and an adventure immediately begins.

---

### D2: `SetLocationEffect` is removed

**Decision:** `SetLocationEffect` in `oscilla/engine/models/adventure.py` and its handler in `oscilla/engine/steps/effects.py` are deleted.

**Why:** Its only function was to set `player.current_location`. That field no longer exists. Any content using this effect must be updated to remove it.

---

### D3: `POST /play/begin` is removed

**Decision:** `POST /play/begin` and its `BeginAdventureRequest` model are deleted from `oscilla/routers/play.py`. `POST /play/go` is the only adventure-start endpoint.

**Why:** Starting a specific adventure by ref is not a feature. The engine's weighted random selection is the design. Keeping an explicit-ref endpoint contradicts it. Tests must use `/play/go` with properly configured location fixtures.

---

### D4: `AdventureList.svelte` is deleted, not repurposed

**Decision:** Delete `frontend/src/lib/components/Overworld/AdventureList.svelte` entirely.

**Why:** Its sole purpose was rendering selectable adventure cards. That concept does not exist. Dead code creates confusion.

---

### D5: `LocationOptionRead` includes `adventures_available: bool`

**Decision:** `LocationOptionRead` has `ref`, `display_name`, `region_ref`, `region_name`, and `adventures_available: bool`. `OverworldStateRead` has no `available_adventures` list, no `current_location`, and no adventure metadata — just `accessible_locations: List[LocationOptionRead]` and `region_graph: RegionGraphRead`.

**Why `adventures_available`:** The UI needs to be able to present a Begin Adventure button in a disabled state when no adventures are currently eligible at a location. Without this boolean the only way to discover unavailability is to call `/play/go` and receive a 422, which gives the player no opportunity to understand the situation before trying. A per-location boolean does not reveal what adventures exist, how many there are, or what they are called — it only answers "can I push this button right now?"

**Why not a list:** `available_adventures` as a list of names, descriptions, or refs would expose spoilers. The boolean exposes nothing about adventure content.

---

### D6: Region-scoped navigation is strictly frontend state

**Decision:** The backend has no concept of which region a player is "currently browsing." The overworld response always returns all accessible locations and the full `region_graph`. The frontend stores `currentRegion: string | null` in local Svelte reactive state. Clicking a region navigates into it; clicking a location calls `POST /play/go`. The `currentRegion` value is never sent to the server.

**Why:** A game with many locations cannot present them all at once — the player must navigate through regions hierarchically. But this is purely a UI affordance, not a game-state concept. Whether a player is "browsing the Forest region" between adventures is not semantically meaningful and must not be persisted. Keeping it as ephemeral Svelte state means:

- The backend needs no new endpoints or columns.
- Refreshing the page resets navigation to the root view (acceptable: the player picks again).
- The backend's correct mental model (no persistent "current location") is preserved.

**Navigation model:** From a region the player sees its direct children — sub-regions and locations that belong to it. Clicking a sub-region updates `currentRegion`. Clicking a location calls `onBeginAdventure(loc.ref)`. The frontend derives this view from the `region_graph` edges. Root regions are region nodes with no incoming edges from other region nodes.

**The null state is the world map:** When `currentRegion` is `null`, the component renders all root regions simultaneously. The region graph is not necessarily a single connected tree — there can be multiple disconnected root regions with no path between them. The null state is the only view from which all of them are reachable, so it functions as a top-level world map. A back button from any root-level region returns to the null state. There is no auto-selection of a single root region, even if only one exists, because that would silently break the moment a second root region is added.

---

## Implementation

### `oscilla/routers/overworld.py`

#### Remove `AdventureOptionRead`, `NavigateRequest`, navigate route, and `current_location*` fields; rebuild `OverworldStateRead` and `_build_overworld_state`

**Before (models):**

```python
class NavigateRequest(BaseModel):
    location_ref: str = Field(description="Destination location ref.")


class AdventureOptionRead(BaseModel):
    ref: str
    display_name: str
    description: str


class LocationOptionRead(BaseModel):
    ref: str
    display_name: str
    is_current: bool


# ...


class OverworldStateRead(BaseModel):
    character_id: UUID
    current_location: str | None
    current_location_name: str | None
    current_region_name: str | None
    available_adventures: List[AdventureOptionRead]
    navigation_options: List[LocationOptionRead]
    region_graph: RegionGraphRead
```

**After (models):**

```python
class LocationOptionRead(BaseModel):
    ref: str
    display_name: str
    region_ref: str
    region_name: str
    adventures_available: bool


# NavigateRequest, AdventureOptionRead removed


class OverworldStateRead(BaseModel):
    character_id: UUID
    accessible_locations: List[LocationOptionRead]
    region_graph: RegionGraphRead
```

---

**Before (`_build_overworld_state` — simplified):** builds from `state.current_location`, iterates adventures, populates `available_adventures`, scopes graph to current region.

**After (`_build_overworld_state`):**

```python
import time as _time


def _is_any_adventure_eligible(
    loc: Any,
    state: CharacterState,
    registry: ContentRegistry,
    now_ts: int,
) -> bool:
    """Return True if the location has at least one currently eligible adventure."""
    for entry in loc.spec.adventures:
        if evaluate(entry.requires, state, registry) and state.is_adventure_eligible(
            adventure_ref=entry.ref,
            spec=registry.adventures.require(entry.ref, "Adventure").spec,
            now_ts=now_ts,
        ):
            return True
    return False


def _build_overworld_state(
    character_id: UUID,
    state: CharacterState,
    registry: ContentRegistry,
) -> OverworldStateRead:
    """Build OverworldStateRead listing all accessible locations and the full world graph."""
    now_ts = int(_time.time())
    accessible_locations: List[LocationOptionRead] = []
    for loc in registry.locations.all():
        if evaluate(loc.spec.effective_unlock, state, registry):
            region = registry.regions.get(loc.spec.region)
            accessible_locations.append(
                LocationOptionRead(
                    ref=loc.metadata.name,
                    display_name=loc.spec.displayName,
                    region_ref=loc.spec.region,
                    region_name=region.spec.displayName if region is not None else loc.spec.region,
                    adventures_available=_is_any_adventure_eligible(
                        loc=loc,
                        state=state,
                        registry=registry,
                        now_ts=now_ts,
                    ),
                )
            )

    # Build the full (unfiltered) world graph for region navigation.
    # The frontend filters out inaccessible location rows using accessible_locations.
    world_graph = build_world_graph(registry=registry)
    region_graph = RegionGraphRead(
        nodes=[RegionGraphNode(id=n.id, label=n.label, kind=n.kind) for n in world_graph.nodes],
        edges=[RegionGraphEdge(source=e.source, target=e.target, label=e.label) for e in world_graph.edges],
    )

    return OverworldStateRead(
        character_id=character_id,
        accessible_locations=accessible_locations,
        region_graph=region_graph,
    )
```

The `POST /navigate` route handler is deleted entirely.

---

### `oscilla/routers/play.py`

#### Remove `begin_adventure` and `BeginAdventureRequest`; add `GoAdventureRequest` and `go_adventure`

**Before (`begin_adventure` — full function):**

```python
class BeginAdventureRequest(BaseModel):
    adventure_ref: str = Field(description="Adventure manifest name to begin.")


@router.post("/characters/{character_id}/play/begin")
async def begin_adventure(
    character_id: UUID,
    body: BeginAdventureRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
    request: Request,
) -> StreamingResponse:
    iteration, registry = await _require_character_and_registry(
        character_id=character_id, user=user, db=db, request=request
    )

    token = str(uuid4())
    conflict_dt = await acquire_web_session_lock(
        session=db,
        iteration_id=iteration.id,
        token=token,
        stale_threshold_minutes=_settings.stale_session_threshold_minutes,
    )
    if conflict_dt is not None:
        raise HTTPException(
            status_code=409,
            detail=SessionConflictRead(...).model_dump(mode="json"),
        )

    if registry.adventures.get(body.adventure_ref) is None:
        await release_web_session_lock(session=db, iteration_id=iteration.id, token=token)
        raise HTTPException(status_code=422, detail=f"Unknown adventure '{body.adventure_ref}'.")

    state = await load_character(...)
    if state is None:
        await release_web_session_lock(session=db, iteration_id=iteration.id, token=token)
        raise HTTPException(status_code=404, detail="Character not found.")

    await clear_session_output(session=db, iteration_id=iteration.id)

    location_ref = state.current_location
    # ... resolve location_name, region_name from state.current_location ...

    web_cb = WebCallbacks(location_ref=location_ref, ...)
    pipeline = AdventurePipeline(...)

    return StreamingResponse(
        _run_pipeline_and_stream(..., adventure_ref=body.adventure_ref, ...),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**After (`go_adventure`):**

```python
class GoAdventureRequest(BaseModel):
    location_ref: str = Field(description="Location ref to begin an adventure from.")


@router.post("/characters/{character_id}/play/go")
async def go_adventure(
    character_id: UUID,
    body: GoAdventureRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
    request: Request,
) -> StreamingResponse:
    """Select and begin an adventure via weighted random from the location's eligible pool.

    Steps:
    1. Validate location exists in the registry (422 if not).
    2. Load character state (404 if not found).
    3. Validate location is accessible to this character via unlock conditions (422 if not).
    4. Build eligible pool: adventures whose `requires` conditions pass and repeat controls allow.
    5. Return 422 if pool is empty.
    6. Select one adventure via weighted random — result is never revealed to the client.
    7. Acquire session lock (409 if already held).
    8. Stream the adventure as SSE.
    """
    iteration, registry = await _require_character_and_registry(
        character_id=character_id, user=user, db=db, request=request
    )

    # 1. Validate location exists in the registry.
    loc = registry.locations.get(body.location_ref)
    if loc is None:
        raise HTTPException(status_code=422, detail=f"Unknown location '{body.location_ref}'.")

    if registry.character_config is None:
        raise HTTPException(status_code=500, detail="Game not configured.")

    # 2. Load character state (required to evaluate unlock conditions and adventure eligibility).
    state = await load_character(
        session=db,
        character_id=character_id,
        character_config=registry.character_config,
        registry=registry,
    )
    if state is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    # 3. Validate the location is accessible to this character.
    #    Unlock conditions may reference character stats, so the full state is required.
    if not evaluate(loc.spec.effective_unlock, state, registry):
        raise HTTPException(status_code=422, detail=f"Location '{body.location_ref}' is not accessible.")

    # 4. Build the eligible pool: same filter as the TUI (conditions + repeat controls).
    now_ts = int(_time.time())
    eligible = [
        entry
        for entry in loc.spec.adventures
        if evaluate(entry.requires, state, registry)
        and state.is_adventure_eligible(
            adventure_ref=entry.ref,
            spec=registry.adventures.require(entry.ref, "Adventure").spec,
            now_ts=now_ts,
        )
    ]

    if not eligible:
        raise HTTPException(status_code=422, detail="No adventures are available at this location right now.")

    weights = [entry.weight for entry in eligible]
    (chosen_entry,) = random.choices(population=eligible, weights=weights, k=1)
    adventure_ref = chosen_entry.ref

    # Acquire lock and begin the adventure pipeline.
    token = str(uuid4())
    conflict_dt = await acquire_web_session_lock(
        session=db,
        iteration_id=iteration.id,
        token=token,
        stale_threshold_minutes=_settings.stale_session_threshold_minutes,
    )
    if conflict_dt is not None:
        raise HTTPException(
            status_code=409,
            detail=SessionConflictRead(
                detail="A live session is already in progress.",
                acquired_at=conflict_dt,
                character_id=character_id,
            ).model_dump(mode="json"),
        )

    await clear_session_output(session=db, iteration_id=iteration.id)

    # Resolve location context for SSE event metadata.
    region = registry.regions.get(loc.spec.region)
    web_cb = WebCallbacks(
        location_ref=body.location_ref,
        location_name=loc.spec.displayName,
        region_name=region.spec.displayName if region is not None else None,
    )
    persist_cb = WebPersistCallback(
        db_session=db,
        iteration_id=iteration.id,
        initial_state=state,
        character_config=registry.character_config,
        registry=registry,
    )
    pipeline = AdventurePipeline(
        registry=registry,
        player=state,
        tui=web_cb,
        on_state_change=persist_cb,
    )

    return StreamingResponse(
        _run_pipeline_and_stream(
            pipeline=pipeline,
            web_cb=web_cb,
            db=db,
            iteration_id=iteration.id,
            adventure_ref=adventure_ref,
            session_token=token,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

`BeginAdventureRequest` and `begin_adventure` are deleted. The `_run_pipeline_and_stream` helper, `advance_adventure`, and all other play endpoints are unchanged.

---

### `oscilla/engine/character.py`

Remove `current_location: str | None` from `CharacterState`. Remove it from:

- The dataclass field definition
- `create_initial_state()` default construction
- `to_save_dict()` serialization
- `from_save_dict()` deserialization

---

### `oscilla/engine/steps/effects.py`

Remove the `SetLocationEffect` handler. The relevant block sets `player.current_location`; delete it entirely.

---

### `oscilla/engine/models/adventure.py`

Remove the `SetLocationEffect` model class (currently `class SetLocationEffect(BaseModel): ...` with `type: Literal["set_location"]` and `location: str | None`). Remove it from the `Effect` union type alias.

---

### `oscilla/models/character_iteration.py`

Remove `current_location: Mapped[str | None] = mapped_column(String, nullable=True)`.

---

### `oscilla/models/api/characters.py`

Remove `current_location: str | None` and `current_location_name: str | None` from `CharacterRead`. Remove the helper code that resolves `current_location_name` from the registry.

---

### `oscilla/services/character.py`

Remove all references to `current_location`:

- The `current_location=state.current_location` line in the character save path
- The `"current_location": iteration.current_location` line in the load path

---

### `db/versions/` — Alembic migration

Create a new migration to drop `character_iterations.current_location`:

```python
def upgrade() -> None:
    op.drop_column("character_iterations", "current_location")


def downgrade() -> None:
    op.add_column(
        "character_iterations",
        sa.Column("current_location", sa.String(), nullable=True),
    )
```

---

### `frontend/src/lib/api/types.ts`

**Remove:**

- `AdventureOptionRead` interface
- `NavigateRequest` interface
- `current_location`, `current_location_name`, `current_region_name`, `available_adventures`, `navigation_options` from `OverworldStateRead`

**Add to `OverworldStateRead`:**

```typescript
export interface LocationOptionRead {
  ref: string;
  display_name: string;
  region_ref: string;
  region_name: string;
  adventures_available: boolean;
}

export interface OverworldStateRead {
  character_id: string;
  accessible_locations: LocationOptionRead[];
  region_graph: RegionGraphRead;
}
```

Also remove `current_location` and `current_location_name` from `CharacterRead`.

---

### `frontend/src/lib/api/play.ts` (or overworld API client)

Remove the `navigate(characterId, locationRef)` function. Add:

```typescript
/**
 * POST /characters/{id}/play/go
 * Takes a location_ref; returns an SSE stream. The adventure selection is server-side.
 */
export async function* beginAdventureGo(
  characterId: string,
  locationRef: string,
): AsyncGenerator<SSEEvent> {
  yield* fetchSSE(
    `/api/characters/${encodeURIComponent(characterId)}/play/go`,
    {
      method: "POST",
      body: JSON.stringify({ location_ref: locationRef }),
    },
  );
}
```

---

### `frontend/src/lib/components/Overworld/AdventureList.svelte`

**Deleted.** No replacement component; the Begin Adventure button is inlined in `OverworldView.svelte`.

---

### `frontend/src/lib/components/Overworld/OverworldView.svelte`

Rebuilt to implement **hierarchical region navigation**. The component stores `currentRegion: string | null` in local Svelte `$state`. This value is never sent to the server; it is purely a UI affordance.

**Navigation model:**

- When `currentRegion` is `null` (the world map view), render all root regions simultaneously. This is always the starting state and is always reachable via the back button.
- When `currentRegion` is set, render its direct children from `region_graph` edges:
  - Region-kind children → rendered as navigation buttons that update `currentRegion`.
  - Location-kind children that are in `accessible_locations` → rendered as location rows with a Begin Adventure button (disabled state when `loc.adventures_available === false`).
- A back button navigates to the parent region. From a root region, back returns to `null` (the world map).

```svelte
<script lang="ts">
  import type { OverworldStateRead, LocationOptionRead } from '$lib/api/types';

  interface Props {
    characterId: string;
    overworldState: OverworldStateRead | null;
    onBeginAdventure: (locationRef: string) => void;
  }

  let { characterId, overworldState, onBeginAdventure }: Props = $props();

  // UI-only navigation state — never sent to server.
  // null = world map view (all root regions shown simultaneously).
  let currentRegion = $state<string | null>(null);

  // Build a child lookup from the region_graph edges.
  const childrenOf = $derived.by(() => {
    if (!overworldState) return new Map<string, string[]>();
    const map = new Map<string, string[]>();
    for (const edge of overworldState.region_graph.edges) {
      const list = map.get(edge.source) ?? [];
      list.push(edge.target);
      map.set(edge.source, list);
    }
    return map;
  });

  // Root regions: region-kind nodes with no incoming edges from other regions.
  const rootRegions = $derived.by(() => {
    if (!overworldState) return [];
    const allTargets = new Set(overworldState.region_graph.edges.map(e => e.target));
    return overworldState.region_graph.nodes.filter(
      n => n.kind === 'region' && !allTargets.has(n.id)
    );
  });

  // Nodes visible in the current view.
  const currentChildren = $derived.by(() => {
    if (!overworldState) return [];
    const nodeIds = currentRegion ? (childrenOf.get(currentRegion) ?? []) : rootRegions.map(r => r.id);
    return nodeIds.map(id => overworldState.region_graph.nodes.find(n => n.id === id)).filter(Boolean);
  });

  // Accessible location index for fast lookup.
  const accessibleIndex = $derived(
    new Map(overworldState?.accessible_locations.map(l => [l.ref, l]) ?? [])
  );

  function enterRegion(regionId: string) {
    currentRegion = regionId;
  }

  function goBack() {
    if (!overworldState || !currentRegion) return;
    // Find the parent of currentRegion.
    const parent = overworldState.region_graph.edges.find(e => e.target === currentRegion)?.source ?? null;
    currentRegion = parent;
  }
</script>

{#if overworldState === null}
  <LoadingSpinner />
{:else}
  {#if currentRegion !== null}
    <Button variant="ghost" onclick={goBack}>← Back</Button>
  {/if}
  <ul class="region-contents">
    {#each currentChildren as node (node.id)}
      {#if node.kind === 'region'}
        <li class="region-item">
          <Button variant="secondary" onclick={() => enterRegion(node.id)}>{node.label}</Button>
        </li>
      {:else}
        {@const loc = accessibleIndex.get(node.id)}
        {#if loc}
          <li class="location-item">
            <span class="location-name">{loc.display_name}</span>
            <Button
              variant="primary"
              disabled={!loc.adventures_available}
              onclick={() => onBeginAdventure(loc.ref)}
            >
              Begin Adventure
            </Button>
          </li>
        {/if}
      {/if}
    {/each}
  </ul>
{/if}
```

Note: If `loc.adventures_available` is `false` the button is rendered disabled. No message explaining why is shown (that would leak information about adventure eligibility conditions).

---

### `frontend/src/routes/play/[id]/+page.svelte` (play route)

The `onBeginAdventure` handler currently calls `gameSession.begin(character.id, adventureRef)`. It is updated to call `gameSession.go(character.id, locationRef)`, which calls `beginAdventureGo(characterId, locationRef)`.

The navigate call (previously triggered when a user selected a location) is removed entirely.

---

## Documentation Plan

| Document                                       | Audience           | Topics                                                                                                                                                                                                                                                                                                             |
| ---------------------------------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docs/dev/api.md` (update)                     | Backend developers | Remove navigate endpoint section; remove `available_adventures` and `current_location*` from `OverworldStateRead` table; add `accessible_locations` and `region_graph`; add `POST /play/go` section with request body, responses (200 SSE, 409, 422 variants), error conditions; remove `POST /play/begin` section |
| `openspec/specs/web-overworld/spec.md` (delta) | Internal spec      | New `OverworldStateRead` schema; navigate endpoint removed; `OverworldView` renders location list                                                                                                                                                                                                                  |
| `openspec/specs/web-play-go/spec.md` (new)     | Internal spec      | Full spec for `POST /play/go`: `location_ref` in body, eligibility filter, weighted selection, 422 conditions, 409, SSE response                                                                                                                                                                                   |

---

## Testing Philosophy

### Tier 1 — Engine unit tests

No new unit tests required. The eligibility filter in `go_adventure` reuses `evaluate` and `is_adventure_eligible`, which are already covered.

### Tier 2 — Router integration tests (TestClient + SQLite)

**`tests/routers/test_overworld.py` — modified:**

All existing tests that reference `available_adventures`, `current_location`, or the navigate endpoint must be updated or removed:

- Replace navigate-then-check-state tests with assertions on `accessible_locations` content.
- Remove assertions on `available_adventures` entirely.
- Remove navigate-endpoint tests (`POST /navigate`).

**`tests/routers/test_play.py` — rewritten:**

All existing tests in this file call `POST /play/begin` with an explicit `adventure_ref`. Every test must be restructured to call `POST /play/go` with a `location_ref`. The test fixtures must ensure the relevant location has the desired adventure in its pool. Key scenarios:

1. `test_go_adventure_streams_sse` — `POST /play/go` with a location that has eligible adventures returns 200 `text/event-stream` with at least one event.
2. `test_go_adventure_422_unknown_location` — unknown `location_ref` returns 422.
3. `test_go_adventure_422_locked_location` — locked location returns 422.
4. `test_go_adventure_422_empty_pool` — location with no eligible adventures returns 422.
5. `test_go_adventure_409_lock_held` — lock held returns 409.
6. `test_go_adventure_404_other_user` — other user's character returns 404.
7. Advance and full-flow tests (choice, narrative, ack) are updated to use `/play/go` to start.

### Tier 3 — Frontend component tests (Vitest)

- Delete `AdventureList.test.ts` if it exists.
- Update `OverworldView.test.ts`: replace adventure-card assertions with region-navigation assertions. Add test: two disconnected root regions → both rendered in null state, no back button; entering a region → its children shown, back button present. Add test: location with `adventures_available: false` → Begin Adventure button disabled. Add test: location with `adventures_available: true` → clicking calls `onBeginAdventure(loc.ref)`.

### Tier 4 — End-to-end tests (Playwright)

The existing E2E suite must be updated to reflect the new flow. The old flow navigated to a location, selected an adventure from a list, then played it. The new flow navigates through regions to a location and clicks a single Begin Adventure button. Key scenarios:

1. **Overworld region navigation** — starting from the world map, navigate into a region, verify locations appear; use back button to return to world map and verify root regions reappear.
2. **Begin Adventure from overworld** — click Begin Adventure at an accessible location, verify the play view loads and the adventure stream begins.
3. **Disabled Begin Adventure** — for a location where all adventures are on cooldown or conditions fail, verify the button is present but disabled and cannot be clicked.

These tests do not reference adventure names or refs at any point, consistent with the spoiler-free design.

### Tier 5 — Accessibility tests (Playwright a11y)

Run `make frontend_a11y` after the component changes. Key checks:

1. **Region navigation buttons** — must have accessible labels (region display names). Verify no unlabeled `<button>` elements in the overworld.
2. **Disabled Begin Adventure button** — must use the `disabled` attribute (not just a visual style), so screen readers announce it as unavailable. The button label must not change based on availability state (no "No adventures available" text substitution that would leak information).
3. **Back button** — must have a clear accessible label. The `← Back` text is sufficient; verify it is not icon-only.
4. **Loading state** — the `LoadingSpinner` must have an appropriate `aria-label` or `role="status"` so assistive technology announces the loading state.

---

## Risks / Trade-offs

| Risk                                                                                                                                                               | Mitigation                                                                                                                                                                |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Character state is loaded before the lock is acquired in `go_adventure`; a concurrent request could modify state between load and lock                             | Pool selection is idempotent — if the pool was eligible at load time and becomes empty by lock time, the adventure pipeline will fail gracefully. Acceptable race window. |
| Weighted random selection is non-deterministic                                                                                                                     | Tests assert that _an_ adventure starts, not _which_ one. This is the correct invariant.                                                                                  |
| Existing content using `SetLocationEffect` will break                                                                                                              | Content must be audited and the effect removed from any YAML that uses it. Task covers this.                                                                              |
| `_build_overworld_state` evaluates the full eligible pool for every accessible location on every overworld fetch; at large scale this is O(locations × adventures) | Acceptable for current game scale. If it becomes a bottleneck, a per-location eligibility cache keyed on character state hash can be introduced later.                    |
| Refreshing the page resets `currentRegion` to null in the frontend                                                                                                 | Intentional; region navigation is ephemeral UI state. No action needed.                                                                                                   |

---

## Migration Plan

This is a breaking API change deployed atomically with the frontend (monorepo). No version skew risk.

1. Remove `current_location` column via Alembic migration on deploy.
2. Deploy backend (overworld router + play router + engine changes).
3. Deploy frontend (types, API client, OverworldView, remove AdventureList).
4. No persistent frontend state stores the overworld shape; no cache invalidation needed.

Rollback: revert migration and both code changes together.
