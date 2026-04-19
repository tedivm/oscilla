---
name: makefile
description: "Complete reference for all make targets in the Oscilla project. Use when: looking up the right make command for any task — setup, testing, linting, formatting, database, frontend, packaging, or cleanup."
---

# Makefile Reference

All developer tasks are exposed as `make` targets. Run from the project root.

---

## Setup

| Target        | What it does                                                    |
| ------------- | --------------------------------------------------------------- |
| `make install` | Install Python + frontend deps, create `.venv` (first-time setup) |
| `make sync`   | Sync Python deps with `uv.lock` (after pulling changes)         |
| `make pre-commit` | Install pre-commit hooks                                   |
| `make lock`   | Upgrade and relock all dependencies                             |
| `make lock-check` | Verify lock file is up to date without changing it         |

---

## Testing (Full Suite)

| Target          | What it does                                                      |
| --------------- | ----------------------------------------------------------------- |
| `make tests`    | Run **everything**: pytest, ruff, mypy, prettier, TOML lint, paracelsus, migration check, content validation, frontend check + vitest + Playwright lint |
| `make pytest`   | Run pytest with coverage report                                  |
| `make pytest_loud` | Run pytest with `DEBUG` log output enabled                    |
| `make validate` | Validate all content packages (YAML manifests)                   |

---

## Code Quality Checks

These check only — they do not auto-fix.

| Target                          | What it checks                                    |
| ------------------------------- | ------------------------------------------------- |
| `make ruff_check`               | Ruff linter                                       |
| `make black_check`              | Ruff formatter (black style)                      |
| `make mypy_check`               | Type checking (mypy)                              |
| `make prettier_check`           | Markdown, JSON, YAML, TOML formatting (prettier)  |
| `make tomlsort_check`           | TOML file formatting (tombi)                      |
| `make paracelsus_check`         | Database schema docs are up to date               |
| `make check_ungenerated_migrations` | No pending Alembic migration changes          |

---

## Code Formatting (Auto-fix)

| Target                   | What it fixes                                          |
| ------------------------ | ------------------------------------------------------ |
| `make chores`            | Run **all** auto-fixes: ruff, format, prettier, TOML, frontend formatting, schema docs |
| `make ruff_fixes`        | Auto-fix ruff lint issues                              |
| `make black_fixes`       | Auto-format Python code (black style via ruff)         |
| `make prettier_fixes`    | Auto-format markdown/JSON/YAML/TOML (root + frontend)  |
| `make tomlsort_fixes`    | Auto-format TOML files (tombi)                         |
| `make frontend_format_fix` | Auto-format frontend source files (prettier)         |

**Typical workflow before committing:** `make chores && make tests`

---

## Database

| Target                                          | What it does                                            |
| ----------------------------------------------- | ------------------------------------------------------- |
| `make create_migration MESSAGE="description"`   | Generate a new Alembic migration from model changes     |
| `make check_ungenerated_migrations`             | Fail if there are model changes without a migration     |
| `make run_migrations`                           | Apply all pending migrations (`alembic upgrade head`)   |
| `make document_schema`                          | Regenerate `docs/dev/database.md` from current models   |
| `make paracelsus_check`                         | Verify schema docs are current (read-only check)        |
| `make reset_db`                                 | Wipe local SQLite test DB and reapply all migrations    |
| `make clear_db`                                 | Delete `test.db*` files only (no migrations)            |

`create_migration` requires a `MESSAGE` argument:

```bash
make create_migration MESSAGE="add email_verified column to users"
```

---

## Frontend

### Core

| Target                  | What it does                                            |
| ----------------------- | ------------------------------------------------------- |
| `make frontend_install` | Install npm dependencies (`npm ci`)                    |
| `make frontend_build`   | Build production assets                                 |
| `make frontend_dev`     | Start Vite dev server (hot reload)                      |
| `make frontend_check`   | Run `svelte-check` type checking                        |
| `make frontend_test`    | Run Vitest unit tests                                   |
| `make frontend_format_fix` | Auto-format `src/` with prettier                    |
| `make frontend_format_check` | Check `src/` formatting (no writes)               |

### Playwright

| Target                        | What it does                                           |
| ----------------------------- | ------------------------------------------------------ |
| `make frontend_playwright_lint` | Parse all test files for config errors (no server needed) |
| `make frontend_e2e`           | Run E2E tests (spins up full stack automatically)      |
| `make frontend_a11y`          | Run accessibility tests (requires built frontend)      |
| `make frontend_playwright_all` | A11y + E2E across Chromium, Firefox, and WebKit       |

Single-browser variants: append `_chromium`, `_firefox`, or `_webkit` (e.g., `make frontend_e2e_chromium`).

`frontend_e2e` automatically:
1. Builds the frontend
2. Starts `db`, `redis`, and `mailhog` via Docker Compose
3. Runs an SQLite-backed API server on port 8000
4. Runs the frontend preview server on port 4173
5. Waits for both to be healthy, then runs tests
6. Cleans up all processes on exit

---

## Packaging and Cleanup

| Target             | What it does                                  |
| ------------------ | --------------------------------------------- |
| `make build`       | Build Python package distribution (sdist + wheel) |
| `make clean`       | Remove `*.log`, saves databases, stray `*.py` scripts |
| `make clean_logs`  | Remove `*.log` files                          |
| `make clean_saves` | Remove `saves.db*` files                      |

---

## Quick Reference by Task

| I want to…                                | Run                                  |
| ----------------------------------------- | ------------------------------------ |
| Set up for the first time                 | `make install`                       |
| Run all tests before a PR                 | `make tests`                         |
| Fix all formatting issues                 | `make chores`                        |
| Check types only                          | `make mypy_check`                    |
| Add a database migration                  | `make create_migration MESSAGE="..."` |
| Regenerate DB docs after model changes    | `make document_schema`               |
| Run only Python tests with verbose output | `make pytest_loud`                   |
| Run only frontend unit tests              | `make frontend_test`                 |
| Run E2E tests                             | `make frontend_e2e`                  |
| Update dependencies                       | `make lock && make sync`             |

---

## Further Reading

- [docs/dev/makefile.md](../../docs/dev/makefile.md) — Full makefile developer guide with detailed explanations of every target, shell autocomplete setup, and usage examples.
