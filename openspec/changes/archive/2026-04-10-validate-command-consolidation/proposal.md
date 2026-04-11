## Why

The `oscilla validate` command and `oscilla content test` command overlap significantly — both load a game package and run validation — but are split across two locations with inconsistent output options. Consolidating them into a single, more capable `validate` command reduces cognitive overhead for content authors and unlocks a new use case: validating manifest content piped from stdin, enabling inline doc examples, CI linting pipelines, and ad-hoc manifest authoring feedback without a full game package on disk.

## What Changes

- **`oscilla validate`** gains three new flags:
  - `--format text|json|yaml` — structured output for CI and tooling (text is default)
  - `--no-references` — skip cross-manifest reference validation
  - **`--stdin`** — explicitly read YAML manifests from stdin instead of from disk; `--game` is ignored in this mode
- **`oscilla content test`** becomes a backwards-compatible alias for `oscilla validate --no-semantic`, preserving existing scripts
- Structured output (`json`/`yaml`) always includes a `summary` field alongside `errors` and `warnings`

## Capabilities

### New Capabilities

- `validate-stdin`: Ability to validate one or more YAML manifest documents piped to `oscilla validate` via stdin, using the same parse → reference check → semantic validation pipeline as disk-based loading

### Modified Capabilities

- `cli-game-loop`: The `validate` command gains `--format`, `--no-references`, and `--stdin`; `content test` becomes an alias

## Impact

- `oscilla/cli.py` — `validate` command updated
- `oscilla/cli_content.py` — `content test` becomes a thin wrapper
- `tests/test_cli.py` — new test scenarios for stdin mode, `--format`, `--no-references`
- `docs/dev/cli.md` — updated to reflect consolidated interface
- `docs/authors/cli.md` — updated to reflect consolidated interface
