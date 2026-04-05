# Author CLI — Trace

## ADDED Requirements

### Requirement: Adventure trace command

The system SHALL provide an `oscilla content trace ADVENTURE_NAME` command that performs a static analysis of all execution paths through a named adventure. The tracer SHALL:

- Walk all steps in the adventure including nested branch steps.
- Treat ALL choice options, ALL combat outcome branches (on_win, on_defeat, on_flee), and ALL stat-check branches (on_pass, on_fail) as potentially reachable.
- Record effects encountered along each path without applying them to any character state.
- Report each distinct path with its sequence of steps, recorded effects, and final outcome.

The command SHALL accept:

- `ADVENTURE_NAME` (positional, required): the adventure's `metadata.name`.
- `--game NAME` (optional): scope to a single game package.
- `--format text|json|yaml` (option, optional): output the full trace result in the requested format.

The command SHALL NOT create a character, modify a database, or invoke any TUI component.

#### Scenario: Trace finds correct number of paths for two-option choice

- **WHEN** `oscilla content trace` is run on an adventure with a single two-option choice step
- **THEN** exactly two paths are reported (one per option)

#### Scenario: Trace captures effects along each path

- **WHEN** an adventure option applies an `xp_grant` effect
- **THEN** the traced path for that option contains an entry for `xp_grant` with the amount

#### Scenario: Trace reports path outcomes

- **WHEN** each path terminates in an `end_adventure` effect with a distinct outcome string
- **THEN** each traced path's `outcome` field reflects the corresponding outcome string

#### Scenario: Trace on adventure with no branches produces one path

- **WHEN** `oscilla content trace` is run on an adventure with only narrative steps
- **THEN** exactly one path is reported

#### Scenario: Unknown adventure exits with error

- **WHEN** `oscilla content trace no-such-adventure` is run
- **THEN** the command exits with code 1 and prints a not-found message

#### Scenario: JSON output is machine-readable

- **WHEN** `oscilla content trace trace-demo --format json` is run
- **THEN** the output is valid JSON containing at minimum `adventure_name`, `paths`, and `total_steps` fields; each path contains a `nodes` array and an `outcome` string

#### Scenario: No character state is created or modified

- **WHEN** `oscilla content trace` is run
- **THEN** no database writes occur and no `CharacterState` object is instantiated
