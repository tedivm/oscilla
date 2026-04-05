# Author CLI — Create

## ADDED Requirements

### Requirement: Interactive manifest scaffolding

The system SHALL provide an `oscilla content create KIND` command that generates a minimal valid YAML manifest file at the conventional directory path for that kind. In interactive mode the command SHALL prompt for required fields. The command SHALL accept:

- `KIND` (positional, required): one of `region`, `location`, `adventure`, `enemy`, `item`, `quest`.
- `--game NAME` (optional): the game package to create content for; auto-selected if only one game exists.
- `--name TEXT` (optional): manifest `metadata.name`; prompted if omitted in interactive mode.
- `--display-name TEXT` (optional): spec `displayName`; prompted if omitted in interactive mode.
- `--description TEXT` (optional): spec `description`; defaults to empty string.
- `--parent TEXT` (optional): parent region name (for `region` kind only).
- `--region TEXT` (optional): region name (required for `location` and `adventure` kinds).
- `--location TEXT` (optional): location name (required for `adventure` kind).
- `--no-interactive` (flag, optional): skip all prompts; all required options must be provided or the command exits with code 1.

The scaffolded file SHALL be loadable by `loader.load()` without schema errors.

#### Scenario: Interactive region creation

- **WHEN** `oscilla content create region` is run with no extra options
- **THEN** the user is prompted for name, display name, description, and parent; a YAML file is created at `<games_path>/<game>/regions/<name>/<name>.yaml`

#### Scenario: Non-interactive adventure creation

- **WHEN** `oscilla content create adventure --name my-quest --display-name "My Quest" --region forest --location clearing --no-interactive` is run
- **THEN** a YAML file is created at `<games_path>/<game>/regions/forest/locations/clearing/adventures/my-quest.yaml` with no prompts

#### Scenario: Missing required option in --no-interactive exits with error

- **WHEN** `oscilla content create adventure --game testlandia --name test --no-interactive` is run without `--region`
- **THEN** the command exits with code 1 and prints an error indicating `--region` is required

#### Scenario: Scaffolded file passes schema validation

- **WHEN** a manifest is created via `oscilla content create` with valid inputs
- **THEN** running `oscilla validate --game <game>` after creation reports no new schema errors for the created manifest

#### Scenario: Output path confirmation

- **WHEN** `oscilla content create enemy --name cave-troll --display-name "Cave Troll" --no-interactive --game testlandia` is run
- **THEN** the command prints the full path of the created file and a reminder to run `oscilla validate`

#### Scenario: Unsupported kind exits with error

- **WHEN** `oscilla content create skill` is run
- **THEN** the command exits with code 1 and lists the supported kinds

---

### Requirement: Conventional file placement

The system SHALL place scaffolded manifest files at the documented canonical path for each kind. The canonical paths SHALL be:

| Kind | Path |
|------|------|
| `region` | `<games_path>/<game>/regions/<name>/<name>.yaml` |
| `location` | `<games_path>/<game>/regions/<region>/locations/<name>/<name>.yaml` |
| `adventure` | `<games_path>/<game>/regions/<region>/locations/<location>/adventures/<name>.yaml` |
| `enemy` | `<games_path>/<game>/enemies/<name>.yaml` |
| `item` | `<games_path>/<game>/items/<name>.yaml` |
| `quest` | `<games_path>/<game>/quests/<name>.yaml` |

All intermediate directories SHALL be created automatically.

#### Scenario: Directories created when they do not exist

- **WHEN** `oscilla content create location --name new-loc --display-name "New Location" --region new-region --no-interactive --game testlandia` is run and `regions/new-region/locations/new-loc/` does not exist
- **THEN** the full directory tree is created and the YAML file is written successfully
