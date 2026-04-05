# Author CLI — Schema Export

## ADDED Requirements

### Requirement: Single-kind schema export

The system SHALL provide an `oscilla content schema KIND` command that prints the JSON Schema for one manifest kind to stdout. The schema SHALL be derived from the Pydantic v2 model for that kind and SHALL include `$schema`, `$id`, and `title` metadata. The command SHALL accept:

- `KIND` (positional, optional): a manifest kind slug (e.g. `adventure`, `region`, `enemy`). If omitted, all schemas are exported.
- `--output FILE` (optional): write the schema to this file path instead of stdout.

#### Scenario: Export adventure schema to stdout

- **WHEN** `oscilla content schema adventure` is run
- **THEN** a valid JSON object is printed containing at minimum a `$schema` field, `$id` field, and `properties` describing the adventure manifest structure

#### Scenario: Export schema to file

- **WHEN** `oscilla content schema adventure --output /tmp/adventure.json` is run
- **THEN** the schema is written to `/tmp/adventure.json` and a confirmation message is printed

#### Scenario: Unknown kind exits with error

- **WHEN** `oscilla content schema widget` is run
- **THEN** the command exits with code 1 and prints an error listing valid kinds

---

### Requirement: All-kinds schema export

The system SHALL allow omitting the KIND argument to export all manifest kind schemas at once. When `--output` is a directory path, each schema SHALL be written as a separate `<kind>.json` file in that directory.

#### Scenario: Export all schemas to stdout

- **WHEN** `oscilla content schema` is run with no arguments
- **THEN** a JSON object is printed keyed by kind slug, with each value being that kind's full JSON Schema

#### Scenario: Export all schemas to directory

- **WHEN** `oscilla content schema --output /tmp/schemas/` is run
- **THEN** one `.json` file per kind is created in `/tmp/schemas/` and the count of written files is confirmed in the output

#### Scenario: Schema is compatible with yaml-language-server

- **WHEN** an exported adventure schema is referenced via a `# yaml-language-server: $schema=...` directive in a YAML manifest
- **THEN** a conforming YAML-aware editor provides schema-driven autocomplete and validation for the manifest's fields
