## Context

The character state endpoint (`GET /characters/{id}`) is the primary data contract between the backend and the frontend. It assembles a `CharacterStateRead` response in `build_character_state_read()` inside `oscilla/models/api/characters.py`. The overworld endpoint (`GET /characters/{id}/overworld`) assembles `OverworldStateRead` in `oscilla/routers/overworld.py`.

Several problems have accumulated across these two endpoints:

1. **Raw refs instead of display metadata.** Sub-models for items, buffs, quests, archetypes, and the active adventure return only the manifest `ref` key. The frontend has no choice but to display internal identifiers to players. All manifest kinds (`ItemSpec`, `SkillSpec`, `BuffSpec`, `QuestSpec`, `ArchetypeSpec`, `AdventureSpec`, `LocationSpec`, `RegionSpec`) already carry `displayName: str` and `description: str = ""` — the engine models are complete. The API layer never reads them.

2. **Hidden stats leak.** `build_character_state_read()` builds the stats map from `public_stats + hidden_stats`. Hidden stats are bookkeeping values (cooldown counters, internal flags) that content authors explicitly exclude from the visible game model. They must not appear in the player-facing API response.

3. **Dead `character_class` field.** `CharacterState.character_class` is initialized to `None`, never assigned any other value anywhere in the engine, and propagated through serialization/deserialization, session diff blocks, and the ORM model. It was scaffolded for a feature that was never built and has no place in the current author-defined vocabulary system (archetypes serve that purpose).

4. **Missing `updated_at` on `CharacterSummaryRead`.** `CharacterRecord` already has an `updated_at` column with `onupdate=lambda: datetime.now(tz=timezone.utc)`. The summary response omits it, so clients cannot display a "last played" date on character selection screens.

5. **No defense against in-adventure state mutations.** The `PATCH /characters/{id}` and `DELETE /characters/{id}` routes can be called while a character has an active web session lock. The play router (`go`, `advance`, `abandon`) serializes state at the end of each step; a concurrent mutation could be silently overwritten. The guard should check whether `session_token` is set on the active `CharacterIterationRecord`.

6. **Overworld missing descriptions.** `LocationOptionRead` has `display_name` but no `description`. `RegionGraphNode` has `label` (which maps to `displayName`) but no `description`. Both spec models have the field populated by content authors.

This change resolves all six issues in a single pass so the API becomes a consistent, complete representation of the content package data model.

---

## Goals / Non-Goals

**Goals:**

- All sub-models in `CharacterStateRead` carry `display_name: str | None` and `description: str | None` populated from the content registry.
- `SkillRead` additionally carries `on_cooldown: bool` and `cooldown_remaining_ticks: int | None` from `CharacterState.skill_tick_expiry`.
- `ActiveQuestRead` carries three display fields: `quest_display_name`, `quest_description`, and `stage_description`.
- Hidden stats are excluded from the API `stats` map.
- `CharacterSummaryRead` includes `updated_at`.
- `character_class` is fully removed from the engine, ORM, serialization, and API.
- `LocationOptionRead` and `RegionGraphNode` carry `description: str | None`.
- A new reusable `require_no_active_adventure` FastAPI dependency blocks state-mutating character routes when a session lock is live.
- The Alembic migration drops `character_iterations.character_class`.
- All test fixtures that reference `character_class` are updated.
- Testlandia content demonstrates all new fields for manual QA.

**Non-Goals:**

- Adding description fields to `MilestoneRead` — milestones are string keys with no manifest kind and no registry entry.
- Exposing adventure lists per location — adventure names and descriptions are spoilers.
- Adding a description to `completed_quests` or `failed_quests` lists — these are ref-only by design (terminal state).
- Changing any play-router logic — the guard is applied to non-play mutating routes only.
- Adding region descriptions to a separate first-class region endpoint — the existing `RegionGraphNode` enrichment is sufficient.

---

## Decisions

### D1: Single assembly pass in `build_character_state_read()`

**Decision:** All display metadata lookups happen inline in the existing `build_character_state_read()` function. No new service layer, no lazy loading, no pre-fetch step.

**Rationale:** The function already holds a `ContentRegistry` reference. Registry lookups are O(1) dict lookups on pre-loaded in-memory data — there is no I/O cost. Adding a new service layer or caching layer would be over-engineering for operations that are already memory-resident.

**Alternative considered:** Pre-fetch all referenced manifests before building the read model (batch lookup). Rejected because the registry is already fully loaded in memory; a pre-fetch pass would add complexity with no performance benefit.

---

### D2: `str | None` for all display fields, never blank string

**Decision:** `display_name: str | None` and `description: str | None` default to `None` in the Pydantic models. When the registry lookup succeeds, an empty-string description is normalized to `None` (i.e., `description or None`).

**Rationale:** Blank strings and `None` have different semantics on the frontend. `None` unambiguously means "no description available; do not render a description element." An empty string would require every client to add `if description` checks or render empty containers.

**Alternative considered:** Always return an empty string. Rejected because it pushes the null-check burden to every consumer.

---

### D3: `on_cooldown: bool` + `cooldown_remaining_ticks: int | None` in `SkillRead`

**Decision:** Expose cooldown state as a boolean flag plus an optional remaining-tick count. `on_cooldown` is `True` when `skill_tick_expiry[ref] > state.internal_ticks`. `cooldown_remaining_ticks` is `skill_tick_expiry[ref] - state.internal_ticks` when on cooldown, else `None`.

**Rationale:** `on_cooldown` is the field a frontend rendering loop needs; `cooldown_remaining_ticks` allows displaying a countdown without client-side arithmetic. Real-time expiry (`skill_real_expiry`) is not exposed in this change — tick-based is sufficient for all current skill types.

**Alternative considered:** Exposing raw `tick_expiry` and `real_expiry` values. Rejected because they require clients to know `internal_ticks` to compute remaining time, and they leak engine internals.

---

### D4: Three-layer quest metadata in `ActiveQuestRead`

**Decision:** `ActiveQuestRead` gains three new fields: `quest_display_name: str | None`, `quest_description: str | None`, and `stage_description: str | None`. The frontend can choose which to render.

**Rationale:** `QuestSpec` has `displayName` and `description` at the top level, and each `QuestStage` has its own `description`. Clients need all three to build a quest-tracker panel (quest name in header, quest description in tooltip, current stage progress text in body). Collapsing them into a single field would require either server-side string interpolation (fragile) or client-side re-lookup (impossible — clients do not have the content registry).

**Alternative considered:**

- Option A: Quest name only. Rejected — no stage context.
- Option B: Quest name + stage description only. Rejected — no overall quest description.
- Option C (chosen): All three layers.

---

### D5: `require_no_active_adventure` as a FastAPI dependency with a structured 409 body

**Decision:** Implement the guard as a standard FastAPI `Depends` function that accepts `character_id: UUID`, `db: AsyncSession`, and `current_user`. It calls `get_active_iteration_record()`, checks `session_token is not None`, and raises `HTTPException(status_code=409)` with a structured `detail` dict when a lock is live.

The guard is applied **only to `PATCH /characters/{id}`** (rename/update). `DELETE /characters/{id}` is deliberately excluded: a player choosing to delete a character owns that decision outright, regardless of whether that character is mid-adventure. Blocking deletion would trap players who simply want to remove a stuck or unwanted character. The guard is not a character-ownership check — it exists only to prevent silent state corruption from concurrent mutations on a character whose engine state is actively being written by the play router.

Note that players may have multiple characters. Switching to a different character while one is in an active adventure is permitted — only mutations to the specific character that holds a live session lock are blocked. When a player returns to the locked character they will still be in their adventure.

**Rationale:** FastAPI's dependency injection system is the idiomatic way to add cross-cutting request-level checks. Placing the guard in `oscilla/dependencies/` follows the existing pattern for shared dependencies (auth, DB session). The guard is stateless and has a single DB round-trip; it does not require a cache or background task. A structured body (rather than a plain string) is required so the frontend can act on the response — a string detail gives the user no route forward.

**Alternative considered:** Check in each route handler body. Rejected — repeated code in every handler, easy to omit from future routes.

**Alternative considered:** Return a `303 See Other` redirect to the play endpoint. Rejected — redirects are not idiomatic for mutation-blocked API responses and require CORS-safe redirect handling on the frontend.

---

### D6: Remove `character_class` entirely, no deprecation period

**Decision:** Delete `character_class` from all layers simultaneously. No null-passthrough or deprecation shim.

**Rationale:** The field has always been `None`. Clients that read it today receive `null` and must already handle that case. There is no observable behavior change for any current consumer. A deprecation period adds maintenance burden with zero benefit.

---

### D7: Filter hidden stats server-side, not client-side

**Decision:** Only `public_stats` are included in the `stats` map returned by the API. Hidden stats never appear in the response body.

**Rationale:** Client-side filtering would require clients to know the hidden-stat list (available only from the content registry, which is server-side). Server-side filtering is the only viable option. Hidden stat names must remain available to the engine at all times — filtering happens only in the serialization layer.

---

### D8: Warn on empty `description` for API-exposed manifest kinds

**Decision:** Add a new `_check_missing_descriptions()` function to `oscilla/engine/semantic_validator.py` that emits a `SemanticIssue` with `severity="warning"` and `kind="missing_description"` for every manifest of an API-exposed kind whose `spec.description` is an empty string. The eight checked kinds are: `Adventure`, `Item`, `Skill`, `Buff`, `Quest`, `Archetype`, `Location`, and `Region`. Enemies, loot tables, and recipes are not checked — they are not directly surfaced by the character-state or overworld APIs.

**Rationale:** Now that `description` is forwarded to the frontend via `str | None` (empty strings are normalized to `None`), an empty description means the frontend receives `null` and silently omits the element. This is easy to miss during authoring because `description` defaults to `""`. The semantic validator is the right tier for this check: it fires post-load against a complete registry, costs nothing (all data is in memory), and surfaces through `oscilla validate` as a yellow warning without blocking the game. `displayName` already has no default and is enforced as a required field by Pydantic schema validation; no additional warning is needed for it.

**Alternative considered:** Emit the warning from the loader (`_validate_*` functions in `loader.py`) against the raw `ManifestEnvelope` list. Rejected — the loader warning helpers are tightly scoped to structural issues (label declarations, passive effect conditions, trigger refs). A "content quality" check belongs in the semantic validator alongside similar completeness checks.

---

## Implementation Sketch

### `oscilla/models/api/characters.py` — sub-model changes

**Before (selected models):**

```python
class StackedItemRead(BaseModel):
    ref: str = Field(description="Item manifest reference.")
    quantity: int = Field(description="Number of this item in the stack.")

class ItemInstanceRead(BaseModel):
    instance_id: UUID = Field(description="Unique instance identifier.")
    item_ref: str = Field(description="Item manifest reference.")
    charges_remaining: int | None = Field(default=None, ...)
    modifiers: Dict[str, int] = Field(default_factory=dict, ...)

class SkillRead(BaseModel):
    ref: str = Field(description="Skill manifest reference.")
    display_name: str | None = Field(default=None, ...)

class BuffRead(BaseModel):
    ref: str = Field(description="Buff manifest reference.")
    remaining_turns: int | None = Field(...)
    tick_expiry: int | None = Field(...)
    game_tick_expiry: int | None = Field(...)
    real_ts_expiry: int | None = Field(...)

class ActiveQuestRead(BaseModel):
    ref: str = Field(description="Quest manifest reference.")
    current_stage: str = Field(description="Current stage name within the quest.")

class ArchetypeRead(BaseModel):
    ref: str = Field(description="Archetype manifest reference.")
    grant_tick: int = Field(...)
    grant_timestamp: int = Field(...)

class ActiveAdventureRead(BaseModel):
    adventure_ref: str = Field(description="Adventure manifest reference.")
    step_index: int = Field(description="Current step index within the adventure.")
```

**After:**

```python
class StackedItemRead(BaseModel):
    ref: str = Field(description="Item manifest reference.")
    quantity: int = Field(description="Number of this item in the stack.")
    display_name: str | None = Field(default=None, description="Human-readable item name.")
    description: str | None = Field(default=None, description="Item description.")

class ItemInstanceRead(BaseModel):
    instance_id: UUID = Field(description="Unique instance identifier.")
    item_ref: str = Field(description="Item manifest reference.")
    charges_remaining: int | None = Field(default=None, ...)
    modifiers: Dict[str, int] = Field(default_factory=dict, ...)
    display_name: str | None = Field(default=None, description="Human-readable item name.")
    description: str | None = Field(default=None, description="Item description.")

class SkillRead(BaseModel):
    ref: str = Field(description="Skill manifest reference.")
    display_name: str | None = Field(default=None, description="Human-readable skill name.")
    description: str | None = Field(default=None, description="Skill description.")
    on_cooldown: bool = Field(default=False, description="True if the skill is currently on cooldown.")
    cooldown_remaining_ticks: int | None = Field(
        default=None,
        description="Internal ticks remaining on the cooldown, if on cooldown.",
    )

class BuffRead(BaseModel):
    ref: str = Field(description="Buff manifest reference.")
    remaining_turns: int | None = Field(...)
    tick_expiry: int | None = Field(...)
    game_tick_expiry: int | None = Field(...)
    real_ts_expiry: int | None = Field(...)
    display_name: str | None = Field(default=None, description="Human-readable buff name.")
    description: str | None = Field(default=None, description="Buff description.")

class ActiveQuestRead(BaseModel):
    ref: str = Field(description="Quest manifest reference.")
    current_stage: str = Field(description="Current stage name within the quest.")
    quest_display_name: str | None = Field(default=None, description="Human-readable quest name.")
    quest_description: str | None = Field(default=None, description="Quest-level description.")
    stage_description: str | None = Field(default=None, description="Description of the current stage.")

class ArchetypeRead(BaseModel):
    ref: str = Field(description="Archetype manifest reference.")
    grant_tick: int = Field(...)
    grant_timestamp: int = Field(...)
    display_name: str | None = Field(default=None, description="Human-readable archetype name.")
    description: str | None = Field(default=None, description="Archetype description.")

class ActiveAdventureRead(BaseModel):
    adventure_ref: str = Field(description="Adventure manifest reference.")
    step_index: int = Field(description="Current step index within the adventure.")
    display_name: str | None = Field(default=None, description="Human-readable adventure name.")
    description: str | None = Field(default=None, description="Adventure description.")
```

### `CharacterStateRead` — remove `character_class`, stats filtering

**Before:**

```python
class CharacterStateRead(BaseModel):
    id: UUID = Field(...)
    name: str = Field(...)
    game_name: str = Field(...)
    character_class: str | None = Field(default=None, description="Character class, if assigned.")
    prestige_count: int = Field(...)
    ...
```

**After:**

```python
class CharacterStateRead(BaseModel):
    id: UUID = Field(...)
    name: str = Field(...)
    game_name: str = Field(...)
    prestige_count: int = Field(...)
    ...
    # character_class removed — field was never populated; archetypes serve this purpose
```

### `CharacterSummaryRead` — add `updated_at`

**Before:**

```python
class CharacterSummaryRead(BaseModel):
    id: UUID = Field(...)
    name: str = Field(...)
    game_name: str = Field(...)
    prestige_count: int = Field(...)
    created_at: datetime = Field(...)
```

**After:**

```python
class CharacterSummaryRead(BaseModel):
    id: UUID = Field(...)
    name: str = Field(...)
    game_name: str = Field(...)
    prestige_count: int = Field(...)
    created_at: datetime = Field(...)
    updated_at: datetime = Field(description="When the character was last modified.")
```

### `build_character_summary()` — populate `updated_at`

**Before:**

```python
def build_character_summary(record: "CharacterRecord", prestige_count: int) -> CharacterSummaryRead:
    return CharacterSummaryRead(
        id=record.id,
        name=record.name,
        game_name=record.game_name,
        prestige_count=prestige_count,
        created_at=record.created_at,
    )
```

**After:**

```python
def build_character_summary(record: "CharacterRecord", prestige_count: int) -> CharacterSummaryRead:
    return CharacterSummaryRead(
        id=record.id,
        name=record.name,
        game_name=record.game_name,
        prestige_count=prestige_count,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
```

### `build_character_state_read()` — hidden stat filter + full display metadata

**Before (stats block):**

```python
all_stat_defs = char_config.spec.public_stats + char_config.spec.hidden_stats
stats: Dict[str, StatValue] = {}
for stat_def in all_stat_defs:
    value = state.stats.get(stat_def.name)
    stats[stat_def.name] = StatValue(
        ref=stat_def.name,
        display_name=stat_def.description or None,
        value=value,
    )
```

**After (stats block — public only):**

```python
stats: Dict[str, StatValue] = {}
for stat_def in char_config.spec.public_stats:
    value = state.stats.get(stat_def.name)
    stats[stat_def.name] = StatValue(
        ref=stat_def.name,
        display_name=stat_def.description or None,
        value=value,
    )
```

**Before (stacks block):**

```python
stacks: Dict[str, StackedItemRead] = {
    ref: StackedItemRead(ref=ref, quantity=qty) for ref, qty in state.stacks.items()
}
```

**After (stacks block):**

```python
stacks: Dict[str, StackedItemRead] = {}
for ref, qty in state.stacks.items():
    item_manifest = registry.items.get(ref)
    stacks[ref] = StackedItemRead(
        ref=ref,
        quantity=qty,
        display_name=item_manifest.spec.displayName if item_manifest is not None else None,
        description=item_manifest.spec.description or None if item_manifest is not None else None,
    )
```

**Before (instances block):**

```python
for inst in state.instances:
    instance_map[inst.instance_id] = ItemInstanceRead(
        instance_id=inst.instance_id,
        item_ref=inst.item_ref,
        charges_remaining=inst.charges_remaining,
        modifiers=dict(inst.modifiers),
    )
```

**After (instances block):**

```python
for inst in state.instances:
    item_manifest = registry.items.get(inst.item_ref)
    instance_map[inst.instance_id] = ItemInstanceRead(
        instance_id=inst.instance_id,
        item_ref=inst.item_ref,
        charges_remaining=inst.charges_remaining,
        modifiers=dict(inst.modifiers),
        display_name=item_manifest.spec.displayName if item_manifest is not None else None,
        description=item_manifest.spec.description or None if item_manifest is not None else None,
    )
```

**Before (skills block):**

```python
for skill_ref in sorted(state.known_skills):
    skill_manifest = registry.skills.get(skill_ref)
    display_name = skill_manifest.spec.displayName if skill_manifest is not None else None
    skills.append(SkillRead(ref=skill_ref, display_name=display_name))
```

**After (skills block):**

```python
for skill_ref in sorted(state.known_skills):
    skill_manifest = registry.skills.get(skill_ref)
    tick_expiry = state.skill_tick_expiry.get(skill_ref)
    on_cooldown = tick_expiry is not None and tick_expiry > state.internal_ticks
    skills.append(
        SkillRead(
            ref=skill_ref,
            display_name=skill_manifest.spec.displayName if skill_manifest is not None else None,
            description=skill_manifest.spec.description or None if skill_manifest is not None else None,
            on_cooldown=on_cooldown,
            cooldown_remaining_ticks=tick_expiry - state.internal_ticks if on_cooldown else None,
        )
    )
```

**Before (buffs block):**

```python
active_buffs: List[BuffRead] = [
    BuffRead(
        ref=sb.buff_ref,
        remaining_turns=sb.remaining_turns,
        tick_expiry=sb.tick_expiry,
        game_tick_expiry=sb.game_tick_expiry,
        real_ts_expiry=sb.real_ts_expiry,
    )
    for sb in state.active_buffs
]
```

**After (buffs block):**

```python
active_buffs: List[BuffRead] = []
for sb in state.active_buffs:
    buff_manifest = registry.buffs.get(sb.buff_ref)
    active_buffs.append(
        BuffRead(
            ref=sb.buff_ref,
            remaining_turns=sb.remaining_turns,
            tick_expiry=sb.tick_expiry,
            game_tick_expiry=sb.game_tick_expiry,
            real_ts_expiry=sb.real_ts_expiry,
            display_name=buff_manifest.spec.displayName if buff_manifest is not None else None,
            description=buff_manifest.spec.description or None if buff_manifest is not None else None,
        )
    )
```

**Before (quests block):**

```python
active_quests: List[ActiveQuestRead] = [
    ActiveQuestRead(ref=ref, current_stage=stage) for ref, stage in state.active_quests.items()
]
```

**After (quests block):**

```python
active_quests: List[ActiveQuestRead] = []
for ref, stage_name in state.active_quests.items():
    quest_manifest = registry.quests.get(ref)
    stage_description: str | None = None
    if quest_manifest is not None:
        matching_stage = next((s for s in quest_manifest.spec.stages if s.name == stage_name), None)
        stage_description = matching_stage.description or None if matching_stage is not None else None
    active_quests.append(
        ActiveQuestRead(
            ref=ref,
            current_stage=stage_name,
            quest_display_name=quest_manifest.spec.displayName if quest_manifest is not None else None,
            quest_description=quest_manifest.spec.description or None if quest_manifest is not None else None,
            stage_description=stage_description,
        )
    )
```

**Before (archetypes block):**

```python
archetypes: List[ArchetypeRead] = [
    ArchetypeRead(ref=ref, grant_tick=gr.tick, grant_timestamp=gr.timestamp) for ref, gr in state.archetypes.items()
]
```

**After (archetypes block):**

```python
archetypes: List[ArchetypeRead] = []
for ref, gr in state.archetypes.items():
    archetype_manifest = registry.archetypes.get(ref)
    archetypes.append(
        ArchetypeRead(
            ref=ref,
            grant_tick=gr.tick,
            grant_timestamp=gr.timestamp,
            display_name=archetype_manifest.spec.displayName if archetype_manifest is not None else None,
            description=archetype_manifest.spec.description or None if archetype_manifest is not None else None,
        )
    )
```

**Before (active adventure block):**

```python
active_adventure: ActiveAdventureRead | None = None
if state.active_adventure is not None:
    active_adventure = ActiveAdventureRead(
        adventure_ref=state.active_adventure.adventure_ref,
        step_index=state.active_adventure.step_index,
    )
```

**After (active adventure block):**

```python
active_adventure: ActiveAdventureRead | None = None
if state.active_adventure is not None:
    adv_manifest = registry.adventures.get(state.active_adventure.adventure_ref)
    active_adventure = ActiveAdventureRead(
        adventure_ref=state.active_adventure.adventure_ref,
        step_index=state.active_adventure.step_index,
        display_name=adv_manifest.spec.displayName if adv_manifest is not None else None,
        description=adv_manifest.spec.description or None if adv_manifest is not None else None,
    )
```

**Before (`return` statement in `build_character_state_read`):**

```python
return CharacterStateRead(
    ...
    character_class=state.character_class,
    ...
)
```

**After (`return` statement — `character_class` removed):**

```python
return CharacterStateRead(
    id=state.character_id,
    name=record.name,
    game_name=record.game_name,
    prestige_count=state.prestige_count,
    pronoun_set=pronoun_set_key,
    created_at=record.created_at,
    stats=stats,
    stacks=stacks,
    instances=instances,
    equipment=equipment,
    skills=skills,
    active_buffs=active_buffs,
    active_quests=active_quests,
    completed_quests=sorted(state.completed_quests),
    failed_quests=sorted(state.failed_quests),
    milestones=milestones,
    archetypes=archetypes,
    internal_ticks=state.internal_ticks,
    game_ticks=state.game_ticks,
    active_adventure=active_adventure,
)
```

---

### `oscilla/routers/overworld.py` — `LocationOptionRead` and `RegionGraphNode`

**Before:**

```python
class LocationOptionRead(BaseModel):
    ref: str
    display_name: str
    region_ref: str
    region_name: str
    adventures_available: bool

class RegionGraphNode(BaseModel):
    id: str
    label: str
    kind: str
```

**After:**

```python
class LocationOptionRead(BaseModel):
    ref: str
    display_name: str
    region_ref: str
    region_name: str
    adventures_available: bool
    description: str | None = None

class RegionGraphNode(BaseModel):
    id: str
    label: str
    kind: str
    description: str | None = None
```

**Before (`_build_overworld_state` — location append):**

```python
accessible_locations.append(
    LocationOptionRead(
        ref=loc.metadata.name,
        display_name=loc.spec.displayName,
        region_ref=loc.spec.region,
        region_name=region.spec.displayName if region is not None else loc.spec.region,
        adventures_available=_is_any_adventure_eligible(...),
    )
)
```

**After:**

```python
accessible_locations.append(
    LocationOptionRead(
        ref=loc.metadata.name,
        display_name=loc.spec.displayName,
        description=loc.spec.description or None,
        region_ref=loc.spec.region,
        region_name=region.spec.displayName if region is not None else loc.spec.region,
        adventures_available=_is_any_adventure_eligible(...),
    )
)
```

**Before (`_build_overworld_state` — region graph nodes):**

```python
region_graph = RegionGraphRead(
    nodes=[RegionGraphNode(id=n.id, label=n.label, kind=n.kind) for n in world_graph.nodes],
    edges=[RegionGraphEdge(source=e.source, target=e.target, label=e.label) for e in world_graph.edges],
)
```

**After (region descriptions are fetched from the registry, not from `world_graph.nodes` which only carry attrs):**

```python
# Build a ref→description lookup for regions so the graph nodes carry descriptions.
region_descriptions: Dict[str, str | None] = {
    region.metadata.name: region.spec.description or None
    for region in registry.regions.all()
}
region_graph = RegionGraphRead(
    nodes=[
        RegionGraphNode(
            id=n.id,
            label=n.label,
            kind=n.kind,
            # region nodes have id like "region:<ref>"; extract ref for lookup
            description=region_descriptions.get(n.id.removeprefix("region:")) if n.kind == "region" else None,
        )
        for n in world_graph.nodes
    ],
    edges=[RegionGraphEdge(source=e.source, target=e.target, label=e.label) for e in world_graph.edges],
)
```

---

### `oscilla/engine/character.py` — remove `character_class`

Remove the `character_class: str | None` field from the `CharacterState` dataclass, its initialization in `__init__` (set to `None`), its serialization in `serialize()` (key `"character_class"`), and its deserialization in `deserialize()` (read from `data.get("character_class")`).

---

### `oscilla/engine/session.py` — remove `character_class` diffs

**Before (two identical blocks):**

```python
# --- Scalar fields (character_class, pronoun_set) ---
...
if last is None or state.character_class != last.character_class:
    scalar_fields["character_class"] = state.character_class
```

**After:**

```python
# --- Scalar fields (pronoun_set) ---
...
# character_class removed — field is not part of CharacterState
```

---

### `oscilla/engine/steps/effects.py` — prestige reset

**Before:**

```python
player.character_class = None
```

**After:** Remove this line entirely (field no longer exists on `CharacterState`).

---

### `oscilla/services/character.py` — two assignment sites

Remove both `character_class=state.character_class` and `"character_class": iteration.character_class` assignments.

---

### `oscilla/models/character_iteration.py` — ORM column

**Before:**

```python
character_class: Mapped[str | None] = mapped_column(String, nullable=True)
```

**After:** Remove this mapped column.

---

### New: `oscilla/dependencies/adventure_guard.py`

```python
"""FastAPI dependency — blocks state-mutating requests while a session lock is live."""

from logging import getLogger
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from oscilla.dependencies.db import get_db
from oscilla.services.character import get_active_iteration_record

logger = getLogger(__name__)


async def require_no_active_adventure(
    character_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Raise 409 Conflict when the character has a live web session lock.

    Apply to all state-mutating character endpoints outside the play flow.
    The play router manages session locks itself and must not use this guard.

    The 409 detail body is a structured dict so the frontend can redirect the
    user directly to the active adventure:
        {
            "code": "active_adventure",
            "character_id": "<uuid>",
            "adventure_ref": "<ref or null>"
        }
    """
    iteration = await get_active_iteration_record(session=db, character_id=character_id)
    if iteration is not None and iteration.session_token is not None:
        logger.warning(
            "State-mutation blocked for character %s — active session lock held by token %r",
            character_id,
            iteration.session_token,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "active_adventure",
                "character_id": str(character_id),
            },
        )
```

The `code: "active_adventure"` field lets the frontend distinguish this 409 from any other conflict errors. When the frontend receives a 409 with this code, it navigates the user to the play page for the character (`/characters/{id}/play`). The SvelteKit load function on that page calls `getCurrentPlayState` automatically, so no `adventure_ref` is needed in the response — the play page self-recovers.

Apply this dependency to `PATCH /characters/{id}` only in `oscilla/routers/characters.py`. `DELETE /characters/{id}` is intentionally **not** guarded — a player may always delete a character they own, even mid-adventure:

```python
from oscilla.dependencies.adventure_guard import require_no_active_adventure

# DELETE is not guarded — players may always delete their own characters.
@router.delete("/{character_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_character(...) -> None: ...

@router.patch("/{character_id}", response_model=CharacterSummaryRead, dependencies=[Depends(require_no_active_adventure)])
async def update_character(...) -> CharacterSummaryRead: ...
```

---

### `oscilla/engine/semantic_validator.py` — missing description warnings

Add a new private function and register it in `validate_semantic()`:

**Add to `validate_semantic()`:**

```python
def validate_semantic(registry: "ContentRegistry") -> List[SemanticIssue]:
    issues: List[SemanticIssue] = []
    issues.extend(_check_undefined_adventure_refs(registry))
    issues.extend(_check_undefined_enemy_refs(registry))
    issues.extend(_check_undefined_item_refs(registry))
    issues.extend(_check_undefined_skill_refs(registry))
    issues.extend(_check_circular_region_parents(registry))
    issues.extend(_check_orphaned_adventures(registry))
    issues.extend(_check_unreachable_adventures(registry))
    issues.extend(_validate_time_spec(registry))
    issues.extend(_check_missing_descriptions(registry))  # new
    return issues
```

**New function:**

```python
# API-exposed manifest kinds whose description field is player-visible.
# displayName has no default and is already enforced by Pydantic — only description needs a warning.
_DESCRIPTION_CHECKS: List[Tuple[str, str]] = [
    ("adventure", "adventures"),
    ("item", "items"),
    ("skill", "skills"),
    ("buff", "buffs"),
    ("quest", "quests"),
    ("archetype", "archetypes"),
    ("location", "locations"),
    ("region", "regions"),
]


def _check_missing_descriptions(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Warn when an API-exposed manifest kind has no description set.

    An empty description means the API returns null for that field and the
    frontend silently omits it. This is usually an authoring oversight because
    description defaults to an empty string.
    """
    issues: List[SemanticIssue] = []
    for kind_label, registry_attr in _DESCRIPTION_CHECKS:
        kind_registry = getattr(registry, registry_attr)
        for manifest in kind_registry.all():
            if not manifest.spec.description:
                issues.append(
                    SemanticIssue(
                        kind="missing_description",
                        message=f"{kind_label} {manifest.metadata.name!r} has no description",
                        manifest=f"{kind_label}:{manifest.metadata.name}",
                        severity="warning",
                    )
                )
    return issues
```

The `_DESCRIPTION_CHECKS` constant uses `(kind_label, registry_attr)` pairs so the function avoids a chain of `if/elif` blocks and is easy to extend when new API-exposed kinds are added.

The `Tuple` import from `typing` is already present in `semantic_validator.py` (used by other internal helpers); add it to the `from typing import` line if absent.

---

### Alembic migration

A new migration in `db/versions/` drops `character_class` from `character_iterations`. It must work on both SQLite and PostgreSQL.

```python
def upgrade() -> None:
    with op.batch_alter_table("character_iterations") as batch_op:
        batch_op.drop_column("character_class")

def downgrade() -> None:
    with op.batch_alter_table("character_iterations") as batch_op:
        batch_op.add_column(sa.Column("character_class", sa.String(), nullable=True))
```

SQLite requires `batch_alter_table` for column drops; PostgreSQL supports it transparently.

---

### `frontend/src/lib/api/characters.ts` — type guard and 409 handling

FastAPI wraps the `detail` value in a `{ "detail": ... }` envelope. The 409 body that arrives at the frontend is therefore:

```json
{ "detail": { "code": "active_adventure", "character_id": "..." } }
```

`ApiError.body` holds this parsed object. Add a typed interface and a type-guard helper at the top of `characters.ts`:

```typescript
/** Structured body of a 409 Conflict raised by the active-adventure guard. */
export interface ActiveAdventureConflict {
  code: "active_adventure";
  character_id: string;
}

/** Returns true and narrows the type when an ApiError is an active-adventure 409. */
export function isActiveAdventureConflict(
  err: unknown,
): err is ApiError & { body: { detail: ActiveAdventureConflict } } {
  if (!(err instanceof ApiError) || err.status !== 409) return false;
  const body = err.body as Record<string, unknown> | null;
  return (
    body !== null &&
    typeof body === "object" &&
    "detail" in body &&
    typeof (body as Record<string, unknown>)["detail"] === "object" &&
    (body as Record<string, Record<string, unknown>>)["detail"]?.["code"] ===
      "active_adventure"
  );
}
```

Import `ApiError` from `./client.js` for use in the guard.

---

### `frontend/src/routes/characters/[id]/+page.svelte` — 409 redirect on delete and rename

The character sheet page hosts the **rename** (via the `CharacterHeader` component or inline) and **delete** (via a button) actions. Both call the guarded endpoints and must handle the 409.

Add a `handleActiveAdventureConflict` helper inside the `<script>` block:

```typescript
import { isActiveAdventureConflict } from "$lib/api/characters.js";

/**
 * When the backend blocks a mutation because an adventure session is live,
 * redirect the user to the play screen instead of showing an error.
 * Returns true if the error was handled, false if it should propagate.
 */
function handleActiveAdventureConflict(err: unknown): boolean {
  if (!isActiveAdventureConflict(err)) return false;
  // Navigate to the play screen — the adventure state is already loaded there.
  goto(`${base}/characters/${id}/play`);
  return true;
}
```

Apply it in every catch block that wraps a `deleteCharacter` or `renameCharacter` call:

**Before (example delete handler):**

```typescript
async function handleDelete(): Promise<void> {
  try {
    await deleteCharacter(id);
    goto(`${base}/characters`);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to delete character.";
  }
}
```

**After:**

```typescript
async function handleDelete(): Promise<void> {
  try {
    await deleteCharacter(id);
    goto(`${base}/characters`);
  } catch (err) {
    if (!handleActiveAdventureConflict(err)) {
      error =
        err instanceof Error ? err.message : "Failed to delete character.";
    }
  }
}
```

Apply the same pattern to the rename handler. The `goto` call navigates the user directly to the play page; the existing play page loads `GET /characters/{id}/play/current` on mount and resumes the in-progress adventure without requiring an `adventure_ref`.

---

### Testlandia content updates

1. Add a `hidden_stats` entry to `testlandia/character_config.yaml` (e.g., `internal_quest_flag` of type `bool`) to exercise the hidden-stat filter in QA.
2. Ensure all existing items, buffs, quests, skills, archetypes, and adventures in testlandia have `description` fields populated so the new API fields return non-null values during manual testing.
3. Add a skill with an explicit `cooldown` configured to testlandia so `on_cooldown` and `cooldown_remaining_ticks` can be verified.
4. Add `description` to all testlandia locations and regions.

---

## Testing Philosophy

- **Unit tests** for `build_character_state_read()` and `build_character_summary()` use mock `ContentRegistry` and `CharacterRecord`/`CharacterState` instances constructed directly in Python. No YAML loading.
- **Unit tests** for `require_no_active_adventure` use a mock `AsyncSession` that returns an iteration record with and without a `session_token`. Tests verify the 409 is raised when a session lock is live and that the handler proceeds normally when it is not.
- **Integration tests** for the overworld response use the existing `_build_overworld_state` test path with a minimal fixture registry that includes at least one region and one location with descriptions populated.
- **No test may reference `content/`**. All fixtures live in `tests/fixtures/content/<scenario>/`.
- Tests for `character_class` removal verify that deserializing a legacy blob that still contains `"character_class": null` does not raise an error (backward-compatible deserialization with `data.get("character_class")` simply being ignored).
- All 291 existing tests must continue passing after this change.
- **Unit tests for `_check_missing_descriptions`** construct a minimal `ContentRegistry` with one manifest of each checked kind — first with an empty description (expects a warning), then with a non-empty description (expects no warning). Also verify that un-checked kinds (e.g., `Enemy`) do not produce warnings even when their description is empty.
- **Frontend unit tests** (`frontend/src/lib/api/`) verify that `isActiveAdventureConflict` returns `true` only for a 409 `ApiError` with `code: "active_adventure"` in the detail, and `false` for all other errors and status codes.
- **Frontend unit tests** for the character sheet page verify that a delete/rename handler that receives the 409 calls `goto` with the play URL and does not set `error` state.
- **E2E stubs** in `frontend/tests/e2e/characters/sheet.spec.ts` — one `test.skip` scenario: `active_adventure_guard_rename`. The stub documents the exact steps to implement against a live dev stack: establish a character with a live session lock, trigger the rename action, assert the rename did not take effect, and assert navigation to `/characters/{id}/play`. Delete is explicitly not tested here — it is unguarded by design. The stub is skipped until the full game-loop infrastructure (started in the play-screen milestone) is available to hold a session lock open during a test.

---

## Documentation Plan

| Document                                              | Audience            | Topics                                                                                                                                                                                          |
| ----------------------------------------------------- | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/dev/api.md`                                     | Backend developers  | Remove `character_class` from field table; add all new display metadata fields; document `updated_at` on summary; document `require_no_active_adventure` 409 behavior and structured body shape |
| `docs/dev/database.md`                                | Backend developers  | Document `character_iterations.character_class` column removal; migration notes                                                                                                                 |
| `docs/authors/character-config.md` (create if absent) | Content authors     | Document `hidden_stats` vs `public_stats` distinction; explain that hidden stats are engine-internal and never appear in the player-facing API                                                  |
| `docs/dev/frontend.md` (update if exists)             | Frontend developers | Document `isActiveAdventureConflict` type guard; document the redirect pattern for guarded endpoints; list which API calls can return 409 `active_adventure`                                    |

---

## Risks / Trade-offs

- **[Breaking removal of `character_class`]** → Any client that reads `character_class` from the response will receive a missing-field error or silently get `undefined`. Since the field was always `null`, well-behaved clients already handle `null` and a missing field degrades equivalently. No existing testlandia frontend code reads this field.
- **[Hidden stat filter breaks any frontend relying on hidden stats]** → No current frontend component reads hidden stats; they were never documented as player-facing. Risk is low.
- **[`require_no_active_adventure` returns 409 to users in unexpected situations]** → The guard fires only when `session_token is not None`. A stale but non-expired lock would block a `PATCH` or `DELETE`. Mitigation: the structured 409 body directs the frontend to the play screen where the user can use the takeover UI (`POST /play/takeover`) or abandon the adventure as the escape hatch.
- **[Region description ID prefix parsing (`n.id.removeprefix("region:")`))]** → `GraphNode.id` convention is `"kind:name"`. If the convention changes, this parsing breaks. This is a localized coupling inside `_build_overworld_state`; a comment should document the dependency.

## Migration Plan

1. Run `make create_migration MESSAGE="remove character_class from character_iterations"` to generate the Alembic migration file.
2. Review the generated migration; replace the generated `ALTER TABLE` (which does not work on SQLite) with `batch_alter_table` as shown above.
3. Deploy the backend change. The migration runs automatically at startup via `alembic upgrade head` in `docker/www/prestart.sh`.
4. The frontend TypeScript interfaces must be updated in the same PR to remove `character_class` and add all new fields; a partial deploy (backend only) is safe since the frontend falls back gracefully for missing fields.

## Open Questions

- Should `require_no_active_adventure` also be applied to the `DELETE /characters/{id}` endpoint? Resolved: **no**. Players own their characters and may delete them at any time. The guard exists only to prevent players from "cheater" by altering their character while an adventure is ongoing — not to restrict player agency over character management. A player who wants to delete a character that is mid-adventure can do so freely.
- Should `RegionGraphNode` descriptions be added to location nodes as well, or only to region-kind nodes? Current answer: location descriptions are already available via `LocationOptionRead.description`. The region graph is used for navigation UI (region hierarchy), not per-location display — region-kind nodes only.
