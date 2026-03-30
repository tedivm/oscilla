## 1. Dependencies

- [x] 1.1 Add `platformdirs` to `[project.dependencies]` in `pyproject.toml`
- [x] 1.2 Run `make lock` to update `uv.lock`

## 2. Settings — Database Path Derivation

- [x] 2.1 Update `DatabaseSettings.derive_sqlite_url()` in `oscilla/conf/db.py` to derive the path from `platformdirs.user_data_path('oscilla') / 'oscilla.db'` instead of `games_path.parent / 'saves.db'`
- [x] 2.2 Call `mkdir(parents=True, exist_ok=True)` on the data directory inside `derive_sqlite_url()` before constructing the URL, so it is created on first use
- [x] 2.3 Update the `database_url` field description in `DatabaseSettings` to reference the new default path pattern

## 3. Log and Crash Report Paths

- [x] 3.1 Add `import platformdirs` to the top of `oscilla/cli.py`
- [x] 3.2 Update `_configure_logging()` in `oscilla/cli.py` to derive `log_path` from `platformdirs.user_data_path("oscilla") / "oscilla.log"` instead of `settings.games_path.parent / "oscilla.log"`
- [x] 3.3 Update `write_crash_report()` in `oscilla/services/crash.py` to derive `crash_path` from `platformdirs.user_data_path("oscilla") / f"oscilla-crash-{timestamp}.log"` instead of `settings.games_path.parent / ...`
- [x] 3.4 Add `import platformdirs` to `oscilla/services/crash.py` and remove the `settings` import if it is no longer needed for anything else in that file

## 4. CLI — data-path Command

- [x] 4.1 Add a `data-path` command to `oscilla/cli.py` that prints `str(platformdirs.user_data_path('oscilla'))` to stdout
- [x] 4.2 Verify `oscilla data-path` appears in `oscilla --help` output

## 5. Tests

- [x] 5.1 Add unit test asserting that when `DATABASE_URL` is not set, the derived URL contains `oscilla.db` and not `saves.db`
- [x] 5.2 Add unit test asserting that the derived URL is under `user_data_path('oscilla')`
- [x] 5.3 Add unit test asserting that when `DATABASE_URL` is explicitly set, `derive_sqlite_url` does not override it
- [x] 5.4 Add unit test asserting that changing `games_path` does not affect the derived database URL
- [x] 5.5 Add unit test asserting that `_configure_logging()` (with `user_data_path` monkeypatched to a `tmp_path`) writes `oscilla.log` inside the data directory
- [x] 5.6 Add unit test asserting that `write_crash_report()` (with `user_data_path` monkeypatched) writes the crash file inside the data directory
- [x] 5.7 Add CLI test asserting `oscilla data-path` exits with code 0
- [x] 5.8 Add CLI test asserting the output of `oscilla data-path` matches `str(platformdirs.user_data_path('oscilla'))`

## 6. Documentation

- [x] 6.1 Update `.env.example`: update the `DATABASE_URL` comment to describe the new default path; update the `DEBUG` comment to note `oscilla.log` is written to the platform data directory
- [x] 6.2 Update `README.md` environment variable table: change the `DATABASE_URL` default description
- [x] 6.3 Add `data-path` command documentation to `README.md` CLI section
- [x] 6.4 Update `docs/dev/database.md` to reflect the new default SQLite path and explain the `platformdirs` derivation
- [x] 6.5 Update `docs/dev/settings.md` to update the `DATABASE_URL` default value description

## 7. Cleanup

- [x] 7.1 Delete `saves.db` and any `saves.bak.*` files from the project root
- [x] 7.2 Ensure `saves.db` and `saves.bak.*` patterns are in `.gitignore` or confirm they are already excluded
- [x] 7.3 Run `make tests` and confirm all checks pass
