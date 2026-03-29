## 1. Settings and Configuration

- [x] 1.1 Rename `content_path` → `games_path` in `oscilla/conf/settings.py`; update env var to `GAMES_PATH`; update default to point at `content/` (library root)
- [x] 1.2 Update `tests/test_settings.py` to assert `GAMES_PATH` is read and `CONTENT_PATH` is no longer a recognised setting

## 2. Content Directory Restructure

- [x] 2.1 Use `git mv content/ content/the-kingdom/` to move the existing game package into a subdirectory
- [x] 2.2 Verify `oscilla validate` still works against `content/the-kingdom/` by running it directly (pre-loader change baseline)
- [x] 2.3 Update `.env.example` and `README.md` to document the new library root layout and `GAMES_PATH`

## 3. Loader: Multi-Game Support

- [x] 3.1 Add `load_games(library_root: Path) -> Dict[str, ContentRegistry]` to `oscilla/engine/loader.py` that scans immediate subdirectories for `game.yaml` and calls `load()` per package
- [x] 3.2 Add integration test fixture `tests/fixtures/content/multi-game-library/` with two minimal game packages (`game-alpha`, `game-beta`)
- [x] 3.3 Write loader integration tests for `load_games()`: two-game library, single-game library, empty library, error in one package

## 4. Database Migration: game_name Column

- [x] 4.1 Add `game_name: Mapped[str]` column to `CharacterRecord` in `oscilla/models/character.py`
- [x] 4.2 Drop `uq_character_user_name` constraint; replace with `uq_character_user_game_name` on `(user_id, game_name, name)`
- [x] 4.3 Run `make create_migration MESSAGE="add game_name to characters"` and edit the generated migration to set `DEFAULT 'the-kingdom'` for existing rows

## 5. Character Services: Game-Scoping

- [x] 5.1 Add `game_name: str` parameter to `save_character()`, `get_character_by_name()`, `list_characters_for_user()`, and `delete_user_characters()` in `oscilla/services/character.py`
- [x] 5.2 Update all internal query filters to include `CharacterRecord.game_name == game_name`
- [x] 5.3 Update all call sites in `oscilla/cli.py` and `oscilla/engine/tui.py` to pass `game_name`
- [x] 5.4 Update `tests/engine/test_character_persistence.py`: add `game_name` fixture parameter; add test that two characters with the same name in different games coexist; add test that `delete_user_characters` is game-scoped

## 6. CLI: --game Flag and Validate Changes

- [x] 6.1 Replace `_load_content()` in `oscilla/cli.py` with `_load_games()` that calls `load_games()` and returns `Dict[str, ContentRegistry]`
- [x] 6.2 Add `--game GAME_NAME` option to the `game` command; pass it through to TUI and service calls
- [x] 6.3 Add `--game GAME_NAME` option to `validate` command; when omitted, validate all games and report per-game; when supplied, validate only that game
- [x] 6.4 Update `--reset-db` logic to delete characters for the selected game only, and include the game name in the confirmation prompt
- [x] 6.5 Update `tests/test_cli.py` with tests for `--game` flag and multi-game `validate` output

## 7. TUI: Game-Selection Screen

- [x] 7.1 Add `GameSelectScreen` Textual `ModalScreen` to `oscilla/engine/tui.py` that lists games by `spec.displayName` and `spec.description` and returns the selected `metadata.name`
- [x] 7.2 In `OscillaApp`, show `GameSelectScreen` when more than one game is loaded and no `--game` flag was supplied; auto-select when only one game is present
- [x] 7.3 Pass `game_name` from the selected registry through to all character service calls within TUI

## 8. Engine: Level-Down

- [x] 8.1 Update `add_xp()` in `oscilla/engine/character.py` to support negative XP, level-down loop, HP cap, XP floor at 0, level floor at 1; change return type to `tuple[List[int], List[int]]`
- [x] 8.2 Update `effects.py` call site for `XpGrantEffect` to unpack the new return tuple and emit de-level TUI messages for each lost level
- [x] 8.3 Write unit tests in `tests/engine/test_character.py` covering: de-level on negative XP, multi-level loss, HP cap, XP clamp at 0, level-1 floor, return tuple structure

## 9. New Effects: stat_change and stat_set

- [x] 9.1 Add `StatChangeEffect` and `StatSetEffect` Pydantic models to `oscilla/engine/models/adventure.py`; add them to the `Effect` union type
- [x] 9.2 Add load-time validation in `oscilla/engine/loader.py`: `stat_change` requires `int` or `float` stat type; `stat_set` value must be type-compatible; both require the stat name to exist in `CharacterConfig`
- [x] 9.3 Implement `stat_change` and `stat_set` handlers in `oscilla/engine/steps/effects.py`
- [x] 9.4 Add fixture `tests/fixtures/content/stat-effects/` with a minimal game package for validation tests
- [x] 9.5 Write unit tests for `stat_change` (positive int, negative float, bool stat → load error, unknown stat → load error) and `stat_set` (int, bool, null str, incompatible type → load error)

## 10. Testlandia Content

- [x] 10.1 Create `content/testlandia/game.yaml` with `metadata.name: testlandia` and developer-friendly display name and description
- [x] 10.2 Create `content/testlandia/character_config.yaml` with all four stat types: `strength` (int), `speed` (float), `is_blessed` (bool), `gold` (int), `title` (str, null default), `debug_counter` (int, hidden)
- [x] 10.3 Create Character Realm: `character` region + `heal` location (full-heal, partial-heal adventures)
- [x] 10.4 Create Character Realm: `xp-lab` location (gain-xp-small, gain-xp-level-up, lose-xp-delevel adventures)
- [x] 10.5 Create Character Realm: `stat-workshop` location (strength, speed, blessing, gold, title stat manipulation adventures)
- [x] 10.6 Create Combat Realm: `combat` region + `training-grounds`, `damage-chamber` locations with combat and damage testing adventures
- [x] 10.7 Create Conditions Realm: `conditions` region + `gated-hall`, `level-gates` locations with stat, level, and blessing requirements
- [x] 10.8 Create Choices Realm: `choices` region + `moral-crossroads`, `puzzle-chambers` locations with branching choice adventures
- [x] 10.9 Create Items Realm: `items` region + `treasure-chamber`, `blacksmith-shop` locations with item discovery and crafting adventures
- [x] 10.10 Run `oscilla validate --game testlandia` and confirm clean exit (code 0)

## 11. Documentation

- [x] 11.1 Update `README.md`: rename `CONTENT_PATH` → `GAMES_PATH`; document multi-game directory layout; add `--game` flag to CLI reference table; update `--reset-db` note to clarify game scope
- [x] 11.2 Update `docs/dev/settings.md`: document `games_path` / `GAMES_PATH`; remove `CONTENT_PATH` entry
- [x] 11.3 Update `docs/dev/game-engine.md`: document `load_games()` API; `stat_change`/`stat_set` YAML syntax and validation rules; `add_xp()` return type change and level-down mechanics
- [x] 11.4 Update `docs/dev/testing.md`: add Testlandia usage guide — which realm covers which feature, how to start a manual test session, note that Testlandia YAML is never imported in automated tests
- [x] 11.5 Update `docs/authors/content-authoring.md`: document multi-package library structure; add `stat_change`/`stat_set` effect reference with typed YAML examples; document level-down XP rules
- [x] 11.6 Create `ROADMAP.md` with an entry noting integer overflow/underflow hardening (XP, stats, inventory quantities) as a future concern

## 12. Final Validation

- [x] 12.1 Run `make tests` and confirm all checks pass (pytest, ruff, black, mypy, dapperdata, tomlsort)
- [x] 12.2 Run `oscilla validate` (all games) and confirm clean output
- [x] 12.3 Run `oscilla game --game testlandia` manually and exercise at least one adventure from each realm
