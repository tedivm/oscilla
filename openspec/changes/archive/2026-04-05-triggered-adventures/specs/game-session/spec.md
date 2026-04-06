## MODIFIED Requirements

### Requirement: New character creation saves immediately

When a new character is created, `GameSession._create_new_character()` SHALL:

1. Apply the `--character-name` CLI argument as the character name if provided
2. Otherwise prompt the user for a name via `TUICallbacks`
3. Initialize a `CharacterState` via `CharacterState.new_character()`
4. Call `state.enqueue_trigger("on_character_create")` if `"on_character_create"` is in `registry.trigger_index`
5. Save the record to DB immediately (with `character_class = None`, `current_location = None`)
6. Proceed to class and location selection before adventure is available

The trigger must be enqueued before the first persist so it survives into the Drain A call in the game loop.

#### Scenario: New character with CLI name

- **WHEN** `--character-name "Aragorn"` is passed and no character named "Aragorn" exists
- **THEN** a new character named "Aragorn" is created without prompting for a name

#### Scenario: New character with prompted name

- **WHEN** no `--character-name` flag is given
- **THEN** the user is prompted to enter a name before character creation proceeds

#### Scenario: on_character_create queued before first persist

- **WHEN** a new character is created and `on_character_create` is wired in `trigger_adventures`
- **THEN** `pending_triggers` contains `"on_character_create"` in the database row immediately after creation

## ADDED Requirements

### Requirement: GameSession.drain_trigger_queue() drains queued triggers

`GameSession` SHALL expose an `async def drain_trigger_queue(self) -> None` method. It SHALL process the character's `pending_triggers` FIFO list, running each registered adventure via `session.run_adventure()` with full condition and repeat-control checks. The drain continues until `pending_triggers` is empty — new trigger entries appended by in-progress triggered adventures are processed in the same call.

After draining, `drain_trigger_queue()` SHALL persist the (now-empty) queue via `_on_state_change(state, "adventure_end")`.

`drain_trigger_queue()` SHALL be called at two defined points in each session:

- **Drain A**: immediately after `start()` returns (handles `on_character_create` and `on_game_rejoin`)
- **Drain B**: immediately after each call to `run_adventure()` returns (handles all other trigger types)

#### Scenario: Drain A runs before world navigation loop

- **WHEN** the game loop calls `drain_trigger_queue()` after `start()` and the queue contains `"on_character_create"`
- **THEN** the registered `on_character_create` adventure completes before the player can select a region

#### Scenario: Drain B runs after each adventure

- **WHEN** an adventure ends and `on_outcome_defeated` is queued
- **THEN** `drain_trigger_queue()` runs before the outcome message is shown and the defeat-recovery adventure completes

#### Scenario: Empty queue is a no-op

- **WHEN** `drain_trigger_queue()` is called with `pending_triggers == []`
- **THEN** the method returns immediately without calling `run_adventure()`

#### Scenario: drain_trigger_queue is safe with no character loaded

- **WHEN** `drain_trigger_queue()` is called before `start()` has loaded a character (`_character is None`)
- **THEN** the method returns immediately without error

### Requirement: on_game_rejoin detection at session load

At session start on the load path (loading an existing character), `GameSession.start()` SHALL check whether the player has been absent for longer than the configured `absence_hours` threshold. If `triggers.on_game_rejoin` is configured, `"on_game_rejoin"` is in `registry.trigger_index`, and the time since `characters.updated_at` exceeds `absence_hours`, then `state.enqueue_trigger("on_game_rejoin")` SHALL be called before returning from `start()`.

The `characters.updated_at` column is the authoritative last-activity timestamp, updated at every `adventure_end` event.

#### Scenario: Long absence triggers on_game_rejoin

- **WHEN** a character was last active more than `absence_hours` hours ago
- **THEN** `"on_game_rejoin"` is appended to `pending_triggers` inside `start()`

#### Scenario: Recent session does not trigger on_game_rejoin

- **WHEN** a character was last active within the `absence_hours` window
- **THEN** `pending_triggers` does not contain `"on_game_rejoin"` after `start()` returns

#### Scenario: Missing on_game_rejoin config skips detection

- **WHEN** `triggers.on_game_rejoin` is `None`
- **THEN** no rejoin detection occurs regardless of absence duration
