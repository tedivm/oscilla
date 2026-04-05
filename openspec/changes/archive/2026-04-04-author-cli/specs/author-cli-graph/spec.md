# Author CLI — Graph

## ADDED Requirements

### Requirement: World graph command

The system SHALL provide an `oscilla content graph world` command that generates a hierarchical graph of regions, locations, and adventure pools. The command SHALL accept:

- `--game NAME` (optional): scope to a single game package.
- `--format FORMAT` (optional, default `ascii`): one of `dot`, `mermaid`, or `ascii`.
- `--output FILE` (optional): write the output to a file instead of stdout.

#### Scenario: ASCII world graph printed to stdout

- **WHEN** `oscilla content graph world --format ascii` is run
- **THEN** a tree-structured ASCII diagram of regions, locations, and adventure pool entries is printed to stdout

#### Scenario: DOT world graph output

- **WHEN** `oscilla content graph world --format dot` is run
- **THEN** a valid Graphviz DOT string is printed to stdout; the string begins with `digraph`

#### Scenario: Mermaid world graph output

- **WHEN** `oscilla content graph world --format mermaid` is run
- **THEN** a valid Mermaid flowchart string is printed to stdout; the string contains `flowchart LR`

#### Scenario: Output written to file

- **WHEN** `oscilla content graph world --format dot --output /tmp/world.dot` is run
- **THEN** the DOT string is written to `/tmp/world.dot` and a confirmation message is printed to stdout

---

### Requirement: Adventure flow graph command

The system SHALL provide an `oscilla content graph adventure NAME` command that generates a step-flow graph for a single adventure, showing all branches (choice options, combat outcomes, stat-check forks) as graph edges. The command SHALL accept:

- `NAME` (positional, required): adventure `metadata.name`.
- `--game NAME` (optional): scope to a single game package.
- `--format FORMAT` (optional, default `ascii`): one of `dot`, `mermaid`, or `ascii`.
- `--output FILE` (optional): write the output to a file.

#### Scenario: Adventure flow graph for branching adventure

- **WHEN** `oscilla content graph adventure trace-demo --format mermaid` is run
- **THEN** a Mermaid flowchart is produced with nodes for each step type and edges for each branch (both choice option paths visible)

#### Scenario: Missing adventure name exits with error

- **WHEN** `oscilla content graph adventure` is run without a name argument
- **THEN** the command exits with code 1 and prints a usage error

#### Scenario: Unknown adventure exits with error

- **WHEN** `oscilla content graph adventure no-such-adventure` is run
- **THEN** the command exits with code 1 and prints a not-found message

---

### Requirement: Dependency graph command

The system SHALL provide an `oscilla content graph deps` command that generates a cross-manifest dependency graph showing which manifests reference which. The command SHALL accept:

- `--game NAME` (optional): scope to a single game package.
- `--format FORMAT` (optional, default `ascii`): one of `dot`, `mermaid`, or `ascii`.
- `--focus NODE_ID` (optional): limit the graph to the focus node and its immediate neighbours; format is `kind:name` (e.g. `item:rusty-sword`).
- `--output FILE` (optional): write the output to a file.

#### Scenario: Full dependency graph

- **WHEN** `oscilla content graph deps` is run
- **THEN** a graph containing nodes for all referenced manifest kinds and edges for each cross-manifest reference is produced

#### Scenario: Focused dependency graph

- **WHEN** `oscilla content graph deps --focus adventure:goblin-fight` is run
- **THEN** only the `adventure:goblin-fight` node and its direct neighbours are present in the output

#### Scenario: DOT output for pydot

- **WHEN** `oscilla content graph deps --format dot` is run
- **THEN** a valid DOT string is produced using pydot; no Graphviz binary is invoked
