# validate-stdin

## Purpose

Specification for stdin-based manifest validation in the `oscilla validate` command, including the `--no-references` and `--format` flags.

## Requirements

### Requirement: Validate manifests from stdin

The `oscilla validate` command SHALL accept a `--stdin` flag. When `--stdin` is passed, the command SHALL read all YAML manifest content from stdin instead of scanning GAMES_PATH. The `--game` flag SHALL be silently ignored when `--stdin` is used. The same parse → reference → condition compilation → template → semantic pipeline SHALL be applied as for disk-based loading.

#### Scenario: Valid manifest batch passes validation

- **WHEN** one or more valid YAML manifests are piped to `oscilla validate`
- **THEN** the command exits 0 and reports no errors

#### Scenario: Invalid YAML exits with error

- **WHEN** malformed YAML is piped to `oscilla validate`
- **THEN** the command exits 1 and reports a YAML parse error

#### Scenario: Unknown kind exits with error

- **WHEN** a YAML document with an unrecognized `kind:` field is piped to `oscilla validate`
- **THEN** the command exits 1 and reports an unknown kind error

#### Scenario: Empty stdin exits with error

- **WHEN** empty or whitespace-only content is piped to `oscilla validate`
- **THEN** the command exits 1 with a message indicating no content was provided

#### Scenario: Multiple documents validated as a batch

- **WHEN** a multi-document YAML stream separated by `---` is piped to `oscilla validate`
- **THEN** all documents are parsed and cross-document references are validated together

#### Scenario: --game flag ignored when --stdin is used

- **WHEN** both `--stdin` and `--game nonexistent` are passed
- **THEN** the `--game` flag is ignored and validation proceeds against the stdin content; the command does not exit 1 due to the unknown game name

---

### Requirement: --no-references flag

The `oscilla validate` command SHALL accept a `--no-references` flag that skips cross-manifest reference validation. This flag SHALL be honoured in both disk mode and stdin mode.

#### Scenario: Manifest referencing absent item passes with --no-references

- **WHEN** a manifest that references another manifest not present in the batch is validated with `--no-references`
- **THEN** the command exits 0 (reference errors are suppressed)

#### Scenario: Manifest referencing absent item fails without --no-references

- **WHEN** a manifest that references another manifest not present in the batch is validated without `--no-references`
- **THEN** the command exits 1 with a reference error

---

### Requirement: --format flag on validate command

The `oscilla validate` command SHALL accept a `--format` flag with values `text` (default), `json`, and `yaml`. Structured output formats SHALL emit a document with three top-level keys: `errors`, `warnings`, and `summary`.

#### Scenario: JSON output includes required keys

- **WHEN** `oscilla validate --format json` is run
- **THEN** stdout is valid JSON containing `errors`, `warnings`, and `summary` keys

#### Scenario: YAML output includes required keys

- **WHEN** `oscilla validate --format yaml` is run
- **THEN** stdout is valid YAML containing `errors`, `warnings`, and `summary` keys

#### Scenario: Summary key in stdin JSON mode uses stdin label

- **WHEN** manifests are piped to `oscilla validate --format json`
- **THEN** the `summary` object contains a key `"<stdin>"` with manifest kind counts

#### Scenario: Summary key in disk mode uses package name

- **WHEN** `oscilla validate --format json` is run against a game package named `testlandia`
- **THEN** the `summary` object contains a key `"testlandia"` with manifest kind counts

#### Scenario: Invalid format value exits with error

- **WHEN** `--format invalid` is passed
- **THEN** the command exits 1 with an error message listing valid format values
