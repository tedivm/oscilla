# Load Warnings

## Purpose

A non-fatal diagnostic tier in the content loader that identifies likely mistakes — things that are safe to run but almost certainly wrong. Warnings let the game load and play while surfacing actionable information to content authors via `oscilla validate` and AI tooling.

---

## Requirements

### Requirement: LoadWarning is a separate dataclass from LoadError

The content loader SHALL define a `LoadWarning` dataclass with:

- `file: Path` — the source file where the issue was found
- `message: str` — human-readable description of the issue
- `suggestion: str = ""` — optional fix hint, intended for developer tools and AI assistants

`LoadWarning` is distinct from `LoadError`. Warnings do not prevent the game from loading or running. Hard errors (schema violations, missing references, mutually exclusive fields) remain `LoadError` instances and cause `ContentLoadError` to be raised as before.

#### Scenario: LoadWarning is not an exception

- **WHEN** the content loader detects a condition that warrants a warning
- **THEN** a `LoadWarning` is accumulated and the load continues; no exception is raised

#### Scenario: LoadWarning carries a suggestion hint

- **WHEN** a `LoadWarning` is created for an undeclared item label
- **THEN** `warning.suggestion` contains a human-readable fix hint (non-empty string)

---

### Requirement: load() returns a tuple of registry and warnings

`load(content_dir: Path)` SHALL return `Tuple[ContentRegistry, List[LoadWarning]]`. The registry is the fully built content registry (identical behavior to before for non-warning content). The warnings list contains all `LoadWarning` instances collected during loading. An empty list indicates no warnings.

`load_games(library_root: Path)` SHALL return `Tuple[Dict[str, ContentRegistry], Dict[str, List[LoadWarning]]]`.

#### Scenario: Clean package returns empty warnings list

- **WHEN** `load()` is called on a valid content package with no undeclared labels or other warning conditions
- **THEN** the returned tuple is `(registry, [])` — the warnings list is empty

#### Scenario: Package with undeclared labels returns warnings

- **WHEN** `load()` is called on a package where an item uses an undeclared label
- **THEN** the returned tuple is `(registry, [warning])` — registry is valid and the warning is present

---

### Requirement: oscilla validate displays warnings in yellow

When `oscilla validate` calls `load()` and the returned warnings list is non-empty, the CLI SHALL print each warning in yellow with a `⚠` prefix. The exit code SHALL remain 0 unless `--strict` is passed.

#### Scenario: Warnings printed in yellow, exit code 0

- **WHEN** `oscilla validate` is run on a package with load warnings (but no errors)
- **THEN** warnings are printed in yellow, a warning count is shown, and the process exits with code 0

#### Scenario: Clean validation exits 0 with no warning output

- **WHEN** `oscilla validate` is run on a package with no errors and no warnings
- **THEN** only the success summary is printed and the process exits with code 0

---

### Requirement: --strict flag promotes warnings to errors

`oscilla validate` SHALL accept a `--strict` flag. When `--strict` is set, any `LoadWarning` returned from `load()` causes the CLI to print the warnings in red (identical formatting to errors) and exit with code 1.

#### Scenario: --strict with warnings exits 1

- **WHEN** `oscilla validate --strict` is run on a package that has load warnings
- **THEN** warnings are printed in red and the exit code is 1

#### Scenario: --strict with no warnings exits 0

- **WHEN** `oscilla validate --strict` is run on a package with no errors and no warnings
- **THEN** the exit code is 0

---

### Requirement: play command logs warnings at WARNING level

When a game is loaded via the play/start CLI path (not `validate`), any `LoadWarning` instances returned from `load()` SHALL be logged using `logger.warning()`. Gameplay SHALL proceed normally. Warnings are not shown to the player in the TUI.

#### Scenario: Play command logs warnings and continues

- **WHEN** the `play` command loads a game that has load warnings
- **THEN** each warning is logged at WARNING level and the game session starts normally

---

### Requirement: Undeclared item labels produce a LoadWarning

An item referencing a label not declared in `GameSpec.item_labels` SHALL produce a `LoadWarning` per item manifest. When a close match exists in `item_labels` (Levenshtein distance ≤ 2), the `suggestion` field SHALL mention the closest match. This is the only warning-generating condition in v1 of this system; additional warning conditions may be added in future changes.

#### Scenario: One undeclared label produces one warning per item

- **WHEN** two items each declare `labels: [undeclard]` and `undeclard` is not in `item_labels`
- **THEN** two `LoadWarning` instances are returned, one per item

#### Scenario: Close match in suggestion

- **WHEN** an item declares `labels: [legendery]` and `legendary` exists in `item_labels`
- **THEN** the warning's `suggestion` mentions `legendary` as the likely intended label
