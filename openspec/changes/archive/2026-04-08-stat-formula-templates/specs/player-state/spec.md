## REMOVED Requirements

### Requirement: level, xp, hp, max_hp as first-class CharacterState fields

**Reason:** These fields hardcode game-specific progression concepts as engine primitives. Games without HP, XP-based leveling, or levels as a concept are forced to inherit fields they do not use. Hard removal is justified because the project is pre-alpha with no published content packages. All four values are expressed as ordinary `CharacterConfig` stats going forward — identical to `strength`, `gold`, or any other author-declared stat.

**Migration:** Declare `level`, `xp`, `hp`, and `max_hp` as stats in `character_config.yaml` using `type: int`. Initialize `hp` and `max_hp` via an `on_character_create` trigger adventure. Wire `level` as a `derived` stat formula that reads `xp` thresholds. Use `stat_change` in place of the removed `xp_grant` effect. See `docs/authors/game-configuration.md` for migration examples.

---

### Requirement: add_xp() method on CharacterState

**Reason:** `add_xp()` was the only path for XP progression; it hardcoded level detection by reading `game.spec.xp_thresholds`, mutating both `self.xp` and `self.level`, and returning level-up counts so the effect handler could enqueue `on_level_up`. All of this is superseded by `stat_change` on the `xp` stat + derived stat change detection + `on_stat_threshold` triggers.

**Migration:** Use `stat_change { stat: xp, amount: <value> }`. Level advancement is driven automatically by `on_stat_threshold` entries for the `xp` stat or by declaring `level` as a derived stat.

---

### Requirement: prestige_count serialized as prestige_count key

**Reason:** No change to this requirement — listed here to avoid confusion. `prestige_count` is preserved; the removed fields are `level`, `xp`, `hp`, and `max_hp` only.

---

## MODIFIED Requirements

### Requirement: CharacterState serializes and deserializes player state

`CharacterState.to_dict()` SHALL serialize all stored stat values under the `stats` key as a flat dict. The fields `level`, `xp`, `hp`, and `max_hp` SHALL NOT appear as top-level keys in the serialized dict. `CharacterState.from_dict()` SHALL not expect or read these fields as top-level keys.

The `_derived_shadows` field SHALL NOT be serialized. Derived shadows are ephemeral and are always recomputed from `CharacterState.stats` on first run of `_recompute_derived_stats()` after load.

Games that declare `level`, `xp`, `hp`, or `max_hp` as stat names in `CharacterConfig` will find those values in `to_dict()["stats"]` exactly as any other stat value.

#### Scenario: to_dict does not contain top-level level/xp/hp/max_hp keys

- **WHEN** `player.to_dict()` is called on any character state
- **THEN** the returned dict does not contain top-level keys named `"level"`, `"xp"`, `"hp"`, or `"max_hp"`

#### Scenario: Stats declared as level/xp/hp/max_hp appear under stats key

- **WHEN** a game declares `level` as a stat and the character has `stats["level"] = 3`
- **THEN** `player.to_dict()["stats"]["level"]` equals `3`

#### Scenario: \_derived_shadows is not serialized

- **WHEN** `player.to_dict()` is called on a character with non-empty `_derived_shadows`
- **THEN** the returned dict does not contain a `"_derived_shadows"` key

#### Scenario: from_dict does not require level/xp/hp/max_hp keys

- **WHEN** `CharacterState.from_dict(data)` is called and `data` has no top-level `"level"` key
- **THEN** the resulting character state deserializes without error

---

### Requirement: new_character() initializes CharacterState without hardcoded progression fields

`new_character()` SHALL initialize `CharacterState` with only:

- Author-declared stat names and their default values (from `CharacterConfig`), for stats that are NOT derived
- Derived stats SHALL be absent from the initial `stats` dict

`new_character()` SHALL NOT read `hp_formula`, `xp_thresholds`, or any game-level HP/XP configuration. Initial HP and other setup values are the responsibility of the `on_character_create` trigger adventure.

#### Scenario: new_character stats contains only non-derived stat defaults

- **WHEN** `CharacterState.new_character()` is called with a `CharacterConfig` containing one derived stat and two stored stats
- **THEN** `player.stats` contains the two stored stats at their default values and does NOT contain the derived stat

#### Scenario: new_character does not read hp_formula

- **WHEN** `CharacterState.new_character()` is called
- **THEN** it does not raise an error even if the `GameSpec` has no `hp_formula` field

---

### Requirement: Database migration removes hardcoded progression columns

A new Alembic migration SHALL remove the `level`, `xp`, `hp`, and `max_hp` columns from `character_iterations`. The downgrade SHALL re-add these columns as nullable integers so data is not lost on rollback.

#### Scenario: Migration removes progression columns

- **WHEN** the migration is applied
- **THEN** `character_iterations` has no columns named `level`, `xp`, `hp`, or `max_hp`

#### Scenario: Migration downgrade restores columns as nullable

- **WHEN** the migration downgrade is applied
- **THEN** `character_iterations` has nullable integer columns named `level`, `xp`, `hp`, and `max_hp`

---

### Requirement: CharacterState.\_derived_shadows initialized empty on new characters

`CharacterState` SHALL include a `_derived_shadows: Dict[str, int | None]` field initialized to an empty dict. This is a non-serialized ephemeral field used by `_recompute_derived_stats()`.

#### Scenario: new_character produces empty_derived_shadows

- **WHEN** `CharacterState.new_character()` is called
- **THEN** `player._derived_shadows == {}`

#### Scenario: \_derived_shadows populated after first recompute

- **WHEN** `_recompute_derived_stats()` is called for the first time after `new_character()`
- **THEN** all derived stat names appear as keys in `player._derived_shadows`

#### Scenario: No skill rows in DB returns empty known_skills

- **WHEN** a character has no rows in `character_iteration_skills`
- **THEN** `player.known_skills == set()` after load

---

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
