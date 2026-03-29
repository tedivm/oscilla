## MODIFIED Requirements

### Requirement: CharacterRecord ORM model stores character identity

A `CharacterRecord` SQLAlchemy model (`oscilla/models/character.py`) SHALL map the `characters` table — the stable identity record that persists across all prestige runs:

**Columns:**

- `id`: UUID primary key
- `user_id`: UUID FK → `users.id`, NOT NULL
- `game_name`: TEXT NOT NULL — the `metadata.name` of the game package this character belongs to
- `name`: TEXT NOT NULL
- `created_at`: DATETIME NOT NULL
- `updated_at`: DATETIME NOT NULL

A `UNIQUE(user_id, game_name, name)` database constraint (`uq_character_user_game_name`) prevents duplicate character names per user per game. The old `uq_character_user_name` constraint is removed. There is no `version` column on `characters` — optimistic locking is only needed on the high-frequency `character_iterations` table.

#### Scenario: Same character name in different games is allowed

- **WHEN** a user has a character named "Aldric" in `the-kingdom` and creates a character named "Aldric" in `testlandia`
- **THEN** both rows exist without a constraint violation

#### Scenario: Duplicate character name in same game is rejected

- **WHEN** a user attempts to create a second character named "Aldric" in `the-kingdom`
- **THEN** the database raises an integrity error

---

## MODIFIED Requirements

### Requirement: Character service functions are game-scoped

All character service functions that operate on characters by name or user SHALL accept a `game_name: str` parameter and filter queries accordingly. This includes `save_character()`, `get_character_by_name()`, `list_characters_for_user()`, and `delete_user_characters()`. The `delete_user_characters()` function SHALL delete only characters belonging to the specified game; characters in other games for the same user SHALL be unaffected.

#### Scenario: list_characters_for_user returns only the selected game's characters

- **WHEN** `list_characters_for_user(session, user_id, game_name="testlandia")` is called
- **THEN** only characters with `game_name = "testlandia"` are returned

#### Scenario: delete_user_characters is game-scoped

- **WHEN** `delete_user_characters(session, user_id, game_name="testlandia")` is called
- **THEN** only Testlandia characters for the user are deleted; The Kingdom characters remain
