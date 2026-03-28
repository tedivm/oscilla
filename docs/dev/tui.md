# CLI/TUI Interface

The command-line interface provides player-facing commands and implements the terminal user interface for interactive gameplay. This document covers the CLI layer and TUI implementation details.

## Overview

The CLI layer (`oscilla/cli.py`) contains:

- **CLI Commands**: `game` (interactive play) and `validate` (content verification)
- **Game Loop Helpers**: Region/location selection and adventure picking logic
- **Character Creation**: Player initialization with name input
- **TUI Integration**: Bridges engine events to Rich-based terminal output

## RichTUI Implementation

`RichTUI` (in `oscilla/engine/tui.py`) is the concrete implementation of `TUICallbacks`:

```python
class RichTUI:
    def show_text(self, text: str) -> None:
        """Display text with Rich rendering (markdown, colors, etc.)."""

    def show_menu(self, prompt: str, options: List[str]) -> int:
        """Present numbered menu using Rich prompts."""

    def show_combat_round(self, player_hp: int, max_hp: int,
                         enemy_name: str, enemy_hp: int, enemy_max_hp: int) -> None:
        """Display combat status with health bars."""

    def wait_for_ack(self) -> None:
        """Wait for Enter key press."""
```

**Design Principle**: `tui.py` is the **only module** that imports Rich directly. This centralization:

- Keeps Rich dependencies contained
- Simplifies testing (engine tests never need Rich)
- Allows easy replacement of the UI layer

### Status Display

The `show_status(player, registry)` function renders the player's current state:

```
┌─ Character Status ─┐
│ Level: 3           │
│ HP: 45/50          │
│ XP: 1250/2000      │
│ Strength: 15       │
│ Dexterity: 12      │
└────────────────────┘
```

**Dynamic Stat Rendering**: The status panel reads `CharacterConfig.public_stats` to determine which custom stats to display. Only stats marked as "public" appear in the status display.

## Game Loop Structure

The `game` command implements the core gameplay loop:

```python
def game() -> None:
    """Main interactive game command."""
    # 1. Load content and initialize systems
    registry = _load_content()
    evaluator = ConditionEvaluator()
    tui = RichTUI()

    # 2. Character creation
    player = _create_character(registry, tui)

    # 3. Main game loop
    while True:
        show_status(player, registry)

        region_ref = _select_region(player, registry, evaluator, tui)
        if region_ref is None:  # Player chose Quit
            break

        location_ref = _select_location(player, registry, evaluator, region_ref, tui)
        if location_ref is None:  # Player chose Back
            continue

        adventure_ref = _pick_adventure(player, registry, evaluator, location_ref)
        if adventure_ref is None:  # No available adventures
            tui.show_text("No adventures available here.")
            continue

        # Record location visit only after successful adventure selection
        player.record_location_visited(location_ref)

        # Execute adventure
        pipeline = AdventurePipeline(registry, player, tui)
        outcome = pipeline.run(adventure_ref)

        # Show outcome and updated status
        _show_outcome(outcome, tui)
        show_status(player, registry)
```

### Helper Functions

#### `_select_region(player, registry, evaluator, tui)`

- Filters regions by accessibility (condition evaluation)
- Presents numbered menu with region names + "Quit"
- Returns selected region reference or `None` for Quit
- **Error Handling**: Calls `SystemExit(1)` if no regions are accessible

#### `_select_location(player, registry, evaluator, region_ref, tui)`

- Shows region header text (`tui.show_text(region.spec.description)`)
- Filters locations within region by unlock conditions
- Presents numbered menu with location names + "Back"
- Returns selected location reference or `None` for Back
- **Important**: Does not record location visit here

#### `_pick_adventure(player, registry, evaluator, location_ref)`

- Filters location's adventure pool by `requires` conditions
- Uses weighted random selection (`random.choices()`) with declared weights
- Returns adventure reference or `None` if no adventures pass conditions
- **Statistics Note**: Adventure completion is recorded by `AdventurePipeline.run()` internally

#### `_show_outcome(outcome, tui)`

Displays adventure results based on outcome string:

- `"victory"`: "You emerged victorious!"
- `"defeat"`: "You were defeated..."
- `"fled"`: "You managed to flee to safety."
- Custom outcomes: Display as-is

### Visit Counter Timing Rule

**Critical Timing**: `player.record_location_visited()` is called **only after** `_pick_adventure()` returns a valid adventure reference.

**Rationale**: Players should not get "credit" for visiting a location if no adventure was available. Empty adventure pools (due to condition gating) do not count as visits.

## CLI Commands

### `game` Command

```bash
uv run oscilla game
```

**Behavior**:

- Loads content from `settings.content_path` (defaults to `./content/`)
- Prompts for character name with Rich input
- Starts interactive game loop
- Exits gracefully on Quit selection (exit code 0)

### `validate` Command

```bash
uv run oscilla validate
```

**Behavior**:

- Invokes `ContentLoader.load()` on configured content path
- Prints success message or detailed error list with file paths
- Exit code 0 for valid content, non-zero for any errors
- Uses same content path as `game` command

## Testing CLI Code

CLI tests use `typer.testing.CliRunner` with mocked dependencies:

```python
from typer.testing import CliRunner
from unittest.mock import patch

def test_game_command_quit_exits():
    runner = CliRunner()

    # Mock RichTUI to avoid terminal interaction
    with patch("oscilla.cli.RichTUI") as mock_tui_class:
        mock_tui = mock_tui_class.return_value
        mock_tui.show_menu.return_value = 0  # Select Quit

        result = runner.invoke(app, ["game"])

        assert result.exit_code == 0
        assert "Goodbye!" in result.stdout
```

**Testing Patterns**:

- Use `patch("oscilla.cli.RichTUI")` to inject `MockTUI` behavior
- Control menu selections via `mock_tui.show_menu.return_value`
- Verify terminal output through `runner.invoke()` result
- Test error conditions with invalid content fixtures

### MockTUI Integration

For engine-level testing, inject `MockTUI` via the `TUICallbacks` interface:

```python
def test_pipeline_records_calls(base_player, minimal_registry, mock_tui):
    pipeline = AdventurePipeline(minimal_registry, base_player, mock_tui)
    outcome = pipeline.run("test-adventure")

    # Verify captured interactions
    assert len(mock_tui.texts) == 2
    assert mock_tui.texts[0] == "You enter the forest..."
    assert mock_tui.acks == 2  # Two acknowledgment pauses
```

## Rich Integration Details

The TUI layer leverages Rich features:

- **Text Rendering**: Supports markdown formatting in narrative text
- **Progress Bars**: Health bars in combat display
- **Prompts**: Numbered menu selection with validation
- **Console Output**: Consistent styling and color themes
- **Error Handling**: Rich exceptions for better stack traces during development

**Performance**: Rich initialization happens once per `RichTUI` instance. The shared console object (`console = Console()`) is reused across all method calls.

## Error Handling

### Content Loading Errors

- Missing content directory: Friendly error message + exit code 1
- Invalid YAML syntax: File path + line number details
- Schema validation failures: Field-level error descriptions
- Broken cross-references: Source and target reference details

### Runtime Errors

- No accessible regions: `SystemExit(1)` with error message
- Character stat conflicts: Validation error during character creation
- Adventure execution exceptions: Caught and logged, graceful fallback

### User Input Errors

- Invalid menu selections: Re-prompt with error message
- Keyboard interrupts (Ctrl+C): Clean exit with goodbye message
- EOF errors: Handle gracefully without stack traces

## Configuration

CLI behavior is controlled by settings in `oscilla/conf/settings.py`:

```python
class Settings:
    content_path: str = Field(
        default="./content/",
        description="Path to game content directory"
    )
```

Both `game` and `validate` commands use the same content path setting. Override via environment variable:

```bash
CONTENT_PATH=/path/to/custom/content uv run oscilla game
```
