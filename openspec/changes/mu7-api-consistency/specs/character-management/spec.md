## MODIFIED Requirements

### Requirement: CharacterSummaryRead includes updated_at

Each `CharacterSummaryRead` object SHALL contain:

- `id: UUID` — character identifier
- `name: str` — character display name
- `game_name: str` — game this character belongs to
- `prestige_count: int` — number of completed prestige cycles
- `created_at: datetime` — when the character was created
- `updated_at: datetime` — when the character was last modified

`updated_at` SHALL be populated from `CharacterRecord.updated_at`, which is updated automatically by SQLAlchemy `onupdate` on every write to the `characters` table.

#### Scenario: CharacterSummaryRead carries updated_at

- **WHEN** a character has been modified since creation
- **THEN** `GET /characters` returns a `CharacterSummaryRead` where `updated_at` is set and is a valid ISO datetime

---

### Requirement: CharacterStateRead omits character_class

`CharacterStateRead` SHALL NOT contain a `character_class` field. The field was never populated and is replaced by the archetype system.

#### Scenario: GET /characters/{id} response has no character_class field

- **WHEN** `GET /characters/{id}` is called for any character
- **THEN** the response body does not include a `character_class` key

---

### Requirement: CharacterStateRead stats map contains only public stats

The `stats` map in `CharacterStateRead` SHALL contain only stats declared in `character_config.spec.public_stats`. Stats declared in `character_config.spec.hidden_stats` SHALL NOT appear in the API response.

Hidden stats remain fully accessible inside the engine and are stored in the database; only the outbound API serialization filters them.

#### Scenario: Hidden stats are not returned in the stats map

- **GIVEN** a character config that declares one public stat (`strength`) and one hidden stat (`internal_flag`)
- **WHEN** `GET /characters/{id}` is called
- **THEN** the `stats` map contains `strength` but does NOT contain `internal_flag`

---

### Requirement: Character sub-models carry display metadata

All character state sub-models returned by `GET /characters/{id}` SHALL carry `display_name: str | None` and `description: str | None` populated from the content registry. `None` is returned when the registry entry is absent or the description is an empty string.

The affected models are:

**`StackedItemRead`** SHALL contain:

- `ref: str` — item manifest reference
- `quantity: int` — number of this item in the stack
- `display_name: str | None` — human-readable item name
- `description: str | None` — item description

**`ItemInstanceRead`** SHALL contain:

- `instance_id: UUID` — unique instance identifier
- `item_ref: str` — item manifest reference
- `charges_remaining: int | None`
- `modifiers: Dict[str, int]`
- `display_name: str | None` — human-readable item name
- `description: str | None` — item description

**`SkillRead`** SHALL contain:

- `ref: str` — skill manifest reference
- `display_name: str | None` — human-readable skill name
- `description: str | None` — skill description
- `on_cooldown: bool` — `True` if the skill is currently on cooldown
- `cooldown_remaining_ticks: int | None` — ticks remaining on the cooldown, or `None` if not on cooldown

**`BuffRead`** SHALL contain:

- `ref: str` — buff manifest reference
- `remaining_turns: int | None`
- `tick_expiry: int | None`
- `game_tick_expiry: int | None`
- `real_ts_expiry: int | None`
- `display_name: str | None` — human-readable buff name
- `description: str | None` — buff description

**`ActiveQuestRead`** SHALL contain:

- `ref: str` — quest manifest reference
- `current_stage: str` — current stage name within the quest
- `quest_display_name: str | None` — human-readable quest name
- `quest_description: str | None` — quest-level description
- `stage_description: str | None` — description of the current stage

**`ArchetypeRead`** SHALL contain:

- `ref: str` — archetype manifest reference
- `grant_tick: int`
- `grant_timestamp: int`
- `display_name: str | None` — human-readable archetype name
- `description: str | None` — archetype description

**`ActiveAdventureRead`** SHALL contain:

- `adventure_ref: str` — adventure manifest reference
- `step_index: int` — current step index within the adventure
- `display_name: str | None` — human-readable adventure name
- `description: str | None` — adventure description

#### Scenario: Item display metadata is populated when manifest exists

- **GIVEN** a character with a stacked item whose manifest has `displayName: "Health Potion"` and `description: "Restores HP"`
- **WHEN** `GET /characters/{id}` is called
- **THEN** the corresponding `StackedItemRead` has `display_name: "Health Potion"` and `description: "Restores HP"`

#### Scenario: Display metadata is null when manifest is absent

- **GIVEN** a character references an item ref not present in the current registry (content drift)
- **WHEN** `GET /characters/{id}` is called
- **THEN** the corresponding item read has `display_name: null` and `description: null`

#### Scenario: Empty description is normalized to null

- **GIVEN** an item manifest with `description: ""`
- **WHEN** `GET /characters/{id}` is called
- **THEN** the corresponding item read has `description: null`

#### Scenario: Skill on_cooldown is true when tick expiry is in the future

- **GIVEN** a character whose skill `"fireball"` has `skill_tick_expiry["fireball"] > internal_ticks`
- **WHEN** `GET /characters/{id}` is called
- **THEN** the `SkillRead` for `"fireball"` has `on_cooldown: true` and `cooldown_remaining_ticks` is a positive integer

#### Scenario: Skill on_cooldown is false when no cooldown is set

- **GIVEN** a character who knows skill `"fireball"` with no active cooldown
- **WHEN** `GET /characters/{id}` is called
- **THEN** the `SkillRead` for `"fireball"` has `on_cooldown: false` and `cooldown_remaining_ticks: null`

#### Scenario: Quest stage_description is populated from the current stage

- **GIVEN** a character with active quest `"main-quest"` at stage `"stage-2"` whose stage has `description: "Find the artifact"`
- **WHEN** `GET /characters/{id}` is called
- **THEN** the corresponding `ActiveQuestRead` has `stage_description: "Find the artifact"`

---

### Requirement: PATCH /characters/{id} is blocked when a session lock is live

`PATCH /characters/{id}` SHALL return HTTP 409 with a structured body when the character's active iteration has a non-null `session_token`.

The 409 response detail SHALL be a dict with:

- `code: "active_adventure"` — discriminator field
- `character_id: str` — the character UUID as a string

`DELETE /characters/{id}` SHALL NOT be blocked regardless of session lock state. A player may always delete a character they own.

#### Scenario: PATCH is blocked when session lock is live

- **GIVEN** a character whose active iteration has a non-null `session_token`
- **WHEN** `PATCH /characters/{id}` is called
- **THEN** the response has HTTP 409 and the body contains `{"detail": {"code": "active_adventure", "character_id": "<id>"}}`

#### Scenario: PATCH proceeds when no session lock is held

- **GIVEN** a character whose active iteration has `session_token: null`
- **WHEN** `PATCH /characters/{id}` is called with a valid rename body
- **THEN** the response has HTTP 200 and the character is renamed

#### Scenario: DELETE proceeds even when session lock is live

- **GIVEN** a character whose active iteration has a non-null `session_token`
- **WHEN** `DELETE /characters/{id}` is called
- **THEN** the response has HTTP 204 and the character is deleted
