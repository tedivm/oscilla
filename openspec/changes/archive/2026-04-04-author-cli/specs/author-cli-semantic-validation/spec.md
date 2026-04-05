# Author CLI — Semantic Validation

## ADDED Requirements

### Requirement: Semantic validation command

The system SHALL provide an `oscilla content test` command that runs cross-manifest semantic checks against a fully loaded `ContentRegistry`. These checks supplement Pydantic schema validation with analysis that requires cross-manifest context. The command SHALL accept:

- `--game NAME` (optional): scope to a single game package.
- `--strict` (flag, optional): treat warnings as errors; exits with code 1 if any warnings are found.
- `--format text|json|yaml` (option, optional): output results as a JSON or YAML object with `errors` and `warnings` arrays.

The command SHALL exit with code 0 when no errors are found (and no warnings if `--strict`), and code 1 otherwise.

#### Scenario: Clean content produces zero issues

- **WHEN** `oscilla content test` is run against a content package with no cross-manifest errors or warnings
- **THEN** a success message is printed and the command exits with code 0

#### Scenario: Undefined adventure reference detected

- **WHEN** a location's adventure pool references an adventure name that has no corresponding manifest
- **THEN** `oscilla content test` reports an error of kind `undefined_ref` and exits with code 1

#### Scenario: Circular region parent chain detected

- **WHEN** region A has parent B and region B has parent A
- **THEN** `oscilla content test` reports an error of kind `circular_chain` for at least one of the regions

#### Scenario: Orphaned adventure is a warning

- **WHEN** an adventure manifest exists but is not referenced in any location's adventure pool
- **THEN** `oscilla content test` reports a warning of kind `orphaned`; the command exits with code 0 unless `--strict` is set

#### Scenario: Strict mode treats warnings as errors

- **WHEN** `oscilla content test --strict` is run with one orphaned adventure warning
- **THEN** the command exits with code 1 and the warning is formatted as an error

#### Scenario: JSON output

- **WHEN** `oscilla content test --format json` is run
- **THEN** a JSON object is printed with `errors` and `warnings` arrays; each element contains `kind`, `message`, and `manifest` fields

---

### Requirement: Default semantic checks on validate command

The existing `oscilla validate` command SHALL run all semantic checks by default in addition to schema validation. The command SHALL accept a `--no-semantic` flag to skip semantic checks for faster runs or when only schema errors are of interest.

#### Scenario: validate runs semantic checks by default

- **WHEN** `oscilla validate` is run against a package with an undefined enemy reference
- **THEN** the semantic error is included in the output alongside any schema errors

#### Scenario: validate --no-semantic skips semantic checks

- **WHEN** `oscilla validate --no-semantic` is run
- **THEN** only schema-level errors and load warnings are reported; no semantic checks are run

#### Scenario: validate --strict fails on semantic warnings

- **WHEN** `oscilla validate --strict` is run against a package with only orphaned-adventure warnings
- **THEN** the command exits with code 1 and the warnings are displayed as errors
