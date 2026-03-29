# Game Engine

The Oscilla game engine is a flexible text-based adventure engine built around a manifest-driven content system. This document covers the engine internals and architecture.

## Architecture Overview

The engine is organized into several key modules:

```
oscilla/engine/
├── models/          # Pydantic models for manifest schemas
├── steps/           # Adventure step handler implementations
├── registry.py      # Content storage and lookup
├── loader.py        # Content scanning, parsing, and validation
├── conditions.py    # Condition evaluation engine
├── player.py        # Player state management
├── pipeline.py      # Adventure execution orchestration
├── tui.py           # Terminal user interface implementation
└── signals.py       # Internal control flow signals
```

### Data Flow

1. **Content Loading**: `ContentLoader` scans YAML manifests → validates schemas → builds cross-references → creates `ContentRegistry`
2. **Adventure Execution**: `AdventurePipeline` receives player state and content registry → executes adventure steps → updates player state
3. **Step Processing**: Each step type has a dedicated handler that interacts with the player through the `TUICallbacks` interface

## Core Interfaces

### TUICallbacks Protocol

The `TUICallbacks` protocol defines the interface between engine logic and user interaction. All player-facing output goes through this interface:

```python
class TUICallbacks(Protocol):
    def show_text(self, text: str) -> None:
        """Display narrative or informational text."""

    def show_menu(self, prompt: str, options: List[str]) -> int:
        """Present numbered choices, return selected index."""

    def show_combat_round(self, player_hp: int, max_hp: int,
                         enemy_name: str, enemy_hp: int, enemy_max_hp: int) -> None:
        """Display combat status during fights."""

    def wait_for_ack(self) -> None:
        """Pause for player acknowledgment."""
```

**Implementation Notes:**

- Production code uses `RichTUI` (in `oscilla/engine/tui.py`)
- Tests use `MockTUI` (in `tests/engine/conftest.py`)
- Step handlers never import `RichTUI` directly — they receive `TUICallbacks`

### Signal Protocol

The engine uses custom exceptions for internal flow control:

```python
class _GotoSignal(Exception):
    """Jump to a labeled step within the current adventure."""

class _EndSignal(Exception):
    """Terminate the adventure with a specific outcome."""
```

These signals allow effects and steps to alter execution flow without complex return value handling. They are caught and handled entirely within `AdventurePipeline.run()`.

## Content Registry

The `ContentRegistry` provides typed access to loaded content:

```python
class ContentRegistry:
    game: GameManifest
    character_config: CharacterConfigManifest
    regions: Dict[str, RegionManifest]
    locations: Dict[str, LocationManifest]
    adventures: Dict[str, AdventureManifest]
    enemies: Dict[str, EnemyManifest]
    items: Dict[str, ItemManifest]
    recipes: Dict[str, RecipeManifest]
    quests: Dict[str, QuestManifest]
    classes: Dict[str, ClassManifest]
```

Content is accessed by reference name (e.g., `registry.items["health-potion"]`).

## Player State

The `PlayerState` dataclass tracks all mutable game state:

```python
@dataclass
class PlayerState:
    name: str
    level: int
    xp: int
    hp: int
    max_hp: int
    stats: Dict[str, int | float | str | bool | None]
    inventory: Dict[str, int]
    equipment: Dict[str, str]
    milestones: Set[str]
    prestige_count: int
    statistics: PlayerStatistics
```

**Key Methods:**

- `new_player()` - Factory for character creation
- `add_xp()` - Handle experience and leveling
- `add_item()` / `remove_item()` - Inventory management
- `grant_milestone()` / `has_milestone()` - Story progress tracking
- `equip()` - Equipment slot management
- Statistics recording: `record_enemy_defeated()`, `record_location_visited()`, `record_adventure_completed()`

## Condition System

Conditions are tree structures that evaluate player state:

**Leaf Conditions:**

- `level`: Player level comparison
- `milestone`: Milestone possession check
- `item`: Inventory quantity check
- `character_stat`: Custom stat comparison
- `prestige_count`: Prestige level comparison
- `enemies_defeated`: Combat victory counting
- `locations_visited`: Exploration tracking
- `adventures_completed`: Quest completion tracking

**Logical Operators:**

- `all`: Requires all child conditions to pass
- `any`: Requires at least one child condition to pass
- `not`: Logical negation of child condition

Conditions are evaluated recursively by `evaluate(condition, player_state)` in `oscilla/engine/conditions.py`.

## Adventure Step Types

Each step type has a dedicated handler module:

### Narrative (`oscilla/engine/steps/narrative.py`)

- Displays text passage
- Waits for player acknowledgment
- No state changes

### Combat (`oscilla/engine/steps/combat.py`)

- Turn-based combat loop
- Player/enemy attack exchange
- Handles win/defeat/flee outcomes
- Updates player HP and records statistics

### Choice (`oscilla/engine/steps/choice.py`)

- Filters options by condition requirements
- Presents menu to player
- Executes selected branch recursively

### Stat Check (`oscilla/engine/steps/stat_check.py`)

- Evaluates condition against player state
- Branches to `on_pass` or `on_fail` steps

### Effects (`oscilla/engine/steps/effects.py`)

- `XpGrantEffect`: Adds experience (may trigger leveling)
- `ItemDropEffect`: Weighted random item distribution
- `MilestoneGrantEffect`: Unlocks story milestones
- `EndAdventureEffect`: Terminates adventure with outcome

## Testing with MockTUI

Engine tests use `MockTUI` to capture and verify interface interactions:

```python
def test_combat_shows_status(base_player, minimal_registry, mock_tui):
    adventure = AdventureManifest(...)
    pipeline = AdventurePipeline(minimal_registry, base_player, mock_tui)

    outcome = pipeline.run(adventure_ref)

    # Verify captured interactions
    assert len(mock_tui.combat_rounds) == 3
    assert "You defeated" in mock_tui.texts[-1]
```

**MockTUI Features:**

- Records all calls: `texts`, `menus`, `combat_rounds`, `acks`
- Configurable menu responses: `set_menu_responses([0, 1, 0])`
- No actual terminal output during tests

## Extension Points

### Adding New Step Types

1. Create handler in `oscilla/engine/steps/your_step.py`
2. Add Pydantic model to `oscilla/engine/models/adventure.py`
3. Register dispatcher in `AdventurePipeline._dispatch_step()`
4. Add tests using existing fixture patterns

### Adding New Effect Types

1. Add Pydantic model to `oscilla/engine/models/adventure.py`
2. Add handler to `run_effect()` in `oscilla/engine/steps/effects.py`
3. Follow existing patterns for player state updates

### Adding New Condition Types

1. Add Pydantic model to `oscilla/engine/models/base.py`
2. Add evaluation logic to `evaluate()` in `oscilla/engine/conditions.py`
3. Update discriminated union in `Condition` type alias

### Adding New Manifest Kinds

1. Create model module in `oscilla/engine/models/your_kind.py`
2. Add fields to `ContentRegistry` in `oscilla/engine/registry.py`
3. Add parsing logic to `ContentLoader` in `oscilla/engine/loader.py`
4. Add validation and cross-reference checking as needed

## Character Persistence

### GameSession Orchestrator

`GameSession` (in `oscilla/engine/session.py`) ties together user identity, character selection, and the adventure pipeline for a single TUI session. It is used exclusively by the TUI layer; the web layer accesses the service layer directly.

```python
async with GameSession(
    registry=registry,
    tui=tui,
    db_session=db_session,
    character_name=None,  # optional --character-name override
) as session:
    await session.start()          # resolve user → select/create character → acquire lock
    await session.run_adventure("my-adventure")
```

**`start()` behavior:**

1. Derives the user key from the environment and calls `get_or_create_user()`.
2. If `--character-name` is set, looks up the character by name; creates it if absent.
3. If no `--character-name` is set:
   - Zero characters → prompts for a name and creates a new character.
   - One character → auto-loads without a menu.
   - N characters → presents a selection menu (newest first) with a "New Character" option.
4. Acquires the session soft-lock on the active `CharacterIterationRecord`.

`close()` (called automatically on context exit) releases the soft-lock even if an exception propagates.

### PersistCallback Protocol

`PersistCallback` (in `oscilla/engine/pipeline.py`) is an async callable that `AdventurePipeline` fires at three lifecycle points:

| Event | When fired |
|---|---|
| `step_start` | Before each adventure step is dispatched |
| `combat_round` | After each pair of player/enemy attacks |
| `adventure_end` | After `active_adventure` is cleared on the player state |

`GameSession._on_state_change()` implements it. At each event it diffs `_character` against `_last_saved_state` and writes only the changed domains (stats, inventory, equipment, milestones, quests, statistics scalars, and adventure progress). Unmodified data is never re-written.

On `StaleDataError` (concurrent write detected), the handler reloads the snapshot from the DB and retries once.

### Content-Drift Resilience

When a character is loaded from the DB, `CharacterState.from_dict()` reconciles stored state against the current `CharacterConfigManifest`:

- **Unknown stat in DB** — a stat that was removed from the manifest is silently dropped with a WARNING log.
- **Missing stat in DB** — a stat newly added to the manifest is injected with its manifest default.
- **Stale adventure reference** — an `active_adventure` whose `adventure_ref` no longer exists in the registry is cleared to `None` with a WARNING log.

This ensures that content updates (renaming stats, removing adventures) do not break existing characters.

## Performance Considerations

- Content is loaded once at startup and cached in memory
- Player state changes are applied immediately (no deferred updates)
- Condition evaluation is recursive but typically shallow
- Combat and choice steps may require multiple user interactions
