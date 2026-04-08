## MODIFIED Requirements

### Requirement: Player state fields

The player state model SHALL include the following fixed fields: `player_id` (UUID), `name` (string), `character_class` (string, nullable), `level` (int, default 1), `xp` (int, default 0), `hp` (int), `max_hp` (int), `prestige_count` (int, default 0), `current_location` (string reference, nullable), `milestones` (dict mapping milestone name to the `internal_ticks` value at grant time — see milestone-timestamps spec), `statistics` (PlayerStatistics dataclass with enemy/location/adventure counters), `stacks` (mapping of item ref to quantity for stackable items), `instances` (list of `ItemInstance` objects for non-stackable items, each with `instance_id: UUID`, `item_ref: str`, and `modifiers: Dict`), `equipment` (mapping of slot name to `instance_id: UUID`), `active_quests` (mapping of quest ref to stage name), `completed_quests` (set of quest refs), `active_adventure` (nullable adventure position struct), `pending_triggers` (FIFO list of trigger names awaiting drain, default empty list), and `prestige_pending` (nullable `PrestigeCarryForward` dataclass, default `None` — see prestige-system spec).

The `prestige_pending` field is ephemeral: it is never serialized to the database or restored from it.

In addition to fixed fields, the player state SHALL contain a `stats` mapping populated dynamically from `CharacterConfig`. Stat values SHALL be typed `int | bool | None`. Integer stats SHALL only be mutated through `CharacterState.set_stat()`.

Adventure completion timestamps SHALL be stored in three separate dicts:

- `adventure_last_completed_at_ticks: Dict[str, int]` — `internal_ticks` value when each adventure was last completed.
- `adventure_last_completed_game_ticks: Dict[str, int]` — `game_ticks` value when each adventure was last completed.
- `adventure_last_completed_real_ts: Dict[str, int]` — Unix timestamp (integer seconds) when each adventure was last completed.

The deprecated `adventure_last_completed_on: Dict[str, str]` (ISO date string) field SHALL be removed. The `__game__` prefix encoding in `adventure_last_completed_at_ticks` SHALL be removed; game-tick completions use the dedicated `adventure_last_completed_game_ticks` dict.

Skill cooldown state SHALL be stored as absolute expiry timestamps:

- `skill_tick_expiry: Dict[str, int]` — `internal_ticks` value at which the adventure-scope cooldown for this skill expires.
- `skill_real_expiry: Dict[str, int]` — Unix timestamp (integer seconds) at which the adventure-scope cooldown expires.

The deprecated `skill_cooldowns: Dict[str, int]` (adventure-count countdown) field SHALL be removed.

#### Scenario: New player starts with default values

- **WHEN** a new player state is created
- **THEN** level is 1, XP is 0, prestige_count is 0, milestones is an empty dict, statistics has all counters at zero, all adventure timestamp dicts are empty, all skill expiry dicts are empty, and stats contains every stat from CharacterConfig initialized to its declared default

#### Scenario: adventure_last_completed_real_ts stores Unix timestamp

- **WHEN** an adventure completes and the current time is Unix timestamp 1700000000
- **THEN** `adventure_last_completed_real_ts[adventure_ref] == 1700000000`

#### Scenario: game-tick completions stored in dedicated dict

- **WHEN** an adventure completes at `game_ticks == 42`
- **THEN** `adventure_last_completed_game_ticks[adventure_ref] == 42`
- **THEN** `adventure_last_completed_at_ticks[adventure_ref]` contains only internal_ticks (no `__game__` prefix entries)

#### Scenario: skill_tick_expiry set on skill use

- **WHEN** a skill with `cooldown: {ticks: 5}` is used at `internal_ticks == 10`
- **THEN** `skill_tick_expiry[skill_ref] == 15`

#### Scenario: skill_real_expiry cleared on prestige

- **WHEN** a prestige effect fires
- **THEN** both `skill_tick_expiry` and `skill_real_expiry` are cleared to empty dicts

#### Scenario: prestige_pending is ephemeral

- **WHEN** `player.to_dict()` is called while `prestige_pending` is not None
- **THEN** the returned dict does not contain a `prestige_pending` key

---

## REMOVED Requirements

### Requirement: adventure_last_completed_on stores ISO date string

**Reason:** Day-precision ISO date strings prevent sub-day cooldowns. Replaced by `adventure_last_completed_real_ts` which stores Unix timestamp integers, supporting second-precision real-world cooldowns.

**Migration:** Content using `cooldown_days: N` must be updated to `cooldown: {seconds: "{{ SECONDS_PER_DAY * N }}"}`.

### Requirement: skill_cooldowns stores adventure-count countdown

**Reason:** The countdown model required `tick_skill_cooldowns()` to be called at adventure start to decrement values, but this method was never called — rendering adventure-scoped skill cooldowns non-functional. Replaced by absolute expiry timestamps (`skill_tick_expiry`, `skill_real_expiry`) that require no ceremony to maintain.

**Migration:** `SkillCooldown(scope="adventure", count=N)` → `Cooldown(ticks=N)` in skill manifests.

### Requirement: **game** prefix encoding in adventure_last_completed_at_ticks

**Reason:** Encoding two conceptually distinct values (internal_tick and game_tick) in the same dict via a naming convention is fragile and confusing. Replaced by two dedicated dicts.

**Migration:** Handled transparently at `from_dict` deserialization time — `__game__` prefixed entries are migrated to `adventure_last_completed_game_ticks` automatically.
