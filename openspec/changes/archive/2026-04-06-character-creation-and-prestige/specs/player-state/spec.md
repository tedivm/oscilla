## MODIFIED Requirements

### Requirement: Player state fields

The player state model SHALL include the following fixed fields: `player_id` (UUID), `name` (string), `character_class` (string, nullable), `level` (int, default 1), `xp` (int, default 0), `hp` (int), `max_hp` (int), `prestige_count` (int, default 0), `current_location` (string reference, nullable), `milestones` (set of strings), `statistics` (PlayerStatistics dataclass with enemy/location/adventure counters), `stacks` (mapping of item ref to quantity for stackable items), `instances` (list of `ItemInstance` objects for non-stackable items, each with `instance_id: UUID`, `item_ref: str`, and `modifiers: Dict`), `equipment` (mapping of slot name to `instance_id: UUID`), `active_quests` (mapping of quest ref to stage name), `completed_quests` (set of quest refs), `active_adventure` (nullable adventure position struct), `pending_triggers` (FIFO list of trigger names awaiting drain, default empty list), and `prestige_pending` (nullable `PrestigeCarryForward` dataclass, default `None` — see prestige-system spec).

The `prestige_pending` field is ephemeral: it is never serialized to the database or restored from it. It exists solely to signal the `adventure_end` persist path that a prestige iteration transition must be executed before writing the reset state. After the transition, the field is cleared to `None`.

In addition to fixed fields, the player state SHALL contain a `stats` mapping (stat name → value) populated dynamically from the `CharacterConfig` manifest at character creation. Both `public_stats` and `hidden_stats` are stored in this single mapping; the distinction is only presentational. Stat values SHALL be typed `int | bool | None` — the `float` type is no longer permitted. Stat values SHALL default to the declared default, or `null` if no default is set. Integer stats SHALL only be mutated through `CharacterState.set_stat()`, which enforces hard INT32 floor/ceiling bounds.

#### Scenario: New player starts with default values

- **WHEN** a new player state is created with only a name
- **THEN** level is 1, XP is 0, prestige_count is 0, milestones is empty, statistics has all counters at zero, stacks is empty, instances is empty, equipment is empty, active_adventure is None, pending_triggers is an empty list, prestige_pending is None, and the stats map contains every stat from CharacterConfig initialised to its declared default

#### Scenario: Public stats are visible, hidden stats are not

- **WHEN** the player status panel is rendered
- **THEN** only stats declared under `public_stats` in CharacterConfig are displayed; stats in `hidden_stats` are omitted from the UI

#### Scenario: Stats map contains only int and bool values

- **WHEN** a character is created from a `CharacterConfig` that declares only `int` and `bool` stats
- **THEN** every value in `player.stats` is an `int`, `bool`, or `None`; no `float` values are present

#### Scenario: prestige_pending is ephemeral — not in to_dict output

- **WHEN** `player.to_dict()` is called while `prestige_pending` is not None
- **THEN** the returned dict does not contain a `prestige_pending` key

#### Scenario: prestige_pending survives in-memory until adventure_end

- **WHEN** the prestige effect fires mid-adventure and sets `prestige_pending`
- **THEN** subsequent steps in the same adventure observe `prestige_pending is not None` on the in-memory state
- **AND THEN** `prestige_pending` is `None` after `_persist_diff(event="adventure_end")` completes

## ADDED Requirements

### Requirement: prestige_count serialized as prestige_count key

The `CharacterState.to_dict()` method SHALL serialize the prestige run counter under the key `"prestige_count"`. The `CharacterState.from_dict()` method SHALL read from `"prestige_count"`, falling back to the legacy `"iteration"` key for backward compatibility with any serialized states created before this change.

#### Scenario: to_dict uses prestige_count key

- **WHEN** `player.to_dict()` is called on any character state
- **THEN** the returned dict contains the key `"prestige_count"` with the integer value and does not contain the key `"iteration"`

#### Scenario: from_dict reads prestige_count key

- **WHEN** `CharacterState.from_dict({"prestige_count": 3, ...})` is called
- **THEN** the resulting state has `prestige_count == 3`

#### Scenario: from_dict accepts legacy iteration key

- **WHEN** `CharacterState.from_dict({"iteration": 2, ...})` is called (no prestige_count key)
- **THEN** the resulting state has `prestige_count == 2` (legacy key accepted for backward compat)
