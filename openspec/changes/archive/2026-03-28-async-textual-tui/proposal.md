## Why

The current TUI is a blocking REPL — player status scrolls away, menus use number input, and all I/O is synchronous, which prevents reuse of the game pipeline in async contexts (FastAPI WebSocket sessions, future multiplayer, etc.). Moving to a fully async pipeline with a persistent Textual-based layout solves this at the root.

## What Changes

- **BREAKING** `TUICallbacks` protocol methods become `async def`; all callers must `await` them
- **BREAKING** `AdventurePipeline.run()` and all internal pipeline methods become `async def`
- **BREAKING** All step handler functions (`run_narrative`, `run_choice`, `run_combat`, `run_stat_check`, `run_effect`) become `async def`
- **BREAKING** `MockTUI` in tests becomes fully async; all pipeline and step-handler tests become `async def`
- `RichTUI` and the standalone `show_status()` function are removed entirely and replaced by a `TextualTUI` backed by a Textual `App`
- The game is launched via `App.run()` rather than a `while True` CLI loop; `_select_region`, `_select_location`, and the blocking `game()` loop in `cli.py` are rewritten as an async Textual worker
- `textual` is added as a runtime dependency
- `asyncio_mode = "auto"` is enabled in `pyproject.toml` to eliminate boilerplate `@pytest.mark.asyncio` markers on the large new batch of async tests
- `docs/dev/tui.md` is updated to describe the new architecture

## Capabilities

### New Capabilities

- `textual-tui`: Full-screen Textual application providing a persistent status sidebar, scrollable narrative log, arrow-key menu selection, and a region/location context panel — all updating in real time as the async game pipeline runs

### Modified Capabilities

- `cli-game-loop`: TUI interaction model changes from number-entered REPL menus to arrow-key selection in a persistent Textual layout; player status is always visible in a sidebar rather than printed on each loop iteration; region context is always visible rather than shown only during location selection
- `adventure-pipeline`: The `TUICallbacks` protocol and all pipeline/step-handler interfaces change from synchronous to fully async

## Impact

- `oscilla/engine/tui.py` — full rewrite
- `oscilla/engine/pipeline.py` — `TUICallbacks` protocol and `AdventurePipeline` all go async
- `oscilla/engine/steps/` — all five handlers go async
- `oscilla/cli.py` — game loop rewritten as Textual worker; `_select_region` / `_select_location` helpers inlined or made async inside the Textual app
- `tests/engine/conftest.py` — `MockTUI` goes async
- `tests/engine/test_pipeline.py` and `tests/engine/steps/*.py` — all tests become async
- `pyproject.toml` — add `textual` dependency; set `asyncio_mode = "auto"`
- `docs/dev/tui.md` — updated architecture documentation
