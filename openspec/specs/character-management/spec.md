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

#### Scenario: Returns all characters for the authenticated user

- **WHEN** an authenticated user has three characters across two games and calls `GET /characters`
- **THEN** the response is a JSON array of three `CharacterSummaryRead` objects

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

| Category   | Fields                                                                                            |
| ---------- | ------------------------------------------------------------------------------------------------- |
| Identity   | `id`, `name`, `game_name`, `character_class`, `prestige_count`, `pronoun_set`, `created_at`       |
| Location   | `current_location`, `current_location_name`, `current_region_name`                                |
| Stats      | `stats: Dict[str, StatValue]` — all declared stats, value=None for unset                          |
| Inventory  | `stacks: Dict[str, StackedItemRead]`, `instances: List[ItemInstanceRead]`                         |
| Equipment  | `equipment: Dict[str, ItemInstanceRead]`                                                          |
| Skills     | `skills: List[SkillRead]`                                                                         |
| Buffs      | `active_buffs: List[BuffRead]`                                                                    |
| Quests     | `active_quests: List[ActiveQuestRead]`, `completed_quests: List[str]`, `failed_quests: List[str]` |
| Milestones | `milestones: Dict[str, MilestoneRead]`                                                            |
| Archetypes | `archetypes: List[ArchetypeRead]`                                                                 |
| Progress   | `internal_ticks: int`, `game_ticks: int`                                                          |
| Adventure  | `active_adventure: ActiveAdventureRead \| None`                                                   |

`StatValue` SHALL carry:

- `ref: str` — the stat identifier
- `display_name: str | None`
- `value: int | bool | None` — None for unset stats

`stats` SHALL be populated for every stat declared in the game's `character_config.yaml`, including stats with no current value (present with `value=None`). This ensures the frontend can render a complete stats panel without prior knowledge of the game's stat list.

Location display names (`current_location_name`, `current_region_name`) SHALL be resolved from the `ContentRegistry` at response assembly time — the database stores only the `current_location` ref string.

#### Scenario: Returns full CharacterStateRead for owned character

- **WHEN** an authenticated user owns character `{id}` and calls `GET /characters/{id}`
- **THEN** the response has HTTP 200
- **AND** the response body matches the `CharacterStateRead` schema with all required fields present

#### Scenario: Stats dict includes all declared stats even when value is None

- **GIVEN** a game with three declared stats and a character that has only set one of them
- **WHEN** `GET /characters/{id}` is called
- **THEN** `stats` contains all three entries, the unset ones with `value: null`

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

### Requirement: All character endpoints enforce ownership via user id

All character endpoints — `GET /characters`, `POST /characters`, `GET /characters/{id}`, `DELETE /characters/{id}`, `PATCH /characters/{id}` — SHALL filter or validate against the authenticated user's `id`. No character operation SHALL expose or modify data belonging to a different user. Attempting to access another user's character SHALL return HTTP 404, not HTTP 403, to prevent character identifier enumeration.

#### Scenario: User cannot list other users' characters

- **GIVEN** user A and user B each own one character
- **WHEN** user A calls `GET /characters`
- **THEN** only user A's character is in the response; user B's character is absent

#### Scenario: Character creation is always for the authenticated user

- **WHEN** user A calls `POST /characters`
- **THEN** the created character's `user_id` equals user A's `id`
