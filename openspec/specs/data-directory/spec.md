# Data Directory

## Purpose

Defines how Oscilla resolves, creates, and exposes a platform-appropriate user data directory for storing the application's persistent user files (SQLite database and any future user-scoped data).

## Requirements

### Requirement: User data directory follows platform conventions

The application SHALL use `platformdirs.user_data_path('oscilla')` to resolve the user data directory. This maps to OS-native conventions:

- macOS: `~/Library/Application Support/oscilla/`
- Linux: `~/.local/share/oscilla/` (respects `XDG_DATA_HOME`)
- Windows: `%LOCALAPPDATA%\oscilla\`

#### Scenario: macOS resolves to Application Support

- **WHEN** the application runs on macOS
- **THEN** the data directory SHALL be `~/Library/Application Support/oscilla/`

#### Scenario: Linux respects XDG_DATA_HOME

- **WHEN** `XDG_DATA_HOME=/custom/data` is set on Linux
- **THEN** the data directory SHALL be `/custom/data/oscilla/`

#### Scenario: Linux falls back to ~/.local/share when XDG_DATA_HOME is unset

- **WHEN** `XDG_DATA_HOME` is not set on Linux
- **THEN** the data directory SHALL be `~/.local/share/oscilla/`

---

### Requirement: Data directory is created automatically on first use

When the data directory is needed and does not exist, it SHALL be created automatically (including any missing parent directories). The application SHALL NOT require the user to manually create this directory.

#### Scenario: First run creates the data directory

- **WHEN** the data directory does not exist and `DATABASE_URL` is not explicitly set
- **THEN** the data directory is created before the database URL is derived, and the application starts without error

#### Scenario: Existing data directory is left untouched

- **WHEN** the data directory already exists
- **THEN** no error is raised and no content is modified

---

### Requirement: data-path CLI command prints the data directory

The system SHALL provide a `data-path` CLI command that prints the resolved data directory path to stdout (without a trailing newline beyond the standard one added by the shell). The command SHALL exit with code 0. No arguments or options are required.

#### Scenario: data-path prints the user data directory

- **WHEN** `oscilla data-path` is run
- **THEN** the output is the resolved `user_data_path('oscilla')` path as a string, followed by a newline

#### Scenario: data-path output is a usable path

- **WHEN** the output of `oscilla data-path` is passed to `ls` or `cd` in a shell
- **THEN** the path is a valid, existing directory (created on first run)
