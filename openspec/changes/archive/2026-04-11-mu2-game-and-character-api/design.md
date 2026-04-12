# Design: MU2 — Game Discovery & Character Management API

## Context

MU1 introduced authenticated `UserRecord` rows for web users. This change builds the first game-facing API surface on top of that foundation.

Two architectural locks are set here that affect the entire lifetime of the platform:

1. **Content registry startup loading.** The `FastAPI` lifespan handler loads all `ContentRegistry` instances once at startup and stores them in `app.state.registries`. Every subsequent request uses this shared read-only state. This is the only supported access pattern — per-request loading is too slow; hot-reload adds complexity that is not justified at this stage.

2. **`CharacterStateRead` schema lock.** The complete `GET /characters/{id}` response schema is defined here. Adding to a response schema is always non-breaking; removing or renaming fields requires a versioned API. Getting this right in MU2 means no breaking API changes for the lifetime of MU3–MU6.

This change introduces no adventure execution. All character endpoints are either read operations or shallow mutations (create, rename, delete). The pipeline and `CharacterState` engine are not called in this phase; character data is assembled from the DB service layer.

---

## Goals / Non-Goals

**Goals:**

- Content registries loaded at startup via FastAPI lifespan; accessible as `app.state.registries: Dict[str, ContentRegistry]`.
- `GET /games` and `GET /games/{game_name}` with `GameFeatureFlags` derived from `game.yaml`.
- Full character CRUD: `GET /characters`, `POST /characters`, `GET /characters/{id}`, `DELETE /characters/{id}`, `PATCH /characters/{id}`.
- `CharacterStateRead` schema: complete from day one, covering all current fields.
- Character ownership enforcement: authenticated user can only access and mutate their own characters.
- All endpoints protected by `get_current_user` dependency from MU1.

**Non-Goals:**

- Adventure execution (MU3).
- Frontend UI (MU4/MU5).
- Character deletion safety checks beyond ownership (e.g., confirmation tokens) — deferred.
- Pagination of character lists — deferred; player character counts are small.
- Admin character access across users — deferred.

---

## Decisions

### D1: Content registry stored as `app.state.registries: Dict[str, ContentRegistry]`

**Decision:** At app startup, scan `settings.games_path` for all game subdirectories with valid `game.yaml`. Load each as a `ContentRegistry`. Store the resulting dict in `app.state.registries`. All API endpoints that need a registry receive it via a FastAPI dependency:

```python
def get_registry(game_name: str, request: Request) -> ContentRegistry:
    registries: Dict[str, ContentRegistry] = request.app.state.registries
    registry = registries.get(game_name)
    if registry is None:
        raise HTTPException(status_code=404, detail=f"Game '{game_name}' not found.")
    return registry
```

Startup loading is wrapped in the lifespan handler — a load failure for any game logs at ERROR level with a full traceback but does not crash the process. A game with a broken manifest is skipped and absent from `registries`. This is acceptable: the server should not refuse to start because one content package has an authoring error.

**Alternatives considered:**

- `app.state.registries` as a `contextvars.ContextVar` for async-safe access — rejected; the dict is read-only after startup, so plain attribute access on `app.state` is safe for concurrent requests.
- Per-request loading via a generator dependency — rejected; prohibitively slow for content packages with hundreds of manifests.

---

### D2: `GameFeatureFlags` derived from live `ContentRegistry`, not game.yaml fields alone

**Decision:** `GameFeatureFlags` is computed from the loaded `ContentRegistry` — specifically by checking which manifests are non-empty (`len(registry.skills) > 0`, `len(registry.quests) > 0`, etc.). This is more accurate than checking `game.yaml` declarations, because content can declare a feature flag in `game.yaml` while having no actual manifests for it.

```python
@dataclass
class GameFeatureFlags:
    has_skills: bool
    has_quests: bool
    has_factions: bool      # future
    has_archetypes: bool
    has_ingame_time: bool   # true if game.yaml includes a time: block (spec.time is not None)
    has_recipes: bool
    has_loot_tables: bool
```

Frontend panel visibility is driven exclusively by this struct. No frontend logic may hard-code panel presence — it always reads from `GameRead.features`.

**Alternatives considered:**

- Boolean flags explicitly declared in `game.yaml` — rejected. Content authors would need to keep flags in sync with actual manifests; derived flags cannot go stale.

---

### D3: `CharacterStateRead` is the complete contract — all roadmap fields included as stubs

**Decision:** `CharacterStateRead` exposes the full `CharacterState` domain. The schema is never reduced; only extended. Future roadmap features add new fields as they land — the response shape is already Pydantic-extensible with no breaking changes required.

Fields included in MU2 `CharacterStateRead`:

| Category   | Fields                                                                                            |
| ---------- | ------------------------------------------------------------------------------------------------- | ----- |
| Identity   | `id`, `name`, `game_name`, `character_class`, `prestige_count`, `pronoun_set`                     |
| Location   | `current_location` (ref), `current_location_name`, `current_region_name`                          |
| Stats      | `stats: Dict[str, StatValue]` — all stat refs and current values                                  |
| Inventory  | `stacks: Dict[str, StackedItemRead]`, `instances: List[ItemInstanceRead]`                         |
| Equipment  | `equipment: Dict[str, ItemInstanceRead]` — slot → equipped item                                   |
| Skills     | `skills: List[SkillRead]` — ref, display name, cooldown status                                    |
| Buffs      | `active_buffs: List[BuffRead]` — only persistent buffs (encounter-scope are mid-combat)           |
| Quests     | `active_quests: List[ActiveQuestRead]`, `completed_quests: List[str]`, `failed_quests: List[str]` |
| Milestones | `milestones: Dict[str, MilestoneRead]`                                                            |
| Progress   | `internal_ticks`, `game_ticks`                                                                    |
| Archetypes | `archetypes: List[ArchetypeRead]`                                                                 |
| Adventure  | `active_adventure: ActiveAdventureRead                                                            | None` |
| Created    | `created_at`                                                                                      |

The `StatValue` type carries both the current value and whether it was changed this tick (for future highlighting):

```python
class StatValue(BaseModel):
    value: int | bool | None
    ref: str
    display_name: str | None
```

**Alternatives considered:**

- Minimal schema today, extend as features land — acceptable for fields that don't exist yet. New fields added to a Pydantic response model are non-breaking for existing clients. The decision here is not to pre-stub fields but to ensure the schema design (Pydantic, additive-only) makes future extensions non-breaking without coordination costs.

---

### D4: Character creation accepts only the game name

**Decision:** `POST /characters` accepts only `game_name`:

```python
class CharacterCreate(BaseModel):
    game_name: str = Field(description="Game this character belongs to.")
```

The service validates `game_name` against loaded registries, then calls `new_character()` to construct an initial `CharacterState`. `new_character()` applies all defaults declared in `character_config.yaml` and in `character_creation` block of `game.yaml` (`default_name`, `default_pronouns`) automatically. The resulting `CharacterState` is persisted via `save_character()`.

No character attributes — name, pronoun set, archetype, or anything else — are accepted at creation time. If a game wants the player to set a name, choose pronouns, or select a class, content authors implement that as a triggered adventure (using `set_name`, `set_pronouns`, `archetype_add` effects, etc.) that fires when the character first starts playing. This is already supported by the trigger system and is the only supported pattern.

**Alternatives considered:**

- Accept `name` and/or `pronoun_set` in `CharacterCreate` — rejected. `character_creation` defaults in `game.yaml` are always applied unconditionally by `new_character()`. Any player-facing customization belongs in a triggered creation adventure, not in the creation API call. Accepting these fields at the API level would create a second, inconsistent code path that bypasses the content author's authored flow.
- Accept `archetype: str | None` — rejected for the same reason, and additionally because archetype grant logic (`gain_effects`, `GrantRecord`, passive effect application) lives entirely in `run_effect()` and must not be duplicated at the API layer.

---

## File Structure

New files introduced by this change:

```
oscilla/
  routers/
    games.py          — GET /games, GET /games/{game_name}
    characters.py     — GET/POST/DELETE/PATCH /characters, GET /characters/{id}
  models/
    api/
      __init__.py
      games.py        — GameRead, GameFeatureFlags
      characters.py   — CharacterSummaryRead, CharacterStateRead, CharacterCreate,
                         StatValue, StackedItemRead, ItemInstanceRead, SkillRead,
                         BuffRead, ActiveQuestRead, MilestoneRead, ArchetypeRead,
                         ActiveAdventureRead
```

`oscilla/www.py` gains the lifespan content registry loading and mounts the two new routers.

---

## `www.py` Lifespan Changes

```python
from typing import Dict
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.loader import load_from_disk

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_caches()

    # Load all content registries at startup
    registries: Dict[str, ContentRegistry] = {}
    if settings.games_path.exists():
        for game_dir in settings.games_path.iterdir():
            if game_dir.is_dir() and (game_dir / "game.yaml").exists():
                try:
                    registry, warnings = load_from_disk(content_path=game_dir)
                    for warning in warnings:
                        logger.warning("Load warning in %s: %s", game_dir, warning)
                    assert registry.game is not None
                    registries[registry.game.metadata.name] = registry
                    logger.info("Loaded game registry: %s", registry.game.metadata.name)
                except Exception:
                    logger.exception("Failed to load game from %s — skipping.", game_dir)
    app.state.registries = registries

    yield
```

---

## API Endpoints

### Games

| Method | Path                 | Auth     | Response         | Notes                    |
| ------ | -------------------- | -------- | ---------------- | ------------------------ |
| `GET`  | `/games`             | Optional | `List[GameRead]` | Returns all loaded games |
| `GET`  | `/games/{game_name}` | Optional | `GameRead`       | Single game metadata     |

`GameRead`:

```python
class GameRead(BaseModel):
    name: str
    display_name: str
    description: str | None
    features: GameFeatureFlags
```

### Characters

| Method   | Path               | Auth     | Response                     | Notes                                                 |
| -------- | ------------------ | -------- | ---------------------------- | ----------------------------------------------------- |
| `GET`    | `/characters`      | Required | `List[CharacterSummaryRead]` | Filtered to authenticated user; optional `?game=name` |
| `POST`   | `/characters`      | Required | `CharacterSummaryRead`       | Creates character; 201                                |
| `GET`    | `/characters/{id}` | Required | `CharacterStateRead`         | Full state; 404 if not owned                          |
| `DELETE` | `/characters/{id}` | Required | `204`                        | Ownership enforced                                    |
| `PATCH`  | `/characters/{id}` | Required | `CharacterSummaryRead`       | Only `name` field accepted                            |

Ownership enforcement: the service layer always filters by `character.user_id == current_user.id`. Attempting to access another user's character returns `404` (not `403`) to prevent character ID enumeration.

---

## CharacterStateRead Full Schema

```python
class CharacterStateRead(BaseModel):
    # Identity
    id: UUID
    name: str
    game_name: str
    character_class: str | None
    prestige_count: int
    pronoun_set: str
    created_at: datetime

    # Location
    current_location: str | None
    current_location_name: str | None
    current_region_name: str | None

    # Stats (all declared stats, including unset ones as StatValue with value=None)
    stats: Dict[str, StatValue]

    # Inventory
    stacks: Dict[str, StackedItemRead]
    instances: List[ItemInstanceRead]
    equipment: Dict[str, ItemInstanceRead]

    # Skills
    skills: List[SkillRead]

    # Buffs
    active_buffs: List[BuffRead]

    # Quests
    active_quests: List[ActiveQuestRead]
    completed_quests: List[str]
    failed_quests: List[str]

    # Milestones
    milestones: Dict[str, MilestoneRead]

    # Archetypes
    archetypes: List[ArchetypeRead]

    # Progress counters
    internal_ticks: int
    game_ticks: int

    # Adventure state
    active_adventure: ActiveAdventureRead | None
```

The `stats` dict is populated for every stat declared in the game's `character_config.yaml`, including stats whose value is `None`. This means the frontend can render a complete stats panel without knowing the game's stat list ahead of time.

Location name and region name are resolved from the `ContentRegistry` at response assembly time — the DB stores only `current_location` as a ref string; the display names come from the manifest.

---

## Testing Philosophy

- **Unit tests** for `get_registry` dependency: returns registry for known game, raises 404 for unknown game.
- **Integration tests** for all 7 endpoints against an in-memory SQLite test DB, using a minimal in-process content registry (not `content/testlandia/`).
- Character CRUD: create, list, get, rename, delete; ownership enforcement (attempting to get another user's character returns 404).
- `CharacterStateRead` schema completeness: assert all declared fields are present in the response even when empty/null.
- Feature flags: game with no skill manifests returns `has_skills: false`; game with skill manifests returns `has_skills: true`.
- No tests may reference `content/` directory. All registry fixtures are minimal in-memory objects constructed from test data.
- All character test fixtures use the FastAPI `TestClient` with a DB session override following the MU1 test pattern.

---

## Documentation Plan

| Document                           | Audience   | Content                                                                                            |
| ---------------------------------- | ---------- | -------------------------------------------------------------------------------------------------- |
| `docs/dev/api.md` (update)         | Developers | Games endpoints, character endpoints, `CharacterStateRead` field reference, content asset serving  |
| `docs/dev/game-engine.md` (update) | Developers | Content registry startup loading, `app.state.registries` access pattern, `get_registry` dependency |

---

## Risks / Trade-offs

| Risk                                                                      | Mitigation                                                                                                                                                                      |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Content registry load failure at startup silently skips a game            | Logged at ERROR with full traceback; game absent from `/games` list makes the omission visible via the API                                                                      |
| `CharacterStateRead` schema is too large — serialization cost per request | State assembly from DB is already done by `load_character()`; assembling the Pydantic model is proportional. Caching can be added later if profiling shows this as a bottleneck |
| Character ID enumeration via 404 vs 403                                   | Intentional: returning 404 for unowned characters prevents leaking whether a UUID belongs to any character                                                                      |
