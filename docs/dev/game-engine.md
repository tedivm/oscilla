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

## Multi-Game Loading

### `load_games()` API

The `load_games(library_root: Path)` function scans a game library directory for multiple game packages:

```python
from pathlib import Path
from oscilla.engine.loader import load_games

# Load all games from the default library directory
games = load_games(Path("content"))
# Returns: Dict[str, ContentRegistry]

# Access specific games by name
kingdom_registry = games["the-kingdom"]
testlandia_registry = games["testlandia"]
```

**Game Library Structure:**

```
content/                    ← library root
├── the-kingdom/           ← game package (name from game.yaml)
│   ├── game.yaml
│   ├── character_config.yaml
│   └── regions/
├── testlandia/           ← another game package
│   ├── game.yaml
│   ├── character_config.yaml
│   └── regions/
└── extras/               ← ignored (no game.yaml)
```

**Loading Rules:**

- Each immediate subdirectory is scanned for a `game.yaml` file
- Directories without `game.yaml` are silently ignored
- Game names come from the `metadata.name` field in `game.yaml`, not directory names
- If any game package fails validation, `ContentLoadError` is raised for the entire library

### `load()` Return Value and `LoadWarning`

Both `load()` and `load_games()` now return warnings alongside the registry:

```python
from oscilla.engine.loader import load, load_games, LoadWarning

# Single package
registry, warnings = load(Path("content/my-game"))

# All packages
games, per_game_warnings = load_games(Path("content"))
# games: Dict[str, ContentRegistry]
# per_game_warnings: Dict[str, List[LoadWarning]]
```

`LoadWarning` is a dataclass:

```python
@dataclass
class LoadWarning:
    file: Path            # manifest file that triggered the warning
    message: str          # human-readable problem description
    suggestion: str = ""  # optional fix hint (e.g. "Did you mean 'rare'?")

    def __str__(self) -> str: ...  # appends suggestion when non-empty
```

**When to emit a warning vs. raise an error:**
A `ContentLoadError` is appropriate when the content _cannot_ run correctly.
A `LoadWarning` is appropriate when the content will run, but something looks wrong or suboptimal.
See [load-warnings.md](./load-warnings.md) for the full policy and how to add new warning conditions.

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
    stats: Dict[str, int | bool | None]
    inventory: Dict[str, int]
    equipment: Dict[str, str]
    milestones: Set[str]
    prestige_count: int
    statistics: PlayerStatistics
```

**Key Methods:**

- `new_player()` - Factory for character creation
- `add_xp()` - Handle experience and leveling (supports level-down)
- `add_item()` / `remove_item()` - Inventory management
- `grant_milestone()` / `has_milestone()` - Story progress tracking
- `equip()` - Equipment slot management
- Statistics recording: `record_enemy_defeated()`, `record_location_visited()`, `record_adventure_completed()`

### Experience and Level Mechanics

**`add_xp(amount: int)` → `tuple[List[int], List[int]]`**

The `add_xp()` method handles both positive and negative experience changes, returning lists of gained and lost levels:

```python
# Gain experience and levels
gained_levels, lost_levels = player.add_xp(75)
# Returns: ([2, 3], [])  if player leveled from 1 → 3

# Lose experience and de-level
gained_levels, lost_levels = player.add_xp(-60)
# Returns: ([], [3, 2])  if player de-leveled from 3 → 1
```

**Level-Down Rules:**

- Negative XP can reduce player level, but not below level 1
- XP cannot go below 0 (clamped to zero)
- HP is capped to new max HP when leveling down
- Return tuple format: `(gained_levels, lost_levels)` where each list contains the levels traversed

**Example Usage in Effects:**

```python
gained, lost = self.player_state.add_xp(effect.amount)

for level in gained:
    self.tui.show_text(f"You reached level {level}!")

for level in lost:
    self.tui.show_text(f"You lost level {level}.")
```

## Condition System

Conditions are tree structures that evaluate player state:

**Leaf Conditions:**

- `level`: Player level comparison
- `milestone`: Milestone possession check
- `item`: Inventory check (stacks **and** instances — both stackable and equipped items)
- `character_stat`: Custom stat comparison (see `stat_source` below)
- `prestige_count`: Prestige level comparison
- `enemies_defeated`: Combat victory counting
- `locations_visited`: Exploration tracking
- `adventures_completed`: Quest completion tracking
- `item_equipped`: True when a specific non-stackable item is currently in an equipment slot
- `item_held_label`: True when any item in inventory (stacks or instances) carries the given label
- `any_item_equipped`: True when any equipped item carries the given label
- `quest_stage`: True when a quest is active and at a specific named stage

**Calendar Conditions (evaluate real-world date/time):**

All calendar predicates resolve the current date and time via `resolve_local_datetime(timezone_name)` in `oscilla/engine/calendar_utils.py`. When the game's `timezone` field is set they use that IANA zone; otherwise they fall back to server local time.

- `season_is`: Compares current meteorological season; hemisphere driven by `GameSpec.season_hemisphere`
- `moon_phase_is`: Approximate lunar phase (±1 day, 29.5-day cycle)
- `zodiac_is`: Western zodiac sign based on Sun-entry boundary dates
- `chinese_zodiac_is`: 12-year Chinese zodiac cycle
- `month_is`: Integer 1–12 or full English month name
- `day_of_week_is`: Integer 0–6 (Mon=0) or full English weekday name
- `date_is`: Month + day (optionally year) — annual or one-off date match
- `date_between`: Month/day range (start + end, each with `month` + `day`); wraps year boundary when start > end
- `time_between`: 24-hour HH:MM window; wraps midnight when start > end

**`character_stat` and `stat_source`:**

The `character_stat` predicate compares a player stat against a threshold.
By default it uses effective stats (base + all equipped-item bonuses).
Set `stat_source: base` to compare against raw stats only, bypassing equipment modifiers.
This is important for item `requires` checks — set `stat_source: base` to ensure the player's
intrinsic strength is tested, not a value inflated by the gear they are trying to equip.

```python
# evaluate() signature
def evaluate(
    condition: Condition,
    player: CharacterState,
    registry: ContentRegistry | None = None,
    exclude_item: str | None = None,
) -> bool:
```

`exclude_item` strips a named item's stat bonuses from the effective-stats calculation.
It is used by the equip-time requirement check to prevent an item from satisfying
its own requirement (self-justification guard).

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

### Passive (`oscilla/engine/steps/passive.py`)

- Auto-evaluated step with no player interaction
- Evaluates a `condition`; if true, runs `effects` and optionally `steps`
- If `condition` is absent or false, runs `bypass` effects and steps instead
- Used for silent in-adventure checks (e.g., giving the player a bonus without showing a menu)

### Effects (`oscilla/engine/steps/effects.py`)

- `XpGrantEffect`: Adds experience (may trigger leveling)
- `DamageEffect`: Reduces player HP
- `HealEffect`: Restores player HP
- `ItemGrantEffect`: Adds items to inventory
- `ItemDropEffect`: Weighted random item distribution
- `MilestoneGrantEffect`: Unlocks story milestones; triggers quest advancement and failure checks
- `StatChangeEffect`: Modifies player stats by amount (addition/subtraction)
- `StatSetEffect`: Sets player stats to specific values
- `SkillGrantEffect`: Teaches the player a new skill
- `UseItemEffect`: Activates an item's use effects
- `DispelEffect`: Removes active combat buffs/debuffs by label
- `ApplyBuffEffect`: Applies a named buff manifest during combat
- `SetPronounsEffect`: Changes the player's active pronoun set
- `QuestActivateEffect`: Starts a quest at its entry stage
- `QuestFailEffect`: Immediately fails an active quest and runs its current stage's `fail_effects`
- `EndAdventureEffect`: Terminates adventure with outcome

#### Stat Mutation Effects

**StatChangeEffect** modifies player stats by adding/subtracting an integer amount:

```yaml
effects:
  - type: stat_change
    stat: "strength"         # Must exist in character_config.yaml
    amount: 2              # Integer; negative values subtract

  - type: stat_change
    stat: "gold"
    amount: -25            # Spend gold
```

**StatSetEffect** assigns player stats to specific values:

```yaml
effects:
  - type: stat_set
    stat: "is_blessed"
    value: true               # Boolean assignment

  - type: stat_set
    stat: "strength"
    value: 20                # Override current value
```

**Stat Bounds** — `StatDefinition` accepts an optional `bounds` field with `min` and/or `max` integer constraints. The engine enforces these at effect application time in `effects.py` (first-line enforcement) and inside `CharacterState.set_stat()` (INT64 backstop):

- When a computed value exceeds the bounds, it is clamped silently to the allowed range.
- A `logger.warning` is emitted and the player is shown a TUI notification.
- The clamping in `set_stat()` uses INT64 limits (`-(2**63)` to `(2**63) - 1`) matching the PostgreSQL `BIGINT` column.

**Validation Rules:**

- Both effects require the stat name to exist in `CharacterConfig`
- Stat types are `int` and `bool` only — `float` and `str` are not supported and cause a `ContentLoadError` at load time
- `StatChangeEffect` cannot be applied to `bool` stats (load-time validation error)
- `StatSetEffect` value must match the stat type (`int` or `bool`)
- `bounds` cannot be specified on `bool` stats (load-time validation error)
- `bounds` cannot be specified on `bool` stats (load-time validation error)
- Load-time validation prevents runtime type errors

## Quest Engine (`oscilla/engine/quest_engine.py`)

Quest progression is handled entirely by `quest_engine.py`. This module owns stage advancement and completion logic, and is imported by `effects.py` and `session.py` without creating circular dependencies.

### Two advancement functions

**`_advance_quests_silent(player, registry)`** — synchronous, no effects.

Called once on every character load (in `session.py` after `load_character`). Re-evaluates every active quest against the player's current milestone set and advances stages without running `completion_effects`. This corrects any desync between quest state and milestone state that could accumulate between sessions or after content updates.

**`evaluate_quest_advancements(player, registry, tui)`** — async, full effects.

Called after every `MilestoneGrantEffect` and after every `QuestActivateEffect` at runtime. Evaluates all active quests, advances stages, and fires `completion_effects` on terminal stages. TUI notifications are sent for quest completion. Multiple chained advancements (where the next stage also has a satisfied milestone) are followed in the same call via an inner `while True` loop.

### Call sites

| Location | Function called | When |
|----------|----------------|------|
| `session.py` — `_select_or_create_character()` | `_advance_quests_silent` | After loading a saved character |
| `effects.py` — `MilestoneGrantEffect` case | `evaluate_quest_advancements` | After granting any milestone |
| `effects.py` — `QuestActivateEffect` case | `evaluate_quest_advancements` | After activating a quest |

### `QuestActivateEffect`

The `QuestActivateEffect` model in `adventure.py` accepts a single field: `quest_ref` (the name of the Quest manifest to activate). The handler in `effects.py` registers the quest at its `entry_stage`, sends a TUI notification, and immediately calls `evaluate_quest_advancements` — so a quest whose entry stage milestone the player already holds advances in the same tick as activation.

Activating an already-active or already-completed quest is a logged no-op.

### `completion_effects` on `QuestStage`

Terminal stages in quest manifests accept a `completion_effects` list. The model validator `validate_stage_graph` rejects non-terminal stages that declare `completion_effects`. Effects are run by `evaluate_quest_advancements` after the quest is marked complete and the TUI completion notification is shown.

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

## Skill and Buff System

### Overview

Skills and buffs are first-class manifest kinds processed by the content loader alongside enemies, items, and adventures. The runtime objects that hold live combat state (`CombatContext`, `ActiveCombatEffect`) are ephemeral dataclasses — they exist only for the duration of a single `run_combat()` call and are never persisted.

### `CombatContext` Lifecycle

`CombatContext` (`oscilla/engine/combat_context.py`) is constructed at the start of `run_combat()` and torn down when combat ends (win, defeat, or flee). It carries all per-combat state that is too transient for `CharacterState`:

| Field | Type | Purpose |
|---|---|---|
| `enemy_hp` | `int` | Current enemy HP; mirrored back to `step_state` each round |
| `turn` | `int` | Current turn number (1-indexed, incremented after each round) |
| `active_effects` | `List[ActiveCombatEffect]` | Active buffs on player and enemy |
| `skill_uses_this_combat` | `Dict[str, int]` | Turn-scope cooldown tracking: skill_ref → last turn used |
| `enemy_resources` | `Dict[str, int]` | Live resource values for enemy skill costs (initialized from `EnemySpec.skill_resources`) |

On combat exit, `CombatContext` is discarded. Only `CharacterState.skill_cooldowns` (adventure-scope cooldowns) is written back to the player state.

### `ActiveCombatEffect`

Each active buff is represented as an `ActiveCombatEffect`:

| Field | Type | Purpose |
|---|---|---|
| `label` | `str` | Buff manifest `name` — stable identity used by `DispelEffect` |
| `target` | `"player"` \| `"enemy"` | Who the buff is applied to |
| `turns_remaining` | `int` | Decremented at round start; removed when 0 |
| `per_turn_effects` | `List[Effect]` | Dispatched through `run_effect()` each round |
| `modifiers` | `List[CombatModifier]` | Passive damage-arithmetic modifiers queried during attack/defense |

### `available_skills()` Contract

`CharacterState.available_skills(registry)` returns the complete set of skill refs the character can currently activate. It combines three sources:

1. `known_skills` — permanently learned skills.
2. Skills from `ItemSpec.grants_skills_equipped` — only for items that are in an active equipment slot.
3. Skills from `ItemSpec.grants_skills_held` — for any item present in inventory (stacks or instances), equipped or not.

Without a registry, only `known_skills` is returned. This makes the method safe to call from contexts where items cannot be resolved (e.g., offline condition checks).

### Cooldown Tracking

Two cooldown scopes exist:

**Turn-scope** (`CombatContext.skill_uses_this_combat`): stored as `skill_ref → turn_last_used`. A skill with `scope: turn, count: 1` can be used at most once per turn. The check is `current_turn - last_used < cooldown.count`. Turn-scope cooldowns reset at the start of every combat.

**Adventure-scope** (`CharacterState.skill_cooldowns`): stored as `skill_ref → adventures_remaining`. Decremented at adventure start by `tick_skill_cooldowns()`. Removed when the count reaches 0. These values are persisted to the database and survive between play sessions.

### `SkillCondition` Modes

`SkillCondition` (in `oscilla/engine/models/base.py`, evaluated in `oscilla/engine/conditions.py`) supports two modes:

- **`learned`** (default): checks `CharacterState.known_skills` directly. No registry required; always fast.
- **`available`**: calls `CharacterState.available_skills(registry)` which includes item-granted skills. Requires a registry.

### `run_effect()` `combat` Parameter

`run_effect()` (in `oscilla/engine/steps/effects.py`) accepts an optional `combat: CombatContext | None` parameter. When `None`:

- `ApplyBuffEffect` logs a WARNING and is skipped — buffs only exist in combat.
- `DispelEffect` logs DEBUG and is skipped — nothing to dispel outside combat.
- `StatChangeEffect` and `HealEffect` with `target="enemy"` log a WARNING and are skipped.

This design means items and skills with both combat and non-combat effects (e.g., a potion that dispels a burn and also heals HP) work correctly in overworld contexts without special-casing in content.

### Damage Modifier Helpers

Three pure helper functions in `oscilla/engine/steps/combat.py` apply modifier arithmetic:

- **`_apply_damage_amplify(base, target, ctx)`** — scans `ctx.active_effects` for `DamageAmplifyModifier` on `target`; sums all `percent` values and scales `base` by `(1 + total/100)`.
- **`_apply_incoming_modifiers(base, target, ctx)`** — reduces damage by `damage_reduction` modifiers and additively increases it by `damage_vulnerability` modifiers. Final formula: `base * max(0.0, 1.0 - reduction/100 + vulnerability/100)`.
- **`_apply_reflect(base, target, ctx, apply_reflect_damage)`** — sums `damage_reflect` modifiers on `target` and calls `apply_reflect_damage(reflected_amount)` if non-zero.

### Equipment Buff Grants at Combat Start

At the start of every `run_combat()` call, before the first round, the engine:

1. Iterates all items currently in an equipment slot → applies each `grants_buffs_equipped` `BuffGrant` via `ApplyBuffEffect`.
2. Iterates all items in inventory (stacks + instances) → applies each `grants_buffs_held` `BuffGrant` via `ApplyBuffEffect`.

Each `BuffGrant.variables` dict is merged with the buff manifest's own `variables` defaults at apply time. The resulting resolved `percent` values are substituted into the modifier's `ActiveCombatEffect`.

### Loader Validation

The content loader (`oscilla/engine/loader.py`) validates skill and buff cross-references at load time:

- All `skill_ref` values in items and enemies must name known `Skill` manifests.
- All `buff_ref` values in `apply_buff` effects and `grants_buffs_*` must name known `Buff` manifests.
- All variable override keys in `ApplyBuffEffect.variables` and `BuffGrant.variables` must be declared in the target buff's `variables` block.
- `CharacterConfig.skill_resources` bindings: both `stat` and `max_stat` must reference declared stats.

## Performance Considerations

- Content is loaded once at startup and cached in memory
- Player state changes are applied immediately (no deferred updates)
- Condition evaluation is recursive but typically shallow
- Combat and choice steps may require multiple user interactions

## Dynamic Template Engine

The template engine (`oscilla/engine/templates.py`) provides Jinja2-based dynamic content. Templates are compiled once at load time and rendered at runtime.

### Template Lifecycle

```
load() → _collect_all_template_strings()
       → GameTemplateEngine(stat_names)
       → _validate_templates()
             precompile_and_validate(raw, template_id, context_type)
                  preprocess_pronouns(raw)      # expand {they} etc.
                  env.from_string(processed)     # Jinja2 compile
                  template.render(mock_ctx)      # catch unknown names
             → ContentLoadError on any failure
       → ContentRegistry.build(..., template_engine=engine)

adventure_pipeline._dispatch()
       → _build_context()        # ExpressionContext from CharacterState
       → run_narrative(step, player, tui, run_effects, registry, ctx)
             engine.render(template_id, ctx)   # cached template
       → _run_effects(effects, ctx)
             run_effect(..., ctx)
                  engine.render_int(template_id, ctx)  # for numeric fields
```

### `GameTemplateEngine`

```python
class GameTemplateEngine:
    def __init__(self, stat_names: List[str]) -> None: ...
    def precompile_and_validate(
        self, raw: str, template_id: str, context_type: str
    ) -> None: ...
    def render(self, template_id: str, ctx: ExpressionContext) -> str: ...
    def render_int(self, template_id: str, ctx: ExpressionContext) -> int: ...
    def is_template(self, value: str) -> bool: ...
```

- **`precompile_and_validate`** — compiles the raw string (after pronoun preprocessing) and performs a mock render to catch unknown context references at load time. Raises `TemplateValidationError` on failure.
- **`render`** / **`render_int`** — looks up the pre-compiled template by ID and renders it against a live `ExpressionContext`. `render_int` coerces the output to `int` for numeric effect fields.
- **`is_template`** — returns `True` when the string contains `{{` or `{%`.
- Template IDs are Python object IDs (`id(effect)` / `id(step)`), stable because manifest objects are parsed once and reused throughout the process lifetime.

### `ExpressionContext` and `PlayerContext`

```python
@dataclass
class ExpressionContext:
    player: PlayerContext
    combat: CombatContextView | None = None

@dataclass
class PlayerContext:
    name: str
    level: int
    title: str
    iteration: int
    hp: int
    max_hp: int
    stats: Dict[str, Any]
    milestones: PlayerMilestoneView
    pronouns: PlayerPronounView

    @classmethod
    def from_character(cls, state: CharacterState) -> PlayerContext: ...
```

`PlayerMilestoneView` exposes `has(name: str) -> bool` for template conditions.

`PlayerPronounView` exposes all grammatical fields (`subject`, `object`, `possessive`, `possessive_standalone`, `reflexive`, `uses_plural_verbs`).

### Pronoun Preprocessing

`preprocess_pronouns(template_str: str) -> str` runs before Jinja2 compilation. It replaces shorthand placeholders like `{they}`, `{Their}`, `{is}`, `{are}`, `{was}`, `{were}`, `{has}`, `{have}` with the equivalent Jinja2 expression that reads from `player.pronouns`. Capitalisation of the placeholder (`{they}` vs `{They}` vs `{THEY}`) controls capitalisation of the output via Jinja2 `| capitalize` / `| upper` filters.

### Adding New Built-in Functions or Filters

- **Built-in functions** — add to `SAFE_GLOBALS` in `templates.py`. If the function has no Jinja2/engine dependency (e.g., a calendar utility), place the implementation in `oscilla/engine/calendar_utils.py` and import it.
- **Filters** — implement as a plain Python function and add to `SAFE_FILTERS`. The key becomes the filter name in templates.
- Both `SAFE_GLOBALS` and `SAFE_FILTERS` are injected into the `SandboxedEnvironment` and also merged into the render context dict, making them available both as globals and as `{% set %}` assignments.
- The mock context (`build_mock_context`) must also expose any new stat names or nested attributes that the new function may reference; otherwise valid uses will fail load-time validation.


## Item System Enhancements

### Item Labels

Authors declare a vocabulary of item labels in `game.yaml` via `item_labels`.
Each label has display metadata (color, sort priority) but no hardcoded meaning.

```python
class ItemLabelDef:
    name: str
    color: str = ""          # Rich markup color string, e.g. "gold1"
    description: str = ""
    sort_priority: int = 0   # Lower value = sorted earlier in inventory
```

Items list their labels in `spec.labels`. At load time, `_validate_labels()` emits a
`LoadWarning` for any label that is not declared in `game.item_labels`, with a
Levenshtein-distance suggestion when a close match exists.

### Item Requirements (`EquipSpec.requires`)

An equippable item may declare a `requires: Condition` in its `EquipSpec`.
The condition is evaluated at equip time with `stat_source: base` recommended
so the item's own stat bonuses cannot satisfy its own requirement.

Two helpers in `character.py` support requirement enforcement:

```python
def validate_equipped_requires(
    player: CharacterState,
    registry: ContentRegistry,
) -> List[str]:
    """Return item_ref strings for equipped items whose requires is no longer met."""

def cascade_unequip_invalid(
    player: CharacterState,
    registry: ContentRegistry,
) -> List[str]:
    """Unequip all failing items in a fixed-point loop; return their display names."""
```

`cascade_unequip_invalid` is called by the TUI after every unequip action and by
stat-mutating step effects (`stat_change`, `stat_set`) to ensure consistency.

At session load, `_warn_invalid_equipped()` in `session.py` logs a `logger.warning`
for each equipped item whose requirement is no longer satisfied — but does **not**
unequip it (player intent is preserved across sessions). The TUI `StatusPanel`
also renders a visible red warning section listing any invalid items.

### Item Charges

Non-stackable items may declare `charges: int` in their spec.
`ItemInstance.charges_remaining` is initialised from `spec.charges` when the
instance is created and decremented on each use. When `charges_remaining` reaches
zero the instance is removed automatically.

`charges` is mutually exclusive with `consumed_on_use: true` and `stackable: true`;
the model validator raises `ValueError` for either combination.

### Passive Effects

`game.yaml` may declare `passive_effects` — unconditional or condition-gated modifiers
that always apply when the player holds or has equipped certain items.

```python
class PassiveEffect:
    condition: Condition | None       # evaluated with registry=None
    stat_modifiers: List[StatModifier]
    skill_grants: List[SkillGrant]
```

`effective_stats()` and `available_skills()` in `character.py` loop `registry.game.passive_effects`
and apply matching effects. Because passive effects are evaluated with `registry=None`,
conditions that require a registry — `item_held_label`, `any_item_equipped` — cannot be honored
and trigger a `LoadWarning` at load time. Similarly, `character_stat` conditions with
`stat_source: effective` also emit a warning since the registry is unavailable.

---

## Dual Clock Model

The engine maintains two independent integer counters on each character iteration:

| Clock | Field | Behavior |
|---|---|---|
| Internal | `internal_ticks` | Monotone, strictly non-decreasing. Represents the character's total play-time in ticks. Used for cooldown checks. |
| Game | `game_ticks` | Narrative clock. Advances with adventures but can be adjusted backward by `adjust_game_ticks` effects. Drives in-game calendar conditions and era progression. |

Both clocks start at 0 and advance by the adventure's tick cost on completion.

### Tick Cost Resolution

Each adventure completion charges both clocks by `_resolve_tick_cost()` in `pipeline.py`:

1. If the adventure manifest sets `spec.ticks`, that value is used.
2. Otherwise, `game.spec.time.ticks_per_adventure` is used (when the time system is active).
3. When the time system is inactive, tick cost is 0 and both clocks stay at 0.

### `adjust_game_ticks` Effect

The `adjust_game_ticks` step effect adjusts `game_ticks` by a signed delta:

```yaml
- type: adjust_game_ticks
  delta: -10        # reduce game_ticks by 10 (clamped at 0)
```

The delta is applied during adventure step execution — before the pipeline's end-of-adventure tick advance. `internal_ticks` is never affected.

### `InGameTimeResolver`

`InGameTimeResolver` (`oscilla/engine/ingame_time.py`) provides a read-only view of the current in-game time for a given tick count. It is built from the `GameTimeSpec` by `compute_epoch_offset()` in `loader.py` and stored as `registry.ingame_time_resolver`.

It exposes:

- `cycles` — a dict of `CycleState` (position, label, count of full cycles elapsed)
- `eras` — a dict of `EraState` (active flag, count of full era-epochs elapsed)
- `update_era_states(game_ticks, character_era_state)` — applies era start/end latch logic

#### Cycle DAG

Cycles form a DAG with exactly one root cycle (type `ticks`). All other cycles derive from a parent:

```
hour (root, count=24)
  └── season (count=4)
        └── year (count=10)
  └── lunar_cycle (count=28)
```

The position of a derived cycle advances whenever the parent completes a full revolution. For example, a `season` cycle with `parent: hour` and `count: 4` advances one slot every 24 hours.

#### Epoch

`epoch` offsets the starting position of named cycles so tick 0 maps to a specific calendar position. For example:

```yaml
epoch:
  season: Spring     # start in the Spring slot
```

The loader calls `compute_epoch_offset()` to translate the cycle position (label or 1-based integer) into the equivalent number of root ticks to subtract from the query.

#### Eras

Eras are named periods with an optional `start_condition` and `end_condition`. They are evaluated via `update_era_states()` each time character state is saved:

- An era without `start_condition` is always active from tick 0.
- An era with `start_condition` activates when the condition first evaluates to true.
- Once active, an era remains active until `end_condition` evaluates to true (if set).
- The latch nature means conditions are not re-evaluated once their transition has fired.

Era `count` tracks completed `epoch_count` × `tracks` cycle revolutions since the era started.

### Condition Types

Three conditions operate against the dual clock state:

| Type | Description |
|---|---|
| `game_calendar_time_is` | Numeric comparison (gt/gte/lt/lte/eq/mod) against `internal_ticks` or `game_ticks` |
| `game_calendar_cycle_is` | Tests the current label of a named cycle |
| `game_calendar_era_is` | Tests whether a named era is active or inactive |

All three evaluate to `False` with a log warning when the time system is not configured in `game.yaml`.

### Persistence

Tick state is saved by `update_character_tick_state()` in `services/character.py`. The following fields are written on every adventure completion:

- `character_iterations.internal_ticks`
- `character_iterations.game_ticks`
- `character_iteration_adventure_state.last_completed_at_ticks` (per adventure)
- `character_iteration_era_state` rows (insert/update for each era with a changed state)
