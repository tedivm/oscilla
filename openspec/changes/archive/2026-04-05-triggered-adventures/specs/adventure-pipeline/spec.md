## MODIFIED Requirements

### Requirement: XP grant effect

An `xp_grant` effect SHALL add a specified amount of XP to the player. Negative amounts are valid (XP penalty). If the resulting total XP meets or exceeds the threshold for the next level, the player's level SHALL be incremented automatically and `max_hp` recalculated. Effects are silent state mutations — `add_xp()` returns the list of level numbers gained (empty if none) but no TUI output is produced at effect dispatch time. The updated level and HP are visible in `show_status()` after the adventure.

After `add_xp()` returns, for each level in `levels_gained`, the xp_grant effect handler SHALL call `player.enqueue_trigger("on_level_up")`. This ensures one queue entry per level gained so multi-level jumps fire the trigger the correct number of times.

#### Scenario: XP is added without levelling

- **WHEN** an xp_grant effect grants 50 XP and the player does not have enough total XP to level up
- **THEN** the player's XP increases by 50, level remains unchanged, and no `on_level_up` trigger is queued

#### Scenario: XP triggers level up

- **WHEN** an xp_grant effect grants enough XP to cross a level threshold
- **THEN** the player's level increments, `max_hp` is recalculated, `"on_level_up"` is appended to `pending_triggers`, and the new level is visible in the status display after the adventure completes

#### Scenario: Multi-level jump queues trigger per level

- **WHEN** an xp_grant effect causes the player to gain two levels in one step
- **THEN** `"on_level_up"` is appended to `pending_triggers` twice (once per level gained)

## ADDED Requirements

### Requirement: EmitTriggerEffect in the effect union

The effect union (used in adventure steps) SHALL include an `emit_trigger` effect type. It SHALL have a `trigger` field (string, required) naming a custom trigger declared in `game.yaml` `triggers.custom`. When dispatched by `run_effect()`, it SHALL call `player.enqueue_trigger(effect.trigger)`.

Load-time validation SHALL verify that every `emit_trigger` effect in every adventure manifest references a name that appears in `game.yaml` `triggers.custom`. An undeclared name SHALL produce a load warning (not a fatal error).

#### Scenario: emit_trigger effect in adventure step queues the trigger

- **WHEN** an adventure step's effects list includes `{type: emit_trigger, trigger: player_became_hero}` and `player_became_hero` is declared in `triggers.custom`
- **THEN** after the step runs, `"player_became_hero"` is in `player.pending_triggers`

#### Scenario: emit_trigger with no wired adventures is a no-op at drain time

- **WHEN** an `emit_trigger` effect fires a trigger that has no entry in `trigger_adventures`
- **THEN** the effect enqueues the name, drain processes it as an empty list, and the session continues without error

#### Scenario: Undeclared emit_trigger produces load warning

- **WHEN** an adventure uses `{type: emit_trigger, trigger: undeclared-name}` and `undeclared-name` is not in `triggers.custom`
- **THEN** a load warning is emitted for the undeclared trigger name at content load time
