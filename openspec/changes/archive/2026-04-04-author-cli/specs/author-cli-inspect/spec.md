# Author CLI — Inspect

## ADDED Requirements

### Requirement: Content list command

The system SHALL provide an `oscilla content list KIND` command that loads the content registry and prints a tabular summary of all manifests of the requested kind. The command SHALL accept:

- `KIND` (positional argument, required): one of `regions`, `locations`, `adventures`, `enemies`, `items`, `skills`, `buffs`, `quests`, `recipes`, `classes`, `loot-tables`.
- `--game NAME` (optional): scopes the load to a single game package; auto-selects if only one exists.
- `--format text|json|yaml` (option, optional): output format; `text` (default) produces a Rich table, `json` or `yaml` produce machine-readable output.

#### Scenario: List adventures as table

- **WHEN** `oscilla content list adventures` is run against a content package with at least one adventure
- **THEN** a formatted table is printed to stdout with columns for `name`, `kind`, `display_name`, `steps`, and `repeatable`

#### Scenario: List adventures as JSON

- **WHEN** `oscilla content list adventures --format json` is run
- **THEN** a JSON array is printed where each element contains at least `name` and `kind` fields

#### Scenario: Unknown kind exits with error

- **WHEN** `oscilla content list widgets` is run
- **THEN** the command exits with code 1 and prints an error message listing valid kinds

#### Scenario: Empty kind produces friendly message

- **WHEN** `oscilla content list quests` is run against a package with no quests
- **THEN** the command exits with code 0 and prints a message indicating no manifests were found

#### Scenario: Multiple games requires --game flag

- **WHEN** multiple game packages are present and `--game` is not supplied
- **THEN** the command exits with code 1 and prints the names of available packages

---

### Requirement: Content show command

The system SHALL provide an `oscilla content show KIND NAME` command that prints a detailed description of a single manifest, including its spec fields and cross-references (what it references and what references it). The command SHALL accept:

- `KIND` (positional, required): manifest kind slug (singular or plural).
- `NAME` (positional, required): the manifest's `metadata.name`.
- `--game NAME` (optional): scope to a single game package.
- `--format text|json|yaml` (option, optional): output the full manifest as a JSON or YAML object (including a `xrefs` sub-object) instead of Rich formatted text.

#### Scenario: Show adventure details

- **WHEN** `oscilla content show adventure goblin-fight` is run
- **THEN** the display name, step count, and any outbound cross-references (enemies, items) are printed

#### Scenario: Show region references

- **WHEN** `oscilla content show region forest` is run
- **THEN** locations that reference the region are listed in the "Referenced by" section

#### Scenario: Show manifest as JSON

- **WHEN** `oscilla content show adventure goblin-fight --format json` is run
- **THEN** the output is valid JSON containing both the `manifest` object and an `xrefs` object

#### Scenario: Unknown manifest exits with error

- **WHEN** `oscilla content show adventure nonexistent-adventure` is run
- **THEN** the command exits with code 1 and prints a not-found message
