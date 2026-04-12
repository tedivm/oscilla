## 1. API Response Models

- [x] 1.1 Create `oscilla/models/api/__init__.py`
- [x] 1.2 Create `oscilla/models/api/games.py` with `GameFeatureFlags` and `GameRead` Pydantic models
- [x] 1.3 Create `oscilla/models/api/characters.py` with `CharacterSummaryRead`, `CharacterCreate`, `CharacterUpdate`, `StatValue`, `StackedItemRead`, `ItemInstanceRead`, `SkillRead`, `BuffRead`, `ActiveQuestRead`, `MilestoneRead`, `ArchetypeRead`, `ActiveAdventureRead`, and `CharacterStateRead` Pydantic models

## 2. Content Registry Loading

- [x] 2.1 Update `oscilla/www.py` lifespan handler to scan `settings.games_path`, call `load_game()` for each valid game directory, and store results in `app.state.registries: Dict[str, ContentRegistry]` — a failed game logs at ERROR and is skipped, never crashes startup
- [x] 2.2 Create `oscilla/dependencies/games.py` with the `get_registry(game_name: str, request: Request) -> ContentRegistry` dependency that raises `HTTPException(404)` for unknown game names

## 3. Games Router

- [x] 3.1 Create `oscilla/routers/games.py` with `GET /games` returning `List[GameRead]` (unauthenticated, uses `app.state.registries`)
- [x] 3.2 Add `GET /games/{game_name}` to `oscilla/routers/games.py` using the `get_registry` dependency, returning a single `GameRead` or 404
- [x] 3.3 Implement `GameFeatureFlags` computation in `oscilla/models/api/games.py` — derive flags from live `ContentRegistry` attributes (`has_skills`, `has_quests`, `has_archetypes`, `has_ingame_time`, `has_recipes`, `has_loot_tables`)
- [x] 3.4 Mount the games router in `oscilla/www.py` with prefix `/games`

## 4. Characters Router

- [x] 4.1 Create `oscilla/routers/characters.py` with `GET /characters` — returns `List[CharacterSummaryRead]` for the authenticated user, supports optional `?game=<game_name>` query parameter
- [x] 4.2 Add `POST /characters` to `oscilla/routers/characters.py` — validates `game_name` against loaded registries, calls `new_character()` then `save_character()`, returns `CharacterSummaryRead` with HTTP 201
- [x] 4.3 Add `GET /characters/{id}` to `oscilla/routers/characters.py` — returns full `CharacterStateRead`; returns 404 if not found or not owned by the authenticated user
- [x] 4.4 Implement `CharacterStateRead` assembly: load character via service layer, build stats dict from all declared stats (including unset ones as `StatValue(value=None)`), resolve location display names from `ContentRegistry`
- [x] 4.5 Add `DELETE /characters/{id}` to `oscilla/routers/characters.py` — deletes owned character, returns 204; returns 404 if not found or not owned
- [x] 4.6 Add `PATCH /characters/{id}` to `oscilla/routers/characters.py` — accepts `CharacterUpdate` with optional `name`, validates non-empty after strip, returns `CharacterSummaryRead`; returns 404 if not found or not owned
- [x] 4.7 Mount the characters router in `oscilla/www.py` with prefix `/characters`

## 5. Settings

- [x] 5.1 Add `games_path: Path` field to `oscilla/conf/settings.py` pointing to the game content directory (default: `Path("content")` relative to CWD, or an absolute path configurable via environment variable)

## 6. Tests — Games

- [x] 6.1 Create `tests/routers/test_games.py` with a `games_client` fixture that overrides `app.state.registries` with a minimal in-memory test registry (no references to `content/`)
- [x] 6.2 Test `GET /games` returns all loaded games and returns `[]` when registry is empty
- [x] 6.3 Test `GET /games/{game_name}` returns correct `GameRead` for a known game
- [x] 6.4 Test `GET /games/{game_name}` returns 404 for an unknown game name
- [x] 6.5 Test `GameFeatureFlags`: game with no skills returns `has_skills=false`; game with skills returns `has_skills=true`
- [x] 6.6 Test `has_ingame_time` is derived from `era_length_ticks` in the game config
- [x] 6.7 Test `get_registry` dependency: returns registry for known game, raises 404 for unknown game (unit test, no HTTP layer needed)

## 7. Tests — Characters

- [x] 7.1 Create `tests/routers/test_characters.py` with a `characters_client` fixture: in-memory SQLite test DB + dependency override + minimal in-memory content registry in `app.state.registries` (no references to `content/`)
- [x] 7.2 Test `POST /characters` creates a character and returns 201 with `CharacterSummaryRead`
- [x] 7.3 Test `POST /characters` returns 422 for an unrecognized game name
- [x] 7.4 Test `POST /characters` returns 401 without authentication
- [x] 7.5 Test `GET /characters` returns only the authenticated user's characters
- [x] 7.6 Test `GET /characters?game=<name>` returns only characters for the specified game
- [x] 7.7 Test `GET /characters` returns `[]` when the user has no characters
- [x] 7.8 Test `GET /characters/{id}` returns full `CharacterStateRead` for an owned character
- [x] 7.9 Test `CharacterStateRead` stats dict includes all declared stats including unset ones with `value=null`
- [x] 7.10 Test `GET /characters/{id}` returns 404 for a character owned by another user (not 403)
- [x] 7.11 Test `GET /characters/{id}` returns 404 for a non-existent UUID
- [x] 7.12 Test `DELETE /characters/{id}` deletes owned character and returns 204
- [x] 7.13 Test `DELETE /characters/{id}` returns 404 for another user's character and does not delete it
- [x] 7.14 Test `PATCH /characters/{id}` renames owned character and returns updated `CharacterSummaryRead`
- [x] 7.15 Test `PATCH /characters/{id}` returns 422 for a whitespace-only name
- [x] 7.16 Test `PATCH /characters/{id}` returns 404 for another user's character

## 8. Documentation

- [x] 8.1 Update `docs/dev/api.md` with Games endpoints (`GET /games`, `GET /games/{game_name}`), all Characters endpoints, and the `CharacterStateRead` field reference table
- [x] 8.2 Update `docs/dev/api.md` or `docs/dev/game-engine.md` to document the content registry startup loading pattern: `app.state.registries`, restart-to-reload behavior, and the `get_registry` dependency

## 9. Testlandia Content Verification

- [x] 9.1 Verify that `content/testlandia/game.yaml` has a `display_name` and `description` field populated so `GET /games/testlandia` returns a complete `GameRead` without null fields
- [x] 9.2 Start the development server with `docker compose up` and confirm `GET /games` lists testlandia with correct feature flags derived from the loaded manifests
- [x] 9.3 Create a character via `POST /characters` with `{"game_name": "testlandia"}` using a registered web user and verify the 201 response shape matches `CharacterSummaryRead`
- [x] 9.4 Call `GET /characters/{id}` on the newly created character and verify the `stats` dict contains all stats declared in `content/testlandia/character_config.yaml` (including string, bool, and int typed stats)
- [x] 9.5 Rename the character via `PATCH /characters/{id}` and confirm the updated name appears in subsequent `GET /characters`
- [x] 9.6 Delete the character via `DELETE /characters/{id}` and confirm it no longer appears in `GET /characters`
