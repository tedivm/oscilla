## REMOVED Requirements

### Requirement: on_level_up trigger detection

**Reason:** `on_level_up` was a built-in trigger key coupled to the now-removed `add_xp()` / `xp_grant` machinery. It represented a hardcoded engine concept: the idea that "leveling up" is a first-class event. With `level` as an author-declared derived stat and `on_stat_threshold` as the generic threshold mechanism, there is no justification for a special-cased level-up trigger.

**Migration:** Declare `on_stat_threshold` entries on your `level` stat (or your `xp` stat if `level` is derived from `xp`). Use threshold names of your choice and wire them in `trigger_adventures`. The behavior is identical: a trigger adventure fires when the stat crosses the threshold upward.

---

## MODIFIED Requirements

### Requirement: game.yaml trigger configuration schema

`GameSpec` SHALL include two optional blocks: `triggers` (a `GameTriggers` model) and `trigger_adventures` (a `Dict[str, List[str]]`). Both SHALL default to empty values if absent.

`GameTriggers` SHALL contain:

- `custom: List[str]` — declared custom trigger names, default empty
- `on_game_rejoin: GameRejoinTrigger | None` — optional, with `absence_hours: int` (min 1)
- `on_stat_threshold: List[StatThresholdTrigger]` — each entry with `stat: str`, `threshold: int`, `name: str`, and an optional `fire_mode: Literal["each", "highest"]` (default `"each"`)
- `max_trigger_queue_depth: int` — maximum pending trigger queue depth, default `6`, minimum `1`

`trigger_adventures` maps a trigger name (string) to an ordered list of adventure refs (strings). Adventures fire top-to-bottom per trigger in declaration order.

`GameSpec` SHALL NOT include `xp_thresholds` or `hp_formula`.

#### Scenario: game.yaml with no triggers block loads cleanly

- **WHEN** a `game.yaml` that has no `triggers` or `trigger_adventures` fields is loaded
- **THEN** the `GameSpec` loads without error, `spec.triggers` is an empty `GameTriggers`, and `spec.trigger_adventures` is `{}`

#### Scenario: trigger_adventures wires an adventure to on_character_create

- **WHEN** `game.yaml` contains `trigger_adventures: {on_character_create: [welcome-adventure]}`
- **THEN** `registry.trigger_index["on_character_create"]` equals `["welcome-adventure"]` after content load

#### Scenario: Multiple adventures per trigger maintain declaration order

- **WHEN** `trigger_adventures: {level-up: [adv-a, adv-b, adv-c]}` is declared
- **THEN** adventures are run in the order `adv-a → adv-b → adv-c` when the trigger fires

#### Scenario: game.yaml with xp_thresholds fails validation

- **WHEN** a `game.yaml` contains a top-level `xp_thresholds` key
- **THEN** the `GameSpec` raises a Pydantic validation error (extra fields forbidden)

---

### Requirement: Load-time validation of trigger_adventures keys

The content loader SHALL validate every key in `trigger_adventures` against the set of known trigger names for the loaded game. Unknown keys SHALL produce a load warning (not a fatal error).

Known trigger names are:

- `on_character_create` (always valid)
- `on_outcome_<name>` for each name in the built-in outcome set (`completed`, `defeated`, `fled`) plus each name in `spec.outcomes`
- `on_game_rejoin` (valid only when `triggers.on_game_rejoin` is configured)
- `<threshold.name>` for each entry in `triggers.on_stat_threshold`
- Each name in `triggers.custom`

`on_level_up` is NOT a known trigger name and SHALL produce a load warning if used as a `trigger_adventures` key.

Each adventure ref in every list SHALL also be validated against the registered adventure manifests. A ref that doesn't resolve SHALL produce a load warning.

Duplicate `name` values among `triggers.on_stat_threshold` entries SHALL produce a load warning.

#### Scenario: Unknown trigger key produces load warning

- **WHEN** `trigger_adventures` contains `{on_unknown_event: [some-adv]}`
- **THEN** a load warning is emitted for the unknown key

#### Scenario: on_level_up key produces load warning

- **WHEN** `trigger_adventures` contains `{on_level_up: [level-up-adv]}`
- **THEN** a load warning is emitted for `on_level_up` (it is no longer a valid built-in key)

#### Scenario: on*outcome*<custom> is valid when outcome is declared

- **WHEN** `game.yaml` has `outcomes: [discovered]` and `trigger_adventures: {on_outcome_discovered: [disc-adv]}`
- **THEN** no load warning is produced for `on_outcome_discovered`

#### Scenario: Unknown adventure ref produces load warning

- **WHEN** a trigger_adventures entry references `[no-such-adv]` and no adventure with that name is registered
- **THEN** a load warning is produced identifying the missing adventure ref

#### Scenario: Duplicate threshold name produces load warning

- **WHEN** two `on_stat_threshold` entries have the same `name` field
- **THEN** a load warning is produced identifying the duplicate name

---

### Requirement: on_stat_threshold trigger detection

After every stored stat value mutation (via `stat_change` or `stat_set` effect handlers), the engine SHALL check all thresholds registered for that stored stat name. Additionally, after `_recompute_derived_stats()` runs, the engine SHALL check all thresholds registered for any derived stat whose shadow value changed.

For each entry: if the old value was `< threshold` and the new value is `>= threshold`, the entry has been crossed. Downward crossings SHALL NOT fire the trigger.

**`fire_mode` controls how crossed entries enqueue:**

- `fire_mode: each` (default) — every crossed entry fires as a separate `enqueue_trigger()` call, in ascending threshold order. A stat jumping from 0 to 700 with thresholds at 100, 300, and 600 enqueues all three.
- `fire_mode: highest` — only the single highest crossed threshold fires. The same jump enqueues only the `600` entry; the `100` and `300` entries are suppressed.

`each` and `highest` entries on the same stat operate in independent groups: all `each` entries fire first (ascending), then the single highest `highest` entry fires (if any `highest` entries were crossed).

`on_stat_threshold` entries may reference either stored or derived stat names. The loader SHALL validate that the `stat` field in each `on_stat_threshold` entry matches a stat name declared in `CharacterConfig` (stored or derived); an unknown stat name SHALL produce a load warning.

#### Scenario: Upward crossing fires threshold trigger

- **WHEN** a stat changes from 99 to 101 and a threshold at 100 is registered for that stat
- **THEN** the threshold's trigger name is appended to `pending_triggers`

#### Scenario: Already above threshold does not re-fire

- **WHEN** a stat changes from 101 to 110 and a threshold at 100 is registered
- **THEN** no new trigger is appended (old value was already >= threshold)

#### Scenario: Downward crossing does not fire

- **WHEN** a stat changes from 110 to 50 and a threshold at 100 is registered
- **THEN** no trigger is appended for the downward crossing

#### Scenario: Multi-cross with `fire_mode: each` enqueues one entry per threshold in ascending order

- **WHEN** a stat changes from 0 to 700 and three thresholds at 100, 300, and 600 are all declared with `fire_mode: each`
- **THEN** three separate trigger entries are appended to `pending_triggers` in threshold-ascending order (`100-name`, `300-name`, `600-name`)

#### Scenario: Multi-cross with `fire_mode: highest` enqueues only the highest crossed threshold

- **WHEN** a stat changes from 0 to 700 and three thresholds at 100, 300, and 600 are all declared with `fire_mode: highest`
- **THEN** only the `600` threshold's trigger name is appended to `pending_triggers`; the 100 and 300 entries are suppressed

#### Scenario: Mixed `fire_mode` entries on the same stat operate independently

- **WHEN** a stat changes from 0 to 700, threshold 100 has `fire_mode: each`, and thresholds 300 and 600 both have `fire_mode: highest`
- **THEN** `pending_triggers` receives: the `100-name` entry (each), then the `600-name` entry (highest); the `300-name` entry is suppressed

#### Scenario: `fire_mode` defaults to `each` when omitted

- **WHEN** an `on_stat_threshold` entry is declared without a `fire_mode` field
- **THEN** it behaves identically to `fire_mode: each`

#### Scenario: Threshold on derived stat fires when derived shadow changes

- **WHEN** a stored stat mutation causes a derived stat's shadow to cross a registered threshold
- **THEN** the threshold's trigger name is appended to `pending_triggers`

#### Scenario: Stat with no registered thresholds is unaffected

- **WHEN** a stat that has no entries in `stat_threshold_index` is mutated
- **THEN** no threshold trigger logic runs for that stat

#### Scenario: on_stat_threshold entry with unknown stat name produces load warning

- **WHEN** `on_stat_threshold` has `stat: nonexistent_stat` and no such stat exists in `CharacterConfig`
- **THEN** a load warning is produced at content load time
