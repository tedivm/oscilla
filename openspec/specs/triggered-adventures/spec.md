# Triggered Adventures

## Purpose

The triggered adventures system enables adventures to fire automatically in response to game events — without the player selecting them from a location pool. Adventures are routed to triggers via `game.yaml` configuration and processed by a FIFO drain queue on `CharacterState`.

## Requirements

### Requirement: game.yaml trigger configuration schema

`GameSpec` SHALL include two new optional blocks: `triggers` (a `GameTriggers` model) and `trigger_adventures` (a `Dict[str, List[str]]`). Both SHALL default to empty values if absent so existing game packages without trigger configuration continue to load without modification.

`GameTriggers` SHALL contain:

- `custom: List[str]` — declared custom trigger names, default empty
- `on_game_rejoin: GameRejoinTrigger | None` — optional, with `absence_hours: int` (min 1)
- `on_stat_threshold: List[StatThresholdTrigger]` — each entry with `stat: str`, `threshold: int`, `name: str`

`trigger_adventures` maps a trigger name (string) to an ordered list of adventure refs (strings). Adventures fire top-to-bottom per trigger in declaration order.

#### Scenario: game.yaml with no triggers block loads cleanly

- **WHEN** a `game.yaml` that has no `triggers` or `trigger_adventures` fields is loaded
- **THEN** the `GameSpec` loads without error, `spec.triggers` is an empty `GameTriggers`, and `spec.trigger_adventures` is `{}`

#### Scenario: trigger_adventures wires an adventure to a built-in trigger

- **WHEN** `game.yaml` contains `trigger_adventures: {on_character_create: [welcome-adventure]}`
- **THEN** `registry.trigger_index["on_character_create"]` equals `["welcome-adventure"]` after content load

#### Scenario: Multiple adventures per trigger maintain declaration order

- **WHEN** `trigger_adventures: {on_level_up: [adv-a, adv-b, adv-c]}` is declared
- **THEN** adventures are run in the order `adv-a → adv-b → adv-c` when the trigger fires

---

### Requirement: Load-time validation of trigger_adventures keys

The content loader SHALL validate every key in `trigger_adventures` against the set of known trigger names for the loaded game. Unknown keys SHALL produce a load warning (not a fatal error, consistent with the load-warnings system).

Known trigger names are:

- `on_character_create` (always valid)
- `on_level_up` (always valid)
- `on_outcome_<name>` for each name in the built-in outcome set (`completed`, `defeated`, `fled`) plus each name in `spec.outcomes`
- `on_game_rejoin` (valid only when `triggers.on_game_rejoin` is configured)
- `<threshold.name>` for each entry in `triggers.on_stat_threshold`
- Each name in `triggers.custom`

Each adventure ref in every list SHALL also be validated against the registered adventure manifests. A ref that doesn't resolve SHALL produce a load warning.

Duplicate `name` values among `triggers.on_stat_threshold` entries SHALL produce a load warning.

#### Scenario: Unknown trigger key produces load warning

- **WHEN** `trigger_adventures` contains `{on_unknown_event: [some-adv]}`
- **THEN** a load warning is emitted for the unknown key and the adventure list is ignored at runtime

#### Scenario: on_outcome_<custom> is valid when outcome is declared

- **WHEN** `game.yaml` has `outcomes: [discovered]` and `trigger_adventures: {on_outcome_discovered: [disc-adv]}`
- **THEN** no load warning is produced for `on_outcome_discovered`

#### Scenario: on_outcome_<custom> without declaration produces warning

- **WHEN** `trigger_adventures: {on_outcome_discovered: [disc-adv]}` but `discovered` is not in `spec.outcomes`
- **THEN** a load warning is produced for `on_outcome_discovered`

#### Scenario: Unknown adventure ref produces load warning

- **WHEN** a trigger_adventures entry references `[no-such-adv]` and no adventure with that name is registered
- **THEN** a load warning is produced identifying the missing adventure ref

#### Scenario: Duplicate threshold name produces load warning

- **WHEN** two `on_stat_threshold` entries have the same `name` field
- **THEN** a load warning is produced identifying the duplicate name

---

### Requirement: Pending trigger queue on CharacterState

`CharacterState` SHALL include `pending_triggers: List[str]` (FIFO queue), default empty. All mutations to the queue SHALL go through `enqueue_trigger(trigger_name: str, max_depth: int)`. The queue maximum depth SHALL be read from `GameTriggers.max_trigger_queue_depth` (default `6`, minimum `1`, configurable in `game.yaml`). `enqueue_trigger()` SHALL silently drop new entries at or above this limit and emit a `logger.warning`.

The queue SHALL be persisted to a dedicated `character_iteration_pending_triggers` table with composite PK `(iteration_id, position)`, following the same pattern as milestones, skills, and other multi-valued character state. The `position` integer column preserves FIFO order. Rows are replaced atomically (delete + insert) at `adventure_end`.

#### Scenario: Trigger is appended to the end of the queue

- **WHEN** `enqueue_trigger("on_level_up")` is called on a player with `pending_triggers = ["on_character_create"]`
- **THEN** `pending_triggers == ["on_character_create", "on_level_up"]`

#### Scenario: Queue depth limit prevents overflow

- **WHEN** the queue is at its configured maximum depth and `enqueue_trigger()` is called again
- **THEN** `len(pending_triggers)` remains at the maximum, a warning is logged, and no exception is raised

#### Scenario: Queue depth limit is configurable per game

- **WHEN** `game.yaml` sets `triggers.max_trigger_queue_depth: 12`
- **THEN** the queue accepts up to 12 entries before dropping and warning

#### Scenario: pending_triggers defaults to empty for new characters

- **WHEN** a new `CharacterState` is created via `CharacterState.new_character()`
- **THEN** `pending_triggers == []`

#### Scenario: pending_triggers persists across sessions

- **WHEN** a character has `pending_triggers = ["on_level_up"]` at `adventure_end`
- **THEN** loading that character from the database restores `pending_triggers == ["on_level_up"]`

#### Scenario: Character with no pending trigger rows loads with empty list

- **WHEN** a `character_iterations` row has no corresponding rows in `character_iteration_pending_triggers`
- **THEN** the loaded character has `pending_triggers == []`

---

### Requirement: on_character_create trigger detection

When a new character is created by `_create_new_character()`, the engine SHALL call `state.enqueue_trigger("on_character_create")` if `"on_character_create"` is a key in `registry.trigger_index`. This MUST happen before the first persist so the trigger survives into the Drain A call.

#### Scenario: New character queues on_character_create

- **WHEN** a new character is created and `on_character_create` is wired in `trigger_adventures`
- **THEN** `pending_triggers` contains `"on_character_create"` immediately after `_create_new_character()` returns

#### Scenario: No wiring means no queue entry

- **WHEN** a new character is created and `on_character_create` is NOT in `trigger_adventures`
- **THEN** `pending_triggers` is empty after `_create_new_character()` returns

---

### Requirement: on_game_rejoin trigger detection

At session start on the load path (an existing character, not a new one), the engine SHALL compare `characters.updated_at` to the current time. If `triggers.on_game_rejoin` is configured, `"on_game_rejoin"` is in `registry.trigger_index`, and the absence exceeds `absence_hours`, then `state.enqueue_trigger("on_game_rejoin")` SHALL be called.

`characters.updated_at` is the column touched at every `adventure_end` event via `touch_character_updated_at()` and serves as the last-activity timestamp.

#### Scenario: Absent player triggers on_game_rejoin

- **WHEN** a character's `updated_at` is more than `absence_hours` ago and `on_game_rejoin` is wired
- **THEN** `pending_triggers` contains `"on_game_rejoin"` after `start()` completes the load path

#### Scenario: Recent player does not trigger on_game_rejoin

- **WHEN** a character's `updated_at` is within the `absence_hours` window
- **THEN** `pending_triggers` does not contain `"on_game_rejoin"`

#### Scenario: No on_game_rejoin config means no detection

- **WHEN** `triggers.on_game_rejoin` is `None` even if `trigger_adventures` has an `on_game_rejoin` key
- **THEN** the rejoin trigger is never queued

---

### Requirement: on_level_up trigger detection

In the `xp_grant` effect handler, for each level in the `levels_gained` list returned by `add_xp()`, the engine SHALL call `player.enqueue_trigger("on_level_up")`. Multi-level jumps result in one queue entry per level gained.

#### Scenario: Single level up queues one trigger

- **WHEN** an `xp_grant` effect causes the player to gain exactly one level
- **THEN** `pending_triggers` contains exactly one `"on_level_up"` entry

#### Scenario: Multi-level jump queues multiple triggers

- **WHEN** an `xp_grant` effect causes the player to gain two levels in one step
- **THEN** `pending_triggers` contains two `"on_level_up"` entries

#### Scenario: No level gained means no queue entry

- **WHEN** an `xp_grant` effect adds XP that does not cross any threshold
- **THEN** `pending_triggers` is unchanged

---

### Requirement: on_outcome_<name> trigger detection

After each call to `session.run_adventure()` returns an outcome, the engine SHALL construct the trigger key `f"on_outcome_{outcome.value}"` and call `player.enqueue_trigger(trigger_key)` if that key is in `registry.trigger_index`.

#### Scenario: Defeat outcome queues on_outcome_defeated

- **WHEN** an adventure ends with the `defeated` outcome and `on_outcome_defeated` is wired in `trigger_adventures`
- **THEN** `pending_triggers` contains `"on_outcome_defeated"` after `run_adventure()` returns

#### Scenario: Completed outcome queues on_outcome_completed

- **WHEN** an adventure ends with the `completed` outcome and `on_outcome_completed` is wired
- **THEN** `pending_triggers` contains `"on_outcome_completed"` after `run_adventure()` returns

#### Scenario: No wiring for outcome means no queue entry

- **WHEN** an adventure ends with the `fled` outcome and `on_outcome_fled` is NOT in `trigger_adventures`
- **THEN** `pending_triggers` is not modified by the outcome

---

### Requirement: on_stat_threshold trigger detection

After every stat value mutation (via `stat_change` or `stat_set` effect handlers), the engine SHALL check all thresholds registered for that stat name in `registry.stat_threshold_index`. For each entry: if the old value was `< threshold` and the new value is `>= threshold`, `player.enqueue_trigger(threshold.name)` SHALL be called. Downward crossings SHALL NOT fire the trigger.

#### Scenario: Upward crossing fires threshold trigger

- **WHEN** a stat changes from 99 to 101 and a threshold at 100 is registered for that stat
- **THEN** the threshold's trigger name is appended to `pending_triggers`

#### Scenario: Already above threshold does not re-fire

- **WHEN** a stat changes from 101 to 110 and a threshold at 100 is registered
- **THEN** no new trigger is appended (old value was already >= threshold)

#### Scenario: Downward crossing does not fire

- **WHEN** a stat changes from 110 to 50 and a threshold at 100 is registered
- **THEN** no trigger is appended for the downward crossing

#### Scenario: Stat with no registered thresholds is unaffected

- **WHEN** a stat that has no entries in `stat_threshold_index` is mutated
- **THEN** no trigger detection logic runs for that stat

---

### Requirement: emit_trigger effect

`EmitTriggerEffect` SHALL be added to the `Effect` union with `type: Literal["emit_trigger"]` and `trigger: str`. The `trigger` field SHALL name a custom trigger declared in `game.yaml` `triggers.custom`. The dispatch handler SHALL call `player.enqueue_trigger(effect.trigger)`. If the trigger has no registered adventures the enqueue is a no-op (the trigger just silently has nothing to drain).

Load-time validation SHALL verify that every `emit_trigger` effect in every adventure manifest references a name declared in `triggers.custom`. Unknown names SHALL produce a load warning.

#### Scenario: emit_trigger effect queues the custom trigger

- **WHEN** an adventure step's effects list contains `{type: emit_trigger, trigger: player_became_hero}`
- **THEN** `"player_became_hero"` is appended to `pending_triggers` when the step runs

#### Scenario: emit_trigger with no wired adventures is a no-op

- **WHEN** `emit_trigger` fires a trigger that has no entry in `trigger_adventures`
- **THEN** the queue still receives the trigger name but `drain_trigger_queue()` processes it as an empty list and moves on

#### Scenario: Undeclared custom trigger produces load warning

- **WHEN** an adventure uses `{type: emit_trigger, trigger: undeclared-name}` and `undeclared-name` is not in `triggers.custom`
- **THEN** a load warning is produced at content load time

---

### Requirement: drain_trigger_queue drains in FIFO order

`GameSession.drain_trigger_queue()` SHALL process `pending_triggers` entries one at a time from the front of the list (FIFO). For each trigger name, it SHALL look up the registered adventure refs in `registry.trigger_index`, then for each ref: evaluate `requires` conditions and repeat-control eligibility. Eligible adventures are run via `session.run_adventure()`. Ineligible adventures are skipped silently with a debug log.

The method SHALL continue until `pending_triggers` is empty. New triggers appended by effect handlers inside triggered adventures are processed in the same loop iteration (they land at the back of the list).

After fully draining the queue, `drain_trigger_queue()` SHALL call `_on_state_change(state, "adventure_end")` to persist the now-empty queue.

#### Scenario: Queue drains fully before returning

- **WHEN** `drain_trigger_queue()` is called with two entries in `pending_triggers`
- **THEN** both entries are processed and `pending_triggers == []` when the method returns

#### Scenario: Triggered adventure that queues new triggers is processed in same drain pass

- **WHEN** a triggered adventure's effects include `emit_trigger: follow-up` and `follow-up` is wired to an adventure
- **THEN** the follow-up adventure also runs in the same `drain_trigger_queue()` call (it was appended to the back of the list and the while-loop continues)

#### Scenario: Ineligible adventure is skipped without error

- **WHEN** a triggered adventure's `requires` condition is not met
- **THEN** the adventure is skipped, no error is raised, and the next trigger in the queue is processed

#### Scenario: Repeat-controlled adventure is skipped without error

- **WHEN** a triggered adventure has `repeatable: false` and has already been completed
- **THEN** the adventure is skipped and the drain continues to the next entry

---

### Requirement: Drain A and Drain B session lifecycle points

`drain_trigger_queue()` SHALL be called at exactly two points in the game session:

- **Drain A** — immediately after `session.start()` returns, before the world-navigation loop begins. Covers `on_character_create` and `on_game_rejoin`.
- **Drain B** — immediately after each call to `session.run_adventure()` returns, before the outcome message is shown to the player. Covers `on_level_up`, `on_outcome_*`, `on_stat_threshold`, and `emit_trigger`.

#### Scenario: on_character_create adventure runs before region menu

- **WHEN** a new character is created and `on_character_create` is wired to `welcome-adventure`
- **THEN** `welcome-adventure` runs before the player can see the region selection menu

#### Scenario: Triggered adventure runs before outcome message

- **WHEN** an adventure ends with `defeated` and `on_outcome_defeated` is wired
- **THEN** the triggered defeat-recovery adventure runs before the defeat message is shown to the player

---

### Requirement: Triggered adventures respect existing conditions and repeat controls

Triggered adventures use the same `requires`/`repeatable`/`max_completions`/`cooldown_days` eligibility checks as pool adventures. No special-casing is needed for triggered adventures in these systems.

#### Scenario: on_character_create adventure is one-shot by default

- **WHEN** `welcome-adventure` has `repeatable: false` and fires via `on_character_create`
- **THEN** the second character creation for the same user does NOT run `welcome-adventure` again (already completed)

#### Scenario: Triggered adventure with repeatable: true runs every time

- **WHEN** a triggered adventure has `repeatable: true` (or default) and its trigger fires on every level-up
- **THEN** it runs each time the trigger drains

---

### Requirement: Database migration adds character_iteration_pending_triggers table

A new Alembic migration SHALL create the `character_iteration_pending_triggers` table with:

- `iteration_id: UUID` — FK to `character_iterations.id`, part of composite PK
- `position: Integer` — 0-based ordinal preserving FIFO order, part of composite PK
- `trigger_name: String` — the trigger name

The migration SHALL be reversible (downgrade drops the table). No data migration is needed — characters with no rows have an empty queue, which is the correct starting state.

#### Scenario: Migration creates table

- **WHEN** the migration is applied
- **THEN** `character_iteration_pending_triggers` exists with the correct columns and composite PK

#### Scenario: Migration is reversible

- **WHEN** the migration downgrade is applied
- **THEN** the `character_iteration_pending_triggers` table is removed
