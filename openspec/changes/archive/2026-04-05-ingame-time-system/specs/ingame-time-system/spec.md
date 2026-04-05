# In-Game Time System

## Purpose

Defines the core in-game time system: the dual-clock architecture, the cycle directed acyclic graph (DAG), era configuration, epoch configuration, and the `game.yaml time:` manifest schema.

## Requirements

### Requirement: Game manifests may declare an optional in-game time configuration

A `game.yaml` manifest MAY include a `time:` block. When absent, the in-game time system SHALL be entirely disabled and all existing game behavior SHALL remain unchanged. No default time configuration is implied.

#### Scenario: Game without time block is unaffected

- **WHEN** a `game.yaml` does not include a `time:` block
- **THEN** `CharacterState.internal_ticks` and `game_ticks` are initialized to 0 but no cycle, era, or epoch logic runs
- **THEN** all `ingame_time` template variables evaluate to `None` or are absent
- **THEN** all existing adventure eligibility and cooldown semantics are unchanged

#### Scenario: Game with time block enables the time system

- **WHEN** a `game.yaml` includes a `time:` block with at least `ticks_per_adventure: 1`
- **THEN** the content registry builds an `InGameTimeResolver` for this game
- **THEN** both clocks advance on adventure completion

---

### Requirement: The in-game time system uses two separate tick counters

Every character iteration SHALL maintain two integer tick counters:

- `internal_ticks`: monotone counter that increments by the adventure's tick cost on every completion. It SHALL NOT be modifiable by any effect or author-defined action. It resets to 0 on a new iteration.
- `game_ticks`: narrative counter that also increments on adventure completion, but MAY be delta-adjusted by the `adjust_game_ticks` effect. It resets to 0 on a new iteration.

Both counters are stored on `CharacterIterationRecord` (database) and in `CharacterState` (in-memory).

#### Scenario: Both clocks advance on adventure completion

- **WHEN** a player completes an adventure with `ticks: 5`
- **THEN** `internal_ticks` increases by 5
- **THEN** `game_ticks` increases by 5

#### Scenario: internal_ticks cannot be adjusted by an effect

- **WHEN** an `adjust_game_ticks` effect with `delta: 10` is applied
- **THEN** `game_ticks` increases by 10
- **THEN** `internal_ticks` is unchanged

#### Scenario: Both clocks reset on new iteration

- **WHEN** a character prestiges and a new iteration begins
- **THEN** `internal_ticks` is reset to 0
- **THEN** `game_ticks` is reset to 0

---

### Requirement: The time system supports a configurable tick cost per adventure

`GameTimeSpec.ticks_per_adventure` (default: 1) sets the default tick cost for all adventures in the game. An individual adventure MAY override this by declaring `ticks: int` (positive integer). When override is absent, the game default applies.

#### Scenario: Default tick cost applies when no override

- **WHEN** `ticks_per_adventure: 3` and an adventure has no `ticks:` field
- **THEN** completing that adventure advances both clocks by 3

#### Scenario: Per-adventure override takes precedence

- **WHEN** `ticks_per_adventure: 3` and an adventure declares `ticks: 10`
- **THEN** completing that adventure advances both clocks by 10

#### Scenario: Default tick cost when no time system

- **WHEN** no `time:` block is configured
- **THEN** each completed adventure advances `internal_ticks` and `game_ticks` by 1

---

### Requirement: Cycle structure is declared as a directed acyclic graph

The `time.cycles` list declares named time units arranged as a DAG. There SHALL be exactly one root cycle (type `ticks`). All other cycles SHALL be derived cycles (type `cycle`) that reference a parent by name or alias.

A root cycle (`type: ticks`) SHALL specify:

- `name`: unique string identifier
- `count`: number of display slots per outer cycle (e.g., 24 for 24-hour days)
- `aliases` (optional): additional names that resolve to this cycle
- `labels` (optional): exactly `count` display strings; if absent, labels default to `"<name> N"` (1-based)

A derived cycle (`type: cycle`) SHALL specify:

- `name`: unique string identifier
- `parent`: name or alias of any previously accessible cycle
- `count`: how many parent units make one of this cycle
- `labels` (optional): exactly `count` display strings

Multiple derived cycles MAY share the same parent (creating parallel branches), enabling two unrelated recurring systems (e.g., weeks and months both branching from days).

#### Scenario: Root cycle defines the base time unit

- **WHEN** a root cycle `hour` with `count: 24` and `labels: [Dawn, ..., Midnight]` is declared
- **THEN** at `game_ticks = 0`, the hour label is `"Dawn"`
- **THEN** at `game_ticks = 23`, the hour label is `"Midnight"`
- **THEN** at `game_ticks = 24`, the hour label wraps back to `"Dawn"`

#### Scenario: Derived cycle advances based on parent count

- **WHEN** `day` is a derived cycle with `parent: hour` and `count: 24`
- **THEN** at `game_ticks = 0` through `23`, the day position is 0
- **THEN** at `game_ticks = 24`, the day position advances to 1

#### Scenario: Parallel branches from same parent are both valid

- **WHEN** both `week` (count: 7, parent: day) and `month` (count: 30, parent: day) are declared
- **THEN** both cycles are evaluated independently at each tick value
- **THEN** `week` and `month` have no interaction with each other

#### Scenario: Multiple levels of nesting are supported

- **WHEN** cycles form the chain `tick → hour(24) → day(30) → season(4)`
- **THEN** `Season 1` spans ticks 0 through 2879 (24 × 30 × 4 − 1 = 2879)

#### Scenario: Duplicate cycle names cause a load error

- **WHEN** two cycles both declare `name: day`
- **THEN** the semantic validator raises a `ContentLoadError`

#### Scenario: Cycle with no declared root raises load error

- **WHEN** no cycle with `type: ticks` is declared and the cycles list is non-empty
- **THEN** the semantic validator raises a `ContentLoadError`

#### Scenario: Cycle with two roots raises load error

- **WHEN** two cycles with `type: ticks` are declared
- **THEN** the semantic validator raises a `ContentLoadError`

#### Scenario: Cycle with bad parent reference raises load error

- **WHEN** a derived cycle declares `parent: nonexistent`
- **THEN** the semantic validator raises a `ContentLoadError`

---

### Requirement: Root cycles support aliases for narrative naming

A root cycle (`type: ticks`) MAY declare an `aliases: list[str]` field. Each alias SHALL resolve to the root cycle in all contexts: `parent` references, epoch positions, and condition `cycle` fields. Aliases SHALL be unique across all cycle names and aliases.

#### Scenario: Alias resolves as parent in derived cycle

- **WHEN** the root cycle `hour` has `aliases: [ship_hour]` and a derived cycle declares `parent: ship_hour`
- **THEN** the derived cycle is correctly computed against the root cycle's tick count

#### Scenario: Alias resolves in condition

- **WHEN** a `game_calendar_cycle_is` condition uses `cycle: ship_hour`
- **THEN** it evaluates against the root cycle's label at the current tick

#### Scenario: Duplicate alias and cycle name raises load error

- **WHEN** an alias `day` is declared on the root cycle, but a derived cycle also named `day` exists
- **THEN** the semantic validator raises a `ContentLoadError`

---

### Requirement: The `epoch` block sets the display position at tick 0

The `time.epoch` block is an optional mapping of cycle name (or alias) to either a label string or a 1-based integer index. When declared, it specifies the displayed calendar position at `game_ticks = 0`. The engine pre-computes an `epoch_offset` (integer number of ticks) that is added to `game_ticks` before computing cycle positions.

Omitted cycles default to position 1 (the first label or index). When `epoch` is absent entirely, the epoch offset is 0 and tick 0 displays as the first position of all cycles.

The `epoch` positions are validated at semantic validation time: each cycle name must resolve and each value must be either a valid label or an integer in `[1, cycle.count]`.

#### Scenario: Named epoch shifts display at tick 0

- **WHEN** `epoch: {season: Summer}` with a cycle `season` having labels `[Spring, Summer, Autumn, Winter]`
- **THEN** at `game_ticks = 0`, the season label is `"Summer"`

#### Scenario: Numeric epoch position is 1-based

- **WHEN** `epoch: {season: 2}` with `count: 4`
- **THEN** at `game_ticks = 0`, the season is at position index 1 (the second label)

#### Scenario: Epoch with nonexistent cycle raises load error

- **WHEN** `epoch: {nonexistent_cycle: Spring}`
- **THEN** the semantic validator raises a `ContentLoadError`

#### Scenario: Epoch with invalid label value raises load error

- **WHEN** `epoch: {season: BadLabel}` and `season` has labels `[Spring, Summer, Autumn, Winter]`
- **THEN** the semantic validator raises a `ContentLoadError`

---

### Requirement: Named eras track a cycle counter with latch-model activation

The `time.eras` list declares named era objects. Each era:

- `name`: unique string identifier used in conditions and templates
- `format`: Python str.format-style string with `{count}` as the only variable
- `epoch_count`: counter value at the moment of era activation (default: 1). For always-active eras this is the value at tick 0.
- `tracks`: name of the cycle whose completions increment the counter; MUST reference a cycle declared in `time.cycles`
- `start_condition` (optional): fires at most once per iteration. When first true, the era activates and `game_ticks` at that moment is recorded as `era_started_at_ticks[name]`. When absent, the era is always active from tick 0.
- `end_condition` (optional): fires at most once per iteration, after the era is active. When first true, the era deactivates and `game_ticks` at that moment is recorded as `era_ended_at_ticks[name]`. When absent, the era never ends.

Both conditions are evaluated by `update_era_states()` after each tick advancement. Neither condition is re-evaluated after it fires.

An era is **active** when its start has been recorded and its end has not been recorded. An era is **inactive** otherwise.

The `count` for an active era is: `epoch_count + floor((game_ticks - started_at_ticks) / ticks_per_tracked_cycle)`, where `started_at_ticks` is 0 for always-active eras.

#### Scenario: Era without start_condition is always active

- **WHEN** an era declares no `start_condition` field
- **THEN** `game_calendar_era_is: {era: <name>, state: active}` evaluates to true at any tick value
- **THEN** the era count at tick 0 equals `epoch_count`

#### Scenario: Era count starts at epoch_count on activation tick

- **WHEN** an era has `start_condition: {type: game_calendar_time_is, clock: game, gte: 365}` and `epoch_count: 1` and `game_ticks = 365` (the tick of activation)
- **THEN** the era count is `1 + floor((365 - 365) / ticks_per_year) = 1`
- **THEN** `game_calendar_era_is: {era: <name>, state: active}` evaluates to true

#### Scenario: Era count advances by tracked cycle completions since activation

- **WHEN** an era was activated at `game_ticks = 365`, tracks `year` (365 ticks/year), `epoch_count = 1`, and `game_ticks = 730`
- **THEN** the era count is `1 + floor((730 - 365) / 365) = 2`

#### Scenario: Era is inactive before start_condition fires

- **WHEN** an era has `start_condition: {type: game_calendar_time_is, clock: game, gte: 365}` and `game_ticks = 100`
- **THEN** `era_started_at_ticks` does not contain the era's name
- **THEN** `game_calendar_era_is: {era: <name>, state: active}` evaluates to false

#### Scenario: Era deactivates when end_condition fires

- **WHEN** an era has `end_condition: {type: milestone_achieved, milestone: king_dies}` and that milestone is achieved
- **THEN** `era_ended_at_ticks` records `game_ticks` at that moment
- **THEN** `game_calendar_era_is: {era: <name>, state: active}` evaluates to false from that tick onward

#### Scenario: Ended era cannot restart

- **WHEN** an era has ended (`era_ended_at_ticks` contains its name)
- **AND** the era's `start_condition` would evaluate true again (e.g., after a `adjust_game_ticks` rewind)
- **THEN** `update_era_states()` SHALL skip the era entirely
- **THEN** the era SHALL remain inactive for the rest of the iteration
- **THEN** `era_started_at_ticks` SHALL NOT be updated or removed

#### Scenario: Era tracks field references declared cycle

- **WHEN** an era declares `tracks: undeclared_cycle` and no cycle named `undeclared_cycle` exists in `time.cycles`
- **THEN** the semantic validator raises a `ContentLoadError`

---

### Requirement: pre_epoch_behavior controls game_ticks floor

`GameTimeSpec.pre_epoch_behavior` SHALL be either `"clamp"` (default) or `"allow"`.

- When `"clamp"`: any `adjust_game_ticks` effect that would push `game_ticks` below 0 is silently clamped at 0. `internal_ticks` is not affected.
- When `"allow"`: `game_ticks` may go negative. Cycle positions are computed with the epoch offset applied, so the calendar continues backward from the epoch position.

#### Scenario: Clamping prevents negative game_ticks

- **WHEN** `pre_epoch_behavior: clamp`, `game_ticks = 5`, and an `adjust_game_ticks: {delta: -100}` effect is applied
- **THEN** `game_ticks` is 0 after the effect
- **THEN** `internal_ticks` is unchanged

#### Scenario: Allow permits negative game_ticks

- **WHEN** `pre_epoch_behavior: allow`, `game_ticks = 5`, and an `adjust_game_ticks: {delta: -100}` effect is applied
- **THEN** `game_ticks` is -95 after the effect
