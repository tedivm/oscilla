# Character Management

## Purpose

Specifies the five character REST endpoints (`GET /characters`, `POST /characters`, `GET /characters/{id}`, `DELETE /characters/{id}`, `PATCH /characters/{id}`), the `CharacterSummaryRead` and `CharacterStateRead` response schemas, and the ownership enforcement rules that prevent cross-user data access.

---

## Requirements

### Requirement: GET /characters returns all characters for the authenticated user

`GET /characters` SHALL be an authenticated endpoint that returns `List[CharacterSummaryRead]` containing only the characters owned by the currently authenticated user.

The endpoint SHALL accept an optional `?game=<game_name>` query parameter. When provided, the response SHALL be filtered to only characters belonging to the specified game. When omitted, all characters for the user are returned regardless of game.

Each `CharacterSummaryRead` object SHALL contain:

- `id: UUID` — character identifier
- `name: str` — character display name
- `game_name: str` — game this character belongs to
- `prestige_count: int` — number of completed prestige cycles
- `created_at: datetime` — when the character was created
- `updated_at: datetime` — when the character was last modified

`updated_at` SHALL be populated from `CharacterRecord.updated_at`, which is updated automatically by SQLAlchemy `onupdate` on every write to the `characters` table.

#### Scenario: Returns all characters for the authenticated user

- **WHEN** an authenticated user has three characters across two games and calls `GET /characters`
- **THEN** the response is a JSON array of three `CharacterSummaryRead` objects

#### Scenario: CharacterSummaryRead carries updated_at

- **WHEN** a character has been modified since creation
- **THEN** `GET /characters` returns a `CharacterSummaryRead` where `updated_at` is set and is a valid ISO datetime

#### Scenario: Returns only characters for a specific game when filtered

- **WHEN** an authenticated user has characters in games `"alpha"` and `"beta"` and calls `GET /characters?game=alpha`
- **THEN** only characters belonging to game `"alpha"` are returned

#### Scenario: Returns empty list when user has no characters

- **WHEN** an authenticated user with no characters calls `GET /characters`
- **THEN** the response is `[]` with HTTP 200

#### Scenario: Requires authentication

- **WHEN** `GET /characters` is called without a valid Bearer token
- **THEN** the response has HTTP 401

---

### Requirement: POST /characters creates a new character for the authenticated user

`POST /characters` SHALL be an authenticated endpoint accepting `CharacterCreate` and returning `CharacterSummaryRead` with HTTP 201.

`CharacterCreate` SHALL contain exactly one field:

- `game_name: str` — the game the character belongs to

The endpoint SHALL validate `game_name` against the loaded registries. If the game is not in `app.state.registries` it SHALL return HTTP 422 with a descriptive error. The endpoint SHALL call `new_character()` to construct the initial `CharacterState`, then call `save_character()` to persist it. All character defaults (name, pronoun set, initial stats) are applied by `new_character()` from `character_config.yaml` and `game.yaml`.

No other character attributes — name, pronoun set, archetype, or class — SHALL be accepted at creation time. If a game requires the player to set any of these, the content author implements that as a triggered creation adventure.

#### Scenario: Successfully creates a character in a loaded game

- **WHEN** an authenticated user calls `POST /characters` with `{"game_name": "testland"}`
- **THEN** the response has HTTP 201
- **AND** the response body is a `CharacterSummaryRead` with `game_name = "testland"` and a non-null `id`

#### Scenario: Returns 422 for an unrecognized game name

- **WHEN** `POST /characters` is called with `{"game_name": "nonexistent"}`
- **THEN** the response has HTTP 422 with a descriptive error message

#### Scenario: Requires authentication

- **WHEN** `POST /characters` is called without a valid Bearer token
- **THEN** the response has HTTP 401

---

### Requirement: GET /characters/{id} returns full character state for an owned character

`GET /characters/{id}` SHALL be an authenticated endpoint that returns `CharacterStateRead` for the specified character. The endpoint SHALL return HTTP 404 if the `id` does not exist or does not belong to the authenticated user. Returning 404 (not 403) for unowned characters prevents character identifier enumeration.

`CharacterStateRead` SHALL be the complete character state contract. All fields listed below SHALL be present in every response, with null or empty-collection values for fields that have no data. The schema SHALL only be extended — never reduced — for the lifetime of the platform:

| Category   | Fields                                                                                                                        |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Identity   | `id`, `name`, `game_name`, `prestige_count`, `pronoun_set`, `created_at`                                                      |
| Location   | `current_location`, `current_location_name`, `current_region_name`                                                            |
| Stats      | `stats: Dict[str, StatValue]` — public stats only (as declared in `character_config.spec.public_stats`), value=None for unset |
| Inventory  | `stacks: Dict[str, StackedItemRead]`, `instances: List[ItemInstanceRead]`                                                     |
| Equipment  | `equipment: Dict[str, ItemInstanceRead]`                                                                                      |
| Skills     | `skills: List[SkillRead]`                                                                                                     |
| Buffs      | `active_buffs: List[BuffRead]`                                                                                                |
| Quests     | `active_quests: List[ActiveQuestRead]`, `completed_quests: List[str]`, `failed_quests: List[str]`                             |
| Milestones | `milestones: Dict[str, MilestoneRead]`                                                                                        |
| Archetypes | `archetypes: List[ArchetypeRead]`                                                                                             |
| Progress   | `internal_ticks: int`, `game_ticks: int`                                                                                      |
| Adventure  | `active_adventure: ActiveAdventureRead \| None`                                                                               |

`StatValue` SHALL carry:

- `ref: str` — the stat identifier
- `display_name: str | None`
- `value: int | bool | None` — None for unset stats

`stats` SHALL be populated for every stat declared in `character_config.spec.public_stats`, including stats with no current value (present with `value=None`). Stats in `character_config.spec.hidden_stats` SHALL NOT appear in the API response — they are used internally by the engine only. This ensures the frontend can render a complete stats panel without prior knowledge of the game's public stat list.

Location display names (`current_location_name`, `current_region_name`) SHALL be resolved from the `ContentRegistry` at response assembly time — the database stores only the `current_location` ref string.

#### Scenario: Returns full CharacterStateRead for owned character

- **WHEN** an authenticated user owns character `{id}` and calls `GET /characters/{id}`
- **THEN** the response has HTTP 200
- **AND** the response body matches the `CharacterStateRead` schema with all required fields present

#### Scenario: Stats dict includes all public stats even when value is None

- **GIVEN** a game with two public stats and one hidden stat, and a character that has only set one of the public stats
- **WHEN** `GET /characters/{id}` is called
- **THEN** `stats` contains both public stat entries (the unset one with `value: null`) but does NOT contain the hidden stat

#### Scenario: Hidden stats are not returned in the stats map

- **GIVEN** a character config that declares one public stat (`strength`) and one hidden stat (`internal_flag`)
- **WHEN** `GET /characters/{id}` is called
- **THEN** the `stats` map contains `strength` but does NOT contain `internal_flag`

#### Scenario: GET /characters/{id} response has no character_class field

- **WHEN** `GET /characters/{id}` is called for any character
- **THEN** the response body does not include a `character_class` key

#### Scenario: Returns 404 for a character belonging to another user

- **GIVEN** character `{id}` belongs to user B
- **WHEN** user A calls `GET /characters/{id}`
- **THEN** the response has HTTP 404

#### Scenario: Returns 404 for a non-existent character id

- **WHEN** `GET /characters/00000000-0000-0000-0000-000000000000` is called with a valid authenticated user
- **THEN** the response has HTTP 404

---

### Requirement: DELETE /characters/{id} deletes an owned character

`DELETE /characters/{id}` SHALL be an authenticated endpoint that deletes the character and all associated database rows. The endpoint SHALL return HTTP 204 on success. The endpoint SHALL return HTTP 404 if the character does not exist or does not belong to the authenticated user (preventing enumeration, same as GET).

#### Scenario: Successfully deletes owned character

- **WHEN** an authenticated user owns character `{id}` and calls `DELETE /characters/{id}`
- **THEN** the response has HTTP 204
- **AND** subsequent `GET /characters/{id}` returns HTTP 404

#### Scenario: Returns 404 when attempting to delete another user's character

- **GIVEN** character `{id}` belongs to user B
- **WHEN** user A calls `DELETE /characters/{id}`
- **THEN** the response has HTTP 404
- **AND** the character is NOT deleted

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

### Requirement: PATCH /characters/{id} renames an owned character

`PATCH /characters/{id}` SHALL be an authenticated endpoint accepting `CharacterUpdate` and returning `CharacterSummaryRead`. The endpoint SHALL return HTTP 404 if the character does not exist or does not belong to the authenticated user.

`CharacterUpdate` SHALL accept only the `name` field:

- `name: str | None` — new display name; if `None` (omitted), the name is unchanged

The endpoint SHALL validate that if `name` is provided it is non-empty (after stripping whitespace). An empty or whitespace-only name SHALL return HTTP 422.

#### Scenario: Successfully renames an owned character

- **WHEN** an authenticated user owns character `{id}` and calls `PATCH /characters/{id}` with `{"name": "New Name"}`
- **THEN** the response has HTTP 200
- **AND** `name` in the response is `"New Name"`
- **AND** subsequent `GET /characters` reflects the new name

#### Scenario: Returns 422 for empty name

- **WHEN** `PATCH /characters/{id}` is called with `{"name": "   "}`
- **THEN** the response has HTTP 422

#### Scenario: Returns 404 when attempting to rename another user's character

- **GIVEN** character `{id}` belongs to user B
- **WHEN** user A calls `PATCH /characters/{id}` with `{"name": "Stolen"}`
- **THEN** the response has HTTP 404
- **AND** the character name is NOT changed

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

---

### Requirement: All character endpoints enforce ownership via user id

All character endpoints — `GET /characters`, `POST /characters`, `GET /characters/{id}`, `DELETE /characters/{id}`, `PATCH /characters/{id}` — SHALL filter or validate against the authenticated user's `id`. No character operation SHALL expose or modify data belonging to a different user. Attempting to access another user's character SHALL return HTTP 404, not HTTP 403, to prevent character identifier enumeration.

#### Scenario: User cannot list other users' characters

- **GIVEN** user A and user B each own one character
- **WHEN** user A calls `GET /characters`
- **THEN** only user A's character is in the response; user B's character is absent

#### Scenario: Character creation is always for the authenticated user

- **WHEN** user A calls `POST /characters`
- **THEN** the created character's `user_id` equals user A's `id`

---

## Web Frontend Requirements (MU4)

### Requirement: Game selection page (`/app/games`)

The game selection page SHALL:

- Fetch `GET /games` on mount using the three-state async pattern (loading -> error | data).
- Render a `GameCard` component for each game returned. Each `GameCard` shows the game's `display_name`, `description` (if non-null), and a "Play" or "Select" button that navigates to `/app/characters?game={name}`.
- Render an empty-state prompt if the games list is empty.

#### Scenario: Games render as cards

- **GIVEN** `GET /games` returns two game objects
- **WHEN** the page mounts
- **THEN** two `GameCard` components are rendered, each showing the game's `display_name`.

#### Scenario: Empty state is shown

- **GIVEN** `GET /games` returns an empty list
- **WHEN** the page mounts
- **THEN** an informational empty-state message is rendered (e.g., "No games are currently available.").

---

### Requirement: Character list page (`/app/characters`)

The character list page SHALL:

- Accept an optional `?game=` query parameter to filter characters by game.
- Fetch `GET /characters?game={name}` (or `GET /characters` if no filter) on mount.
- Render a `CharacterCard` for each character, showing at minimum: `name`, `game_name`, `prestige_count`, and `created_at`.
- Provide a "New Character" button that navigates to `/app/characters/new?game={name}` (using any active game filter).
- Render an empty-state prompt with a "Create your first character" call-to-action when the list is empty.

#### Scenario: List renders character cards

- **GIVEN** `GET /characters` returns two characters
- **WHEN** the page mounts
- **THEN** two `CharacterCard` components are rendered.

#### Scenario: Game filter is applied

- **GIVEN** the URL includes `?game=testlandia`
- **WHEN** the page fetches characters
- **THEN** `GET /characters?game=testlandia` is called (not `GET /characters`).

#### Scenario: Empty state includes create link

- **GIVEN** `GET /characters` returns an empty list
- **WHEN** the page mounts
- **THEN** an empty-state prompt with a "Create your first character" link/button is rendered.

---

### Requirement: Character creation page (`/app/characters/new`)

Character creation SHALL be a single-step form — not a multi-step wizard. `POST /characters` accepts only `game_name`; all name, pronoun, and archetype customization is handled by the game's triggered creation adventure in MU5.

The creation page SHALL:

- Accept an optional `?game=` pre-selection parameter.
- If `?game=` is present: show a confirmation card with the game's `display_name` and a single "Create Character" button that POSTs to `POST /characters` with `{ game_name }`.
- If `?game=` is absent: show the same game selection grid (`GET /games`) so the user can pick first; selecting a game proceeds to the confirmation step.
- On success (`201 Created`): navigate to `/app/characters/{new_id}` (the character sheet).
- On error: display an `ErrorBanner` with the server's `detail` message.

#### Scenario: Pre-selected game shows confirmation

- **GIVEN** the URL is `/app/characters/new?game=testlandia`
- **WHEN** the page mounts
- **THEN** the game picker is not shown
- **AND** a confirmation UI showing the game name is rendered.

#### Scenario: Successful creation navigates to character sheet

- **GIVEN** the user confirms creation
- **AND** `POST /characters` returns `201` with a `CharacterSummaryRead`
- **THEN** the user is navigated to `/app/characters/{id}`.

---

### Requirement: Character sheet page (`/app/characters/[id]`)

The character sheet page SHALL:

- Fetch `GET /characters/{id}` on mount, then fetch `GET /games/{game_name}` using the resolved character game name (using the three-state async pattern).
- Pass the `CharacterStateRead` and `GameFeatureFlags` to the panel components.
- Render a `CharacterHeader` showing at minimum: `name`, `game_name`, `pronoun_set`, `prestige_count`, and current location (`current_location_name`, `current_region_name`).
- Render the panels listed in the table below according to `GameFeatureFlags`.
- Return to the character list via a "Back" link.
- The page is read-only in MU4. Adventure controls are not shown.

| Panel             | When shown                         | Data source                                                                        |
| ----------------- | ---------------------------------- | ---------------------------------------------------------------------------------- |
| `StatsPanel`      | Always                             | `CharacterStateRead.stats` (a `Record<string, StatValue>`)                         |
| `InventoryPanel`  | Always                             | `stacks` (stacked) and `instances` (item instances), displayed in tabs             |
| `EquipmentPanel`  | Always                             | `equipment` (slot -> `ItemInstanceRead`)                                           |
| `SkillsPanel`     | `features.has_skills === true`     | `skills` list; cooldown state is NOT in the current API — display name or ref only |
| `BuffsPanel`      | Always (shows empty state)         | `active_buffs` list                                                                |
| `QuestsPanel`     | `features.has_quests === true`     | `active_quests`, `completed_quests`, `failed_quests`                               |
| `MilestonesPanel` | Always (hides when empty)          | `milestones` record                                                                |
| `ArchetypesPanel` | `features.has_archetypes === true` | `archetypes` list                                                                  |

Panels whose feature flag is `false` SHALL not be rendered at all — not just empty. The `GameFeatureFlags` check is the sole source of panel visibility.

#### Scenario: Skills panel hidden when game has no skills

- **GIVEN** `features.has_skills === false`
- **WHEN** the character sheet renders
- **THEN** no `SkillsPanel` DOM node is present.

#### Scenario: Quests panel shown when game has quests

- **GIVEN** `features.has_quests === true`
- **WHEN** the character sheet renders
- **THEN** the `QuestsPanel` component is rendered.

#### Scenario: Another user's character returns 404

- **GIVEN** the character `{id}` belongs to a different user
- **WHEN** the page fetches `GET /characters/{id}`
- **THEN** a 404 `ApiError` is received
- **AND** the page renders a not-found error state.

#### Scenario: Inventory panel shows stacked and instance tabs

- **GIVEN** the character has both stacked items and item instances
- **WHEN** the inventory panel renders
- **THEN** two tabs ("Stacked" and "Instances") are visible and each tab displays its respective data.

---

### Requirement: Three-state async pattern on all data-fetching pages

Every page that fetches data SHALL follow the pattern specified in design D8:

- Show `LoadingSpinner` while `loading === true`.
- Show a local `ErrorBanner` (not the global `authStore.error` banner) when `error !== null`.
- Render page content only when `loading === false && error === null`.

HTTP 404 errors from `ApiError` SHALL navigate to a not-found state rather than showing a generic error. HTTP 403 errors SHALL display a prompt to verify email. HTTP 5xx errors SHALL show a generic "server error" message through `ErrorBanner`.
