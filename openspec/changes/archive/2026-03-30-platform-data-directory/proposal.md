## Why

The SQLite save database is currently derived from `games_path` and ends up at the project root as `saves.db`, polluting the git working tree alongside source code. The file name "saves.db" is also non-standard for an application database. User data should live in the OS-designated user data directory, following platform conventions.

## What Changes

- Add `platformdirs` as a direct dependency in `pyproject.toml`.
- Change the default SQLite database path from `<games_path.parent>/saves.db` to `<user_data_dir('oscilla')>/oscilla.db` (e.g. `~/Library/Application Support/oscilla/oscilla.db` on macOS, `~/.local/share/oscilla/oscilla.db` on Linux).
- Decouple database path derivation from `games_path` — the two settings have unrelated concerns.
- Move `oscilla.log` (debug log) from `games_path.parent / "oscilla.log"` to `user_data_path('oscilla') / "oscilla.log"`.
- Move crash reports from `games_path.parent / "oscilla-crash-<timestamp>.log"` to `user_data_path('oscilla') / "oscilla-crash-<timestamp>.log"`.
- Ensure the data directory is created automatically if it does not exist before opening the database.
- Add an `oscilla data-path` CLI command that prints the resolved data directory path to stdout, making it easy to script against (backup, reset, inspect).
- Update `DatabaseSettings` commentary, `.env.example`, `README.md`, and developer documentation to reflect the new default path.

## Capabilities

### New Capabilities

- `data-directory`: Platform-standard user data directory management — resolving, creating, and exposing the OS-appropriate data directory used for the application's SQLite database and any future user-scoped persistent files.

### Modified Capabilities

- `player-persistence`: The default SQLite database URL derivation no longer ties to `games_path`; it derives from `platformdirs.user_data_path('oscilla')` instead, and the database filename changes from `saves.db` to `oscilla.db`.
- `cli-game-loop`: A new `data-path` command is added to the CLI.

## Impact

- `oscilla/conf/db.py`: `DatabaseSettings.derive_sqlite_url()` validator updated to use `platformdirs`.
- `oscilla/cli.py`: `_configure_logging()` updated to write `oscilla.log` to the data directory; new `data-path` command added.
- `oscilla/services/crash.py`: `write_crash_report()` updated to write crash files to the data directory.
- `pyproject.toml`: `platformdirs` added to `[project.dependencies]`.
- `.env.example`: Comment describing the default log and database paths updated.
- `README.md`: Environment variable table updated; `data-path` command documented.
- `docs/dev/database.md`: Default path updated in documentation.
- `docs/dev/settings.md`: `DATABASE_URL` default description updated.
