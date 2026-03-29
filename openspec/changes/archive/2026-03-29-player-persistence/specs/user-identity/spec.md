# User Identity

## Purpose

Defines how a stable user identity is resolved and persisted for the TUI, and how the `users` table is structured for future web auth integration.

## ADDED Requirements

### Requirement: UserRecord ORM model stores user identity

A `UserRecord` SQLAlchemy model (`oscilla/models/user.py`) SHALL map the `users` table with the following columns:

- `id`: UUID primary key
- `user_key`: TEXT UNIQUE NOT NULL — stable identity string for the user
- `created_at`: DATETIME NOT NULL

#### Scenario: New user row is created

- **WHEN** `get_or_create_user(session, user_key)` is called with a key that does not exist in the table
- **THEN** a new row is inserted and returned

#### Scenario: Existing user row is returned

- **WHEN** `get_or_create_user(session, user_key)` is called with a key that already exists
- **THEN** the existing row is returned without creating a duplicate

---

### Requirement: TUI user key is derived from system environment

The function `derive_tui_user_key()` (`oscilla/services/user.py`) SHALL return a string in the format `<username>@<hostname>`:

- `username` is read from the `USER` env var, falling back to `LOGNAME`, falling back to `"unknown"`
- `hostname` is obtained from `socket.gethostname()`

#### Scenario: USER env var is set

- **WHEN** `USER=tedivm` and `socket.gethostname()` returns `"macbook-pro"`
- **THEN** `derive_tui_user_key()` returns `"tedivm@macbook-pro"`

#### Scenario: USER env var is absent, LOGNAME present

- **WHEN** `USER` is not set, `LOGNAME=backup`, and `socket.gethostname()` returns `"server1"`
- **THEN** `derive_tui_user_key()` returns `"backup@server1"`

#### Scenario: Both USER and LOGNAME are absent

- **WHEN** neither `USER` nor `LOGNAME` is set
- **THEN** `derive_tui_user_key()` returns `"unknown@<hostname>"`

---

### Requirement: TUI auto-creates user on first launch

On TUI startup, if no user row exists for the derived key, a new `UserRecord` SHALL be created and committed. This operation SHALL be transparent to the user — no user-visible message is shown.

#### Scenario: First ever launch

- **WHEN** `oscilla game` is run for the first time on a machine
- **THEN** a user row with `user_key = derive_tui_user_key()` is created in the database

#### Scenario: Subsequent launch

- **WHEN** `oscilla game` is run again on the same machine
- **THEN** the existing user row is retrieved and no new row is created
