## MODIFIED Requirements

### Requirement: Content directory scanning

The content loader SHALL accept a configurable game _library root_ path via the `GAMES_PATH` setting (env var `GAMES_PATH`). The `load_games(library_root: Path)` function SHALL scan immediate subdirectories of `library_root` for game packages (directories containing a `game.yaml`). Subdirectories without a `game.yaml` are silently skipped. The single-game `load(content_path: Path)` function is retained as an internal helper and accepts either a directory path or a path to a single YAML file.

#### Scenario: GAMES_PATH is used as library root

- **WHEN** the `GAMES_PATH` setting is set to a custom directory
- **THEN** `load_games()` scans that directory's immediate subdirectories for game packages

#### Scenario: Non-YAML files are ignored within a game package

- **WHEN** a game package directory contains files with extensions other than `.yaml` or `.yml`
- **THEN** those files are silently ignored during manifest scanning

#### Scenario: Game package with no YAML files loads cleanly

- **WHEN** a subdirectory contains a `game.yaml` but no other manifests
- **THEN** the package loads without error and the registry contains only the `Game` manifest

#### Scenario: load() accepts a single file path

- **WHEN** `load()` is called with a path to a single YAML file (not a directory)
- **THEN** all documents in that file are used as the complete manifest set and a ContentRegistry is returned

---

## ADDED Requirements

### Requirement: Schema export provides an umbrella union schema

The schema export system SHALL provide an `export_union_schema()` function that returns a JSON Schema covering all registered manifest kinds as a `kind`-discriminated `oneOf` union. This schema SHALL be written as `manifest.json` alongside per-kind schema files when `oscilla content schema --output` is invoked.

#### Scenario: Union schema covers all registered kinds

- **WHEN** `export_union_schema()` is called
- **THEN** the returned schema contains references to every kind registered in `ALL_KINDS`

#### Scenario: Union schema is written as manifest.json

- **WHEN** `oscilla content schema --output <dir>` is invoked
- **THEN** a `manifest.json` file is written to `<dir>` alongside the per-kind schema files

---

### Requirement: `content schema --vscode` uses a content-path glob association

When `--vscode` is passed to `oscilla content schema`, the `.vscode/settings.json` `yaml.schemas` entry SHALL use a content-path glob (`./content/**/*.yaml`) pointing at `manifest.json`, rather than per-filename globs. The default output directory when `--output` is not provided SHALL be `.vscode/oscilla-schemas/`.

#### Scenario: --vscode without --output defaults to .vscode/oscilla-schemas/

- **WHEN** `oscilla content schema --vscode` is run without `--output`
- **THEN** schemas are written to `.vscode/oscilla-schemas/` and `settings.json` is updated

#### Scenario: settings.json contains content glob pointing at manifest.json

- **WHEN** `oscilla content schema --vscode` completes
- **THEN** `.vscode/settings.json` contains a `yaml.schemas` entry mapping `./content/**/*.yaml` to the path of `manifest.json`

#### Scenario: Existing settings.json content is preserved

- **WHEN** `.vscode/settings.json` already contains other keys (e.g., theme or extension settings)
- **THEN** those keys are unchanged after the command runs; only `yaml.schemas` is updated
