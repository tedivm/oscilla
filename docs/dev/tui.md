# TUI Interface

The terminal user interface provides the full-screen, async interactive experience for gameplay. This document covers the Textual-based TUI implementation and the CLI commands that launch it.

## Overview

The TUI stack has three layers:

| Layer | File | Responsibility |
|---|---|---|
| CLI entry point | `oscilla/cli.py` | Command parsing, content loading |
| Textual application | `oscilla/engine/tui.py` | Full-screen UI, async game loop |
| Engine protocol | `oscilla/engine/pipeline.py` | `TUICallbacks` interface consumed by the pipeline |

`OscillaApp` (a Textual `App`) owns the game loop as a worker coroutine. It drives `AdventurePipeline` via the `TextualTUI` adapter, which implements the async `TUICallbacks` protocol using Textual's widget API.

## Architecture

### Async Game Loop

The game runs inside a Textual **worker** — a background coroutine managed by Textual's event loop. The `@work(exclusive=True)` decorator registers `_game_loop()` as a worker, so `on_mount` just calls it directly:

```python
@work(exclusive=True)
async def _game_loop(self) -> None:
    ...

def on_mount(self) -> None:
    self._game_loop()
```

`_game_loop()` performs region selection, location selection, weighted adventure picking, and pipeline execution — all with `await`. Player input (menus, name entry) suspends the loop via `asyncio.Event`; Textual's event handlers set those events when the player acts.

### TUICallbacks Protocol

All engine components interact with the TUI exclusively through the async `TUICallbacks` protocol defined in `oscilla/engine/pipeline.py`:

```python
class TUICallbacks(Protocol):
    async def show_text(self, text: str) -> None: ...
    async def show_menu(self, prompt: str, options: List[str]) -> int: ...
    async def show_combat_round(
        self,
        player_hp: int, max_hp: int,
        enemy_name: str, enemy_hp: int, enemy_max_hp: int,
    ) -> None: ...
    async def wait_for_ack(self) -> None: ...
```

`show_menu()` returns a **1-based** integer (the index of the chosen option).

**Design principle**: `tui.py` is the **only** module that imports Textual directly. Engine code only sees `TUICallbacks`, which makes testing completely independent of Textual.

## Widget Inventory

All widgets are defined in `oscilla/engine/tui.py`.

### `NarrativeLog(RichLog)`

Scrollable log that accumulates all narrative text during a session.

- `append_text(text: str) -> None` — wraps content in a Rich `Panel` and writes it to the log.
- CSS: occupies the upper portion of the left panel, scrolls automatically.

### `ChoiceMenu(OptionList)`

Player-choice menu. Hidden between prompts; shown when a selection is needed.

- `wait_for_selection(options: List[str]) -> int` — calls `set_options()` then suspends via `asyncio.Event`; returns a 1-based index when the player confirms a selection.
- `on_option_list_option_selected(event)` — Textual event handler that stores `event.option_index + 1` and sets the event.
- `highlighted = 0` is set after each `set_options()` call to pre-select the first item, ensuring Enter works without navigating first.

`wait_for_ack()` in `TextualTUI` is implemented by calling `wait_for_selection(["▶  Press Enter to continue"])`.

### `StatusPanel(Static)`

Right-panel widget showing the current player state.

- `set_registry(registry: ContentRegistry) -> None` — stores the registry reference for stat lookup.
- `refresh_player(player: PlayerState) -> None` — re-renders name, level, HP, XP, and all `public_stats` declared in `CharacterConfig`.

### `RegionPanel(Static)`

Right-panel widget showing the current region.

- `set_region(name: str, description: str) -> None` — updates the displayed region name and description.

### `HelpOverlay(ModalScreen[None])`

Modal overlay showing key binding help. Dismissed by `?` or `Escape`.

### `OscillaApp(App[None])`

The root Textual application.

**Layout**:

```
┌────────────────────────────────────┬────────────────┐
│  NarrativeLog (#left-panel, 3fr)   │  StatusPanel   │
│                                    │  RegionPanel   │
│  ChoiceMenu                        │  (#right-panel │
│                                    │   1fr)         │
├────────────────────────────────────┴────────────────┤
│  Footer (key binding hints)                         │
└─────────────────────────────────────────────────────┘
│  Input#name-input  (hidden except during name prompt)
```

**Key bindings**:

| Key | Action |
|---|---|
| `ctrl+q` | Quit application |
| `?` | Toggle `HelpOverlay` |

**Name prompt**: `_prompt_name()` shows the `Input` widget, suspends on an `asyncio.Event`, and returns the entered name (defaulting to `"Hero"` if empty).

### `TextualTUI`

Concrete implementation of `TUICallbacks` backed by `OscillaApp` widgets. Constructed inside `_game_loop()` with a reference to the running `OscillaApp`:

```python
tui = TextualTUI(self)  # self = OscillaApp instance
```

| Protocol method | Widget used |
|---|---|
| `show_text` | `NarrativeLog.append_text()` |
| `show_menu` | `NarrativeLog.append_text()` (prompt) + `ChoiceMenu.wait_for_selection()` |
| `show_combat_round` | `NarrativeLog` (Rich `Table` showing HP) |
| `wait_for_ack` | `ChoiceMenu.wait_for_selection(["▶  Press Enter to continue"])` |

## Game Loop Detail

```
_game_loop()
│
├─ _prompt_name()          → player name via Input widget
├─ PlayerState.new_player()
├─ StatusPanel.set_registry()
│
└─ while True:  ← outer region loop
   ├─ filter accessible regions  (condition evaluator)
   ├─ tui.show_menu()            → region choice (or Quit)
   ├─ RegionPanel.set_region()
   │
   └─ while True:  ← inner location loop (stays in region after each adventure)
      ├─ filter accessible locs
      ├─ (no locs) → tui.show_text() + break to region loop
      ├─ tui.show_menu()            → location choice (or Back)
      ├─ (Back chosen) → break to region loop
      ├─ weighted random adventure pick
      ├─ player.statistics.record_location_visited()
      ├─ AdventurePipeline.run()    → outcome
      ├─ tui.show_text()            → outcome message
      └─ StatusPanel.refresh_player()
```

## CLI Commands

### `game`

```bash
uv run oscilla game
```

- Loads content from `settings.content_path` (default `./content/`).
- Instantiates `OscillaApp(registry=registry)` and calls `.run()` — this hands control to Textual.
- The full-screen TUI owns the session from this point onward.

### `validate`

```bash
uv run oscilla validate
```

- Invokes `ContentLoader.load()` on configured content path.
- Prints success or detailed errors (file path + descriptions).
- Exit code 0 for valid content, non-zero on any error.

## Testing

### MockTUI

`tests/engine/conftest.py` provides `MockTUI`, which satisfies the async `TUICallbacks` protocol without any Textual or terminal interaction:

```python
class MockTUI:
    async def show_text(self, text: str) -> None:
        self.texts.append(text)

    async def show_menu(self, prompt: str, options: List[str]) -> int:
        return self.menu_responses.pop(0)

    async def show_combat_round(self, ...) -> None:
        self.combat_rounds.append(...)

    async def wait_for_ack(self) -> None:
        self.acks += 1
```

Configure responses before the test, then assert on captured calls:

```python
async def test_pipeline_records_calls(base_player, minimal_registry, mock_tui):
    mock_tui.menu_responses = [1]  # Always pick option 1
    pipeline = AdventurePipeline(registry=minimal_registry, player=base_player, tui=mock_tui)
    outcome = await pipeline.run("test-adventure")

    assert len(mock_tui.texts) > 0
```

### asyncio_mode = "auto"

`pyproject.toml` sets `asyncio_mode = "auto"` under `[tool.pytest.ini_options]`. All `async def test_*` functions are automatically treated as async tests — no `@pytest.mark.asyncio` decorator is needed.

### No Textual in Engine Tests

Engine tests (`tests/engine/`) never import Textual. They use `MockTUI` exclusively. This keeps the engine test suite fast and independent of the full-screen UI framework.

## Configuration

```python
# oscilla/conf/settings.py
content_path: str = Field(
    default="./content/",
    description="Path to game content directory",
)
```

Both `game` and `validate` use `settings.content_path`. Override via environment variable:

```bash
CONTENT_PATH=/path/to/custom/content uv run oscilla game
```

## Extending the TUI

To add a new UI capability (e.g., a map view):

1. Add a new method to the `TUICallbacks` protocol in `pipeline.py`.
2. Implement the method as `async def` in `TextualTUI` using Textual widgets.
3. Add a corresponding `async def` no-op or stub in `MockTUI` (`tests/engine/conftest.py`).
4. Update any step handlers that need to call the new method.

The Protocol + MockTUI pattern ensures that adding TUI features never breaks the engine test suite as long as MockTUI provides a matching async signature.
