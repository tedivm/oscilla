## MODIFIED Requirements

### Requirement: Validate command options

The `oscilla validate` command SHALL accept the following flags:

- `--game GAME_NAME` (string, optional): validate only this game package. Silently ignored when `--stdin` is used.
- `--stdin` (flag, optional): read YAML manifest content from stdin instead of from GAMES_PATH.
- `--strict` (flag, optional): treat warnings as errors and exit 1 if any are present.
- `--no-semantic` (flag, optional): skip semantic checks (undefined refs, circular chains, orphaned/unreachable content).
- `--no-references` (flag, optional): skip cross-manifest reference validation.
- `--format FORMAT` (string, optional, default `text`): output format — `text`, `json`, or `yaml`.

#### Scenario: --format flag appears in validate --help

- **WHEN** `oscilla validate --help` is run
- **THEN** `--format` and `-F` appear in the output

#### Scenario: --no-references flag appears in validate --help

- **WHEN** `oscilla validate --help` is run
- **THEN** `--no-references` appears in the output

#### Scenario: validate with no flags uses text output

- **WHEN** `oscilla validate` is run with no flags
- **THEN** output is in text format (no JSON structure)

---

### Requirement: content test command is a backwards-compatible alias

The `oscilla content test` command SHALL remain available and SHALL behave identically to `oscilla validate` for disk-based validation. It SHALL accept `--game`, `--strict`, and `--format` flags with the same semantics. It SHALL NOT accept `--no-references` or `--no-semantic`.

#### Scenario: content test succeeds on valid content

- **WHEN** `oscilla content test` is run against valid game content
- **THEN** the command exits 0

#### Scenario: content test --format json produces structured output

- **WHEN** `oscilla content test --format json` is run
- **THEN** stdout is valid JSON containing `errors`, `warnings`, and `summary` keys
