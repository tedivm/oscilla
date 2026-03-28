## 1. Dependencies and Configuration

- [x] 1.1 Add `textual` to runtime dependencies in `pyproject.toml`
- [x] 1.2 Add `asyncio_mode = "auto"` to `[tool.pytest.ini_options]` in `pyproject.toml`
- [x] 1.3 Run `make sync` to update the lockfile

## 2. Async TUICallbacks Protocol

- [x] 2.1 Change all four methods in the `TUICallbacks` Protocol in `oscilla/engine/pipeline.py` from `def` to `async def`
- [x] 2.2 Update the `RunOutcomeBranch` callable type hint in step handler signatures to use `Awaitable[AdventureOutcome]`

## 3. Async Step Handlers

- [x] 3.1 Convert `run_narrative` in `oscilla/engine/steps/narrative.py` to `async def`, adding `await` before all `tui` calls
- [x] 3.2 Convert `run_choice` in `oscilla/engine/steps/choice.py` to `async def`, adding `await` before `tui.show_menu()`
- [x] 3.3 Convert `run_combat` in `oscilla/engine/steps/combat.py` to `async def`, adding `await` before all `tui` calls
- [x] 3.4 Convert `run_stat_check` in `oscilla/engine/steps/stat_check.py` to `async def` (no TUI calls, but called with `await` by the pipeline)
- [x] 3.5 Convert `run_effect` in `oscilla/engine/steps/effects.py` to `async def` (no TUI calls, but called with `await` by the pipeline)

## 4. Async AdventurePipeline

- [x] 4.1 Convert `AdventurePipeline.run()` to `async def`, adding `await` before `_run_from()`
- [x] 4.2 Convert `AdventurePipeline._run_from()` to `async def`, adding `await` before `_dispatch()`
- [x] 4.3 Convert `AdventurePipeline._run_steps()` to `async def`, adding `await` before `_dispatch()`
- [x] 4.4 Convert `AdventurePipeline._dispatch()` to `async def`, adding `await` before all step handler calls
- [x] 4.5 Convert `AdventurePipeline._run_effects()` to `async def`, adding `await` before `run_effect()`
- [x] 4.6 Convert `AdventurePipeline._run_outcome_branch()` to `async def`, adding `await` before `_run_steps()`

## 5. Textual TUI Implementation

- [x] 5.1 Remove `RichTUI`, `show_status()`, and all Rich prompt imports from `oscilla/engine/tui.py`
- [x] 5.2 Implement `NarrativeLog` widget (Textual `RichLog` subclass) with `append_text()` method
- [x] 5.3 Implement `ChoiceMenu` widget (Textual `ListView` subclass) with `set_options()` method that replaces current items; handle `on_list_view_selected` to fire a selection event
- [x] 5.4 Implement `StatusPanel` widget (`Static` subclass) with `refresh_player()` method that renders name, level, HP, XP, and public stats from `PlayerState`
- [x] 5.5 Implement `RegionPanel` widget (`Static` subclass) with `set_region()` method that renders region name and description
- [x] 5.6 Implement `OscillaApp(App)` with the two-column layout: left panel (`NarrativeLog` + `ChoiceMenu`), right panel (`StatusPanel` + `RegionPanel`), and footer bar showing minimal always-visible hints including `[?] Help`
- [x] 5.6a Implement `HelpOverlay` as a Textual `ModalScreen` listing all key bindings grouped by category (Navigation, Narrative Log, Application); bind `?` to toggle it and `Escape` to dismiss it
- [x] 5.7 Implement `TextualTUI` class satisfying the async `TUICallbacks` protocol; each method updates the appropriate widget and `await`s an `asyncio.Event` set by the widget's interaction handler
- [x] 5.8 Implement `OscillaApp._game_loop()` async worker method: character name prompt, region selection loop, location selection, weighted adventure selection, `AdventurePipeline.run()`, outcome display, and quit handling — all via `await tui.*` calls
- [x] 5.9 Register `_game_loop()` as a Textual worker in `OscillaApp.on_mount()`

## 6. CLI Entrypoint Update

- [x] 6.1 Rewrite `game()` command in `oscilla/cli.py` to instantiate `OscillaApp` with the loaded `ContentRegistry` and call `app.run()` (synchronous Textual entry point — no `@syncify` needed)
- [x] 6.2 Remove `_select_region`, `_select_location`, `_pick_adventure`, `_show_outcome`, and the old `while True` game loop from `oscilla/cli.py`
- [x] 6.3 Remove the `from oscilla.engine.tui import RichTUI, console, show_status` import from `oscilla/cli.py`

## 7. Test Updates — MockTUI and Fixtures

- [x] 7.1 Convert all four `MockTUI` methods in `tests/engine/conftest.py` to `async def` (logic unchanged)
- [x] 7.2 Remove `@pytest.mark.asyncio` decorators from all tests in `tests/services/test_cache.py` (now redundant with `asyncio_mode = "auto"`)

## 8. Test Updates — Pipeline Tests

- [x] 8.1 Convert all test functions in `tests/engine/test_pipeline.py` to `async def`, adding `await` before `pipeline.run()` calls
- [x] 8.2 Verify all assertions in `tests/engine/test_pipeline.py` still hold with no logic changes needed

## 9. Test Updates — Step Handler Tests

- [x] 9.1 Convert all test functions in `tests/engine/steps/test_choice.py` to `async def`, adding `await` before `run_choice()` calls; update the `mock_run_outcome_branch` callback to `async def`
- [x] 9.2 Convert all test functions in `tests/engine/steps/test_combat.py` to `async def`, adding `await` before `run_combat()` calls; update helper callbacks to `async def`
- [x] 9.3 Convert all test functions in `tests/engine/steps/test_stat_check.py` to `async def`, adding `await` before `run_stat_check()` calls; update helper callbacks to `async def`
- [x] 9.4 Convert all test functions in `tests/engine/steps/test_effects.py` to `async def`, adding `await` before `run_effect()` calls

## 10. Validation

- [x] 10.1 Run `make pytest` and confirm all tests pass with zero failures
- [x] 10.2 Run `make ruff_check` and `make black_check` and fix any issues
- [x] 10.3 Run `make mypy_check` and fix any type errors introduced by the async conversions
- [x] 10.4 Run `make chores` to auto-format any remaining style issues
- [x] 10.5 Launch `oscilla game` manually and verify the Textual layout renders, status sidebar stays visible, arrow-key selection works, and the game loop completes at least one adventure end-to-end

## 11. Documentation

- [x] 11.1 Rewrite `docs/dev/tui.md` to cover: new Textual app architecture; widget inventory (`NarrativeLog`, `ChoiceMenu`, `StatusPanel`, `RegionPanel`); `TextualTUI` async protocol implementation; how the game loop worker drives the pipeline; how to implement a future `WebSocketTUI`; removal of `RichTUI` and `show_status()`
