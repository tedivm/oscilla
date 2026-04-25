## MODIFIED Requirements

### Requirement: Combat step (turn-based)

A `combat` step SHALL initiate a turn-based fight between the player and an enemy referenced by name from the registry. Combat behavior is fully governed by the resolved `CombatSystem` manifest (merged with any per-step `combat_overrides`). The `run_combat()` handler SHALL be an `async def` function that `await`s all `tui` calls.

The combat loop SHALL proceed as follows each round:

1. Tick active effects (`_tick_active_effects()`).
2. Resolve turn order via `resolve_turn_order()`.
3. First actor phase executes. In sequential modes, defeat conditions are evaluated after the first phase; if defeated, the second actor phase and `resolution_formulas` are skipped.
4. Second actor phase executes. In sequential modes, defeat conditions are evaluated after the second phase.
5. `resolution_formulas` phase — in `"simultaneous"` mode always fires; in sequential modes fires only if no mid-round defeat occurred.
6. `on_round_end` lifecycle effects fire if no defeat occurred.
7. Defeat conditions are re-evaluated after `on_round_end`.

Combat ends when a defeat condition is satisfied. On combat end, `on_combat_end` fires first; then `on_combat_victory` (player win) or `on_combat_defeat` (enemy win or flee). On player victory, `on_defeat_effects` from the enemy manifest run before loot and branch dispatch.

Enemy stats are persisted under `step_state["enemy_stats"]` and `combat_stats` under `step_state["combat_stats"]` each round for mid-session save/resume. On session resume, `on_combat_start` does not fire again. `combat_stats` are discarded at encounter end and never written to `player.stats`.

#### Scenario: Player wins manifest-driven combat

- **WHEN** a combat step runs and the `enemy_defeat_condition` evaluates to true after the player's phase
- **THEN** the combat step is marked complete, the enemy's `on_defeat_effects` run, loot is distributed, and the pipeline proceeds

#### Scenario: Enemy defeats player

- **WHEN** the `player_defeat_condition` evaluates to true after the enemy's phase
- **THEN** the adventure ends immediately and the player is returned to location selection

#### Scenario: Player flees

- **WHEN** a combat step runs and the player chooses to flee
- **THEN** the combat step terminates and the adventure ends (remaining steps are skipped)

#### Scenario: Turn order — player_first sequential short-circuit

- **WHEN** `turn_order: "player_first"` and the player reduces the enemy to zero HP in their phase
- **THEN** the enemy phase does not execute that round

#### Scenario: Combat stats initialized on new encounter

- **WHEN** a new combat begins and the system declares `combat_stats`
- **THEN** each stat is initialized to its declared default value

#### Scenario: Enemy stats and combat stats survive session resume

- **WHEN** a session is saved mid-combat and the player resumes
- **THEN** `enemy_stats` and `combat_stats` are restored from `step_state` and combat continues from where it left off

#### Scenario: Auto mode player phase fires formulas without menu

- **WHEN** `player_turn_mode: "auto"` and `player_damage_formulas` is non-empty
- **THEN** the player's damage formulas are applied automatically without presenting an action menu

#### Scenario: Choice mode player phase presents action menu

- **WHEN** `player_turn_mode: "choice"` and at least one system skill or player-owned combat skill is available
- **THEN** the player is presented with an action menu listing eligible skills, eligible items, and "Do Nothing"
