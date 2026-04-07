# Manifest System

## Purpose

The manifest system provides the foundational content loading infrastructure for the game engine, including YAML parsing, cross-reference validation, and content registry management.

## Requirements

### Requirement: YAML manifest envelope structure

All content manifests SHALL use a four-field top-level envelope: `apiVersion`, `kind`, `metadata`, and `spec`. The `apiVersion` field SHALL be `oscilla/v1`. The `kind` field SHALL be one of the registered entity kinds. The `metadata` field SHALL contain at minimum a `name` string that is unique within its kind. The `spec` field SHALL contain kind-specific configuration.

#### Scenario: Valid manifest is parsed

- **WHEN** the content loader reads a YAML file with a valid envelope and a recognised `kind`
- **THEN** it parses the file into the corresponding Pydantic manifest model without error

#### Scenario: Unknown kind is rejected

- **WHEN** the content loader reads a YAML file with an unrecognised `kind` value
- **THEN** it raises a validation error identifying the file and the invalid kind

#### Scenario: Missing required envelope field

- **WHEN** a manifest file omits `apiVersion`, `kind`, `metadata`, or `metadata.name`
- **THEN** the loader raises a validation error identifying the missing field and file path

---

### Requirement: Supported entity kinds

The manifest system SHALL support the following `kind` values: `Region`, `Location`, `Adventure`, `Enemy`, `Item`, `Recipe`, `Quest`, `Class`, `Game`, and `CharacterConfig`.

#### Scenario: Each kind maps to a Pydantic model

- **WHEN** a manifest with a supported `kind` is loaded
- **THEN** it is validated against the corresponding Pydantic schema and stored in the content registry under that kind's namespace

---

### Requirement: CharacterConfig manifest defines player stats

The `CharacterConfig` manifest SHALL define `public_stats` and `hidden_stats` as lists of `StatDefinition`. Each `StatDefinition` SHALL have a `name` (string), `type` (`"int"` or `"bool"` — `"float"` is not a valid type), `default` (`int | bool | None`), and `description` (string, optional). Each `StatDefinition` for an `int` stat MAY include an optional `bounds: StatBounds` object with `min: int | None` and `max: int | None` fields. Setting `bounds` on a `bool` stat is a content load error. Stat names SHALL be unique across `public_stats` and `hidden_stats` within the same `CharacterConfig`; duplicate names SHALL be a content load error.

#### Scenario: Valid character config with int and bool stats loads successfully

- **WHEN** a `CharacterConfig` manifest declares `int` and `bool` stats with valid names and defaults
- **THEN** the manifest loads without error and the stat definitions are accessible via `CharacterConfigSpec`

#### Scenario: Float stat type is rejected

- **WHEN** a `CharacterConfig` manifest declares a stat with `type: float`
- **THEN** the content loader raises a `ValidationError` identifying the invalid stat type

#### Scenario: Player stat storage matches CharacterConfig

- **WHEN** a new player is created and a `CharacterConfig` manifest is present
- **THEN** the player's stat map contains every stat defined in both `public_stats` and `hidden_stats`, initialised to each stat's declared default (or `null` if no default is set)

#### Scenario: Duplicate stat names are a load error

- **WHEN** a `CharacterConfig` manifest declares two stats with the same name (even if one is public and one hidden)
- **THEN** the content loader raises a `ValidationError` listing the duplicate names

#### Scenario: Unknown stat reference is rejected

- **WHEN** a condition, adventure step, or other manifest references a stat name that does not appear in `CharacterConfig`
- **THEN** the content loader raises a validation error at cross-reference validation time identifying the referencing manifest and the unknown stat name

#### Scenario: Stat default type is validated at load time

- **WHEN** a stat's `default` value is not compatible with its declared `type`
- **THEN** the content loader raises a validation error at parse time

#### Scenario: CharacterConfig with bounds on int stat loads successfully

- **WHEN** a `CharacterConfig` declares an `int` stat with `bounds: { min: 0, max: 1000000 }`
- **THEN** the manifest loads without error and the stat's bounds are accessible

#### Scenario: CharacterConfig with bounds on bool stat is a load error

- **WHEN** a `CharacterConfig` declares a `bool` stat with any `bounds` value
- **THEN** the content loader raises a `ValidationError` identifying the stat name and invalid field

---

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

### Requirement: Cross-reference validation

The content loader SHALL validate all cross-references between manifests after all files are parsed. Any reference (e.g., a Location referencing a Region by name, an Adventure referencing an Enemy by name) where the target does not exist in the registry SHALL be reported as a validation error.

#### Scenario: Valid cross-reference resolves

- **WHEN** a Location manifest references a Region by `metadata.name` that exists in the registry
- **THEN** the reference resolves successfully with no error

#### Scenario: Broken cross-reference is reported

- **WHEN** a Location manifest references a Region name that does not exist in the registry
- **THEN** the loader raises a validation error that includes both the referencing file and the missing target name

---

### Requirement: Region and Location inheritance of unlock conditions

Regions form a tree via an optional `parent` reference in their spec. Locations belong to exactly one Region. The effective unlock condition for a Location SHALL be the logical `all` conjunction of: the Location's own `unlock` condition (if any), plus the `unlock` condition of its Region, plus all ancestor Region `unlock` conditions up to the root.

#### Scenario: Location inherits ancestor conditions

- **WHEN** a Location belongs to a Region that has a `level: 3` unlock condition, and the Location itself has a `milestone: found-map` unlock condition
- **THEN** the effective condition for the Location requires both `level ≥ 3` AND `milestone: found-map`

#### Scenario: Location with no own condition inherits region condition

- **WHEN** a Location has no `unlock` block but its Region has an `unlock` condition
- **THEN** the effective condition for the Location is the Region's condition

#### Scenario: Root region with no unlock is always accessible

- **WHEN** a Region has no parent and no `unlock` condition
- **THEN** all Locations in that Region (with no own unlock) are always accessible

---

### Requirement: Validate CLI command

The system SHALL provide a `validate` CLI command that loads and validates all game packages under `GAMES_PATH`. By default it validates all games and reports errors per-game. An optional `--game GAME_NAME` flag restricts validation to a single named game package.

#### Scenario: Validate with no flag validates all games

- **WHEN** `oscilla validate` is run against a library root containing two game packages
- **THEN** both packages are validated and a per-game success or error summary is printed

#### Scenario: Validate with --game validates one game

- **WHEN** `oscilla validate --game testlandia` is run
- **THEN** only the `testlandia` package is validated; other packages are not loaded

#### Scenario: Valid content reports success per game

- **WHEN** `oscilla validate` is run against a library where all packages have no errors
- **THEN** the command exits with code 0 and prints a success summary for each game

#### Scenario: Invalid content reports all errors

- **WHEN** `oscilla validate` is run and one game contains an invalid manifest
- **THEN** the command exits with a non-zero code and prints each error with its game package name and source file path

#### Scenario: Validate does not start the game

- **WHEN** `oscilla validate` completes (success or failure)
- **THEN** no game session is started and no player state is initialized

---

### Requirement: Template strings are valid values in string-typed manifest fields

Any manifest field with a declared type of `str` SHALL accept Jinja2 template syntax as its value. The loader SHALL detect template strings by the presence of `{{`, `{%`, or a pronoun/verb placeholder pattern (`{word}` where `word` is a known pronoun or verb). Detected template strings SHALL be preprocessed (pronoun placeholder substitution), compiled into a `jinja2.Template`, and stored in the `GameTemplateEngine` cache keyed by a stable template identifier path. Template compilation and mock-render validation SHALL occur as part of `load()` after all existing parse and cross-reference validations pass.

#### Scenario: Template string in NarrativeStep text field is accepted

- **WHEN** an `Adventure` manifest has `text: "{{ player.name }} received the reward."`
- **THEN** `load()` compiles the template and stores it without error

#### Scenario: Template string with unknown player property fails load

- **WHEN** an `Adventure` manifest has `text: "{{ player.notarealfield }}"`
- **THEN** `load()` raises a `ContentLoadError` before returning the registry

---

### Requirement: CharacterConfig manifest may declare additional pronoun sets

The `CharacterConfig` manifest SHALL accept an optional `extra_pronoun_sets` list. Each entry SHALL be validated for required fields (`name`, `display_name`, all five pronoun form strings, `uses_plural_verbs`). A `name` that conflicts with a built-in set (`they_them`, `she_her`, `he_him`) SHALL be a content load error.

#### Scenario: Valid extra pronoun set in CharacterConfig loads without error

- **WHEN** `CharacterConfig` declares `extra_pronoun_sets: [{name: xe_xir, ...}]` with all required fields
- **THEN** `load()` completes without error

#### Scenario: Extra pronoun set with conflict name is a load error

- **WHEN** `CharacterConfig` declares `extra_pronoun_sets: [{name: she_her, ...}]`
- **THEN** `load()` raises a `ContentLoadError` identifying the conflict

---

### Requirement: Template validation errors are reported as ContentLoadErrors

`TemplateValidationError`s SHALL be collected and raised as a `ContentLoadError` with the same formatting and structure as schema and reference validation errors. The error message SHALL include the template identifier path (e.g. `adventure-name:step[0].text`) and a human-readable description of the failure.

#### Scenario: Multiple template errors are reported together

- **WHEN** a game package has three adventures each with one invalid template
- **THEN** `load()` raises a single `ContentLoadError` listing all three template errors

#### Scenario: oscilla validate reports template errors

- **WHEN** `oscilla validate --game mygame` is run on a package with template errors
- **THEN** the command exits with a non-zero code and prints each template error with its path

---

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
