# Game Discovery

## Purpose

Specifies how game `ContentRegistry` instances are loaded at server startup, the `app.state.registries` store, the `get_registry` FastAPI dependency, the `GET /games` and `GET /games/{game_name}` endpoints, and the `GameFeatureFlags` schema derived from the live registry.

---

## Requirements

### Requirement: Content registries are loaded once at startup

The application SHALL load all game `ContentRegistry` instances during the FastAPI lifespan handler at server startup. The resulting registries SHALL be stored in `app.state.registries` as `Dict[str, ContentRegistry]`, keyed by `game.name` from each game's `game.yaml`.

The lifespan handler SHALL scan `settings.games_path` for subdirectories containing a valid `game.yaml` file. For each such directory it SHALL attempt to call `load_game(game_dir)` and store the result. If loading any single game raises an exception, the handler SHALL log the error at ERROR level with a full traceback and skip that game — it MUST NOT abort startup or crash the server. A game with a broken manifest will be absent from `app.state.registries` and therefore absent from all API responses.

A server restart is required to pick up new or changed content.

#### Scenario: Healthy game directories are loaded at startup

- **WHEN** `settings.games_path` contains two valid game directories
- **THEN** `app.state.registries` contains two entries keyed by game name after lifespan completes

#### Scenario: Broken game directory is skipped on startup

- **WHEN** one game directory has an invalid `game.yaml`
- **THEN** that game is absent from `app.state.registries`
- **AND** the server starts successfully
- **AND** an ERROR-level log entry is emitted for the failed directory

#### Scenario: Empty games path produces empty registry dict

- **WHEN** `settings.games_path` exists but contains no subdirectories
- **THEN** `app.state.registries` is an empty dict and the server starts normally

---

### Requirement: get_registry dependency resolves a ContentRegistry by game name

A FastAPI dependency `get_registry(game_name: str, request: Request) -> ContentRegistry` SHALL be provided for use by any endpoint that needs registry access.

The dependency SHALL look up `game_name` in `request.app.state.registries`. If found it SHALL return the `ContentRegistry` instance. If not found it SHALL raise `HTTPException(status_code=404, detail=f"Game '{game_name}' not found.")`.

#### Scenario: Known game name returns registry

- **WHEN** `get_registry` is called with a game name present in `app.state.registries`
- **THEN** the corresponding `ContentRegistry` is returned

#### Scenario: Unknown game name raises 404

- **WHEN** `get_registry` is called with a game name not present in `app.state.registries`
- **THEN** `HTTPException` with `status_code=404` is raised

---

### Requirement: GET /games returns a list of all loaded games

`GET /games` SHALL be an unauthenticated endpoint that returns `List[GameRead]` — one entry for each game currently in `app.state.registries`. The response MAY be empty if no games are loaded.

Each `GameRead` object SHALL contain:

- `name: str` — the machine-readable game name (matches the key in `registries`)
- `display_name: str` — `game.yaml` `display_name` field
- `description: str | None` — `game.yaml` `description` field, `None` if absent
- `features: GameFeatureFlags` — derived from the live `ContentRegistry`

#### Scenario: Returns all loaded games

- **WHEN** two games are loaded at startup and `GET /games` is called
- **THEN** the response is a JSON array of two `GameRead` objects with correct names

#### Scenario: Returns empty list when no games are loaded

- **WHEN** no games are loaded in `app.state.registries`
- **THEN** the response is `[]` with HTTP 200

---

### Requirement: GET /games/{game_name} returns metadata for a single game

`GET /games/{game_name}` SHALL be an unauthenticated endpoint that returns a single `GameRead` for the named game.

The endpoint SHALL return HTTP 404 if `game_name` is not in `app.state.registries`.

#### Scenario: Returns GameRead for a known game

- **WHEN** a game named `"testland"` is loaded and `GET /games/testland` is called
- **THEN** the response is a `GameRead` object with `name = "testland"` and HTTP 200

#### Scenario: Returns 404 for an unknown game name

- **WHEN** `GET /games/nonexistent` is called and that game is not loaded
- **THEN** the response has HTTP 404

---

### Requirement: GameFeatureFlags is derived from the live ContentRegistry

`GameFeatureFlags` SHALL be computed from the loaded `ContentRegistry` by inspecting the actual manifests. It MUST NOT be based solely on `game.yaml` declarations. The following boolean fields SHALL be present:

| Field             | True when                                                                    |
| ----------------- | ---------------------------------------------------------------------------- |
| `has_skills`      | `len(registry.skills) > 0`                                                   |
| `has_quests`      | `len(registry.quests) > 0`                                                   |
| `has_archetypes`  | `len(registry.archetypes) > 0`                                               |
| `has_ingame_time` | `game.yaml` includes a `time:` block (`registry.game.spec.time is not None`) |
| `has_recipes`     | `len(registry.recipes) > 0`                                                  |
| `has_loot_tables` | `len(registry.loot_tables) > 0`                                              |

#### Scenario: Game with no skills returns has_skills=false

- **GIVEN** a game registry with an empty skills collection
- **WHEN** `GET /games/{game_name}` is called
- **THEN** `features.has_skills` is `false` in the response

#### Scenario: Game with skill manifests returns has_skills=true

- **GIVEN** a game registry with at least one skill manifest
- **WHEN** `GET /games/{game_name}` is called
- **THEN** `features.has_skills` is `true` in the response

#### Scenario: has_ingame_time is true when a time block is declared

- **GIVEN** a game configured with a `time:` block in `game.yaml` (i.e. `registry.game.spec.time is not None`)
- **WHEN** `GET /games/{game_name}` is called
- **THEN** `features.has_ingame_time` is `true` in the response
