## ADDED Requirements

### Requirement: data-path command is available in the CLI

The system SHALL expose a `data-path` command in the `oscilla` CLI that prints the resolved user data directory to stdout. This is defined here as a CLI-loop concern: it is a first-class, discoverable CLI command alongside `game`, `validate`, and `version`.

#### Scenario: data-path appears in --help output

- **WHEN** `oscilla --help` is run
- **THEN** `data-path` appears in the list of available commands with a brief description

#### Scenario: data-path is a synchronous command

- **WHEN** `data-path` is invoked
- **THEN** it completes without requiring an async runtime, database connection, or any external service
