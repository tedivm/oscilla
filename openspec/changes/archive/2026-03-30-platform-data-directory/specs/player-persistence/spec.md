## ADDED Requirements

### Requirement: Default SQLite database lives in the platform data directory

When `DATABASE_URL` is not explicitly configured, the application SHALL derive a SQLite database URL using the platform data directory resolved by `platformdirs.user_data_path('oscilla')`. The derived database file SHALL be named `oscilla.db`. The derived URL format SHALL be `sqlite+aiosqlite:///<absolute_path_to_oscilla.db>`.

This derivation SHALL be independent of `GAMES_PATH` — changing the game library location SHALL NOT affect where save data lives.

#### Scenario: Default URL uses platform data directory

- **WHEN** `DATABASE_URL` is not set
- **THEN** the derived `database_url` is `sqlite+aiosqlite:///<user_data_path('oscilla')>/oscilla.db`

#### Scenario: Explicit DATABASE_URL is not overridden

- **WHEN** `DATABASE_URL=postgresql+asyncpg://user:pass@localhost/oscilla` is set
- **THEN** `database_url` equals the explicitly set value and the derivation logic does not run

#### Scenario: Changing GAMES_PATH does not affect database location

- **WHEN** `GAMES_PATH=/custom/library` is set and `DATABASE_URL` is not set
- **THEN** the derived `database_url` still points to `<user_data_path('oscilla')>/oscilla.db`, not to `/custom/library/../oscilla.db`
