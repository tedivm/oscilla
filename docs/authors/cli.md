# Author CLI Reference

The `oscilla content` subapp provides tooling for content authors to inspect, validate, visualize, trace, and scaffold game manifests — all from the command line.

---

## Installation

These commands are available once you have installed Oscilla:

```bash
pip install oscilla         # or: uv add oscilla
```

Then run:

```bash
oscilla content --help
```

---

## Common Options

Most commands accept a `--game` option to target a specific game package. If your `GAMES_PATH` contains exactly one game, you can omit it.

```bash
oscilla content list adventures               # auto-detects the single game
oscilla content list adventures --game myworld   # explicit game selection
```

---

## `oscilla content list`

List all manifests of a given kind.

```bash
oscilla content list <kind> [--game NAME] [--format text|json|yaml]
```

**Arguments**

| Argument | Description                                                                                                                                                                    |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `kind`   | Plural manifest kind: `regions`, `locations`, `adventures`, `enemies`, `items`, `skills`, `quests`, `recipes`, `loot-tables`, `buffs`, `classes`, `games`, `character-configs` |

**Options**

| Option           | Default | Description                           |
| ---------------- | ------- | ------------------------------------- |
| `--game`, `-g`   | auto    | Game package name                     |
| `--format`, `-F` | `text`  | Output format: `text`, `json`, `yaml` |

**Examples**

```bash
# Print a table of all adventures
oscilla content list adventures

# Export adventure list as JSON for scripting
oscilla content list adventures --format json

# List items in a specific game package
oscilla content list items --game the-example-kingdom
```

---

## `oscilla content show`

Print a detailed description of one manifest, including cross-references to and from other manifests.

```bash
oscilla content show <kind> <name> [--game NAME] [--format text|json|yaml]
```

**Arguments**

| Argument | Description                                                          |
| -------- | -------------------------------------------------------------------- |
| `kind`   | Singular or plural manifest kind (e.g., `adventure` or `adventures`) |
| `name`   | Manifest name (`metadata.name`)                                      |

**Examples**

```bash
# Inspect a specific adventure
oscilla content show adventure find-sword

# Show as JSON (includes all spec fields and cross-refs)
oscilla content show adventure find-sword --format json
```

---

## `oscilla content graph`

Generate a graph visualization of game content relationships.

```bash
oscilla content graph <type> [name] [--game NAME] [--format dot|mermaid|ascii]
                     [--focus NODE_ID] [--include-kinds KINDS] [--exclude-kinds KINDS]
                     [--output FILE]
```

**Graph types**

| Type        | Description                                                                   |
| ----------- | ----------------------------------------------------------------------------- |
| `world`     | Full world map: game → regions → locations → adventures                       |
| `adventure` | Step-by-step flow graph of a single adventure                                 |
| `deps`      | Dependency graph: items, loot tables, enemies, skills, buffs, recipes, quests |

**Options**

| Option            | Default | Description                                                          |
| ----------------- | ------- | -------------------------------------------------------------------- |
| `--format`, `-f`  | `ascii` | Output format: `dot`, `mermaid`, `ascii`                             |
| `--focus`         | —       | For `deps`: center output on this node id, e.g. `item:rusty-sword`   |
| `--include-kinds` | —       | For `deps`: comma-separated kinds to include, e.g. `item,enemy`      |
| `--exclude-kinds` | —       | For `deps`: comma-separated kinds to exclude, e.g. `quest,milestone` |
| `--output`, `-o`  | stdout  | Write output to a file instead of printing it                        |

**Examples**

```bash
# Print an ASCII world map
oscilla content graph world

# Generate a Mermaid adventure flow diagram
oscilla content graph adventure find-sword --format mermaid

# Generate a DOT file for Graphviz
oscilla content graph world --format dot --output world.dot
dot -Tsvg world.dot -o world.svg

# Show only the dependency neighborhood around one item
oscilla content graph deps --focus item:iron-key --game myworld
```

---

## `oscilla content schema`

Export the JSON Schema for one or all manifest kinds.

```bash
oscilla content schema [kind] [--output PATH] [--vscode]
```

**Arguments**

| Argument          | Description                                              |
| ----------------- | -------------------------------------------------------- |
| `kind` (optional) | Kind slug (e.g., `adventure`). Omit to export all kinds. |

**Options**

| Option           | Description                                                                                                                                                    |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--output`, `-o` | Write to this file (single kind) or directory (all kinds). Prints to stdout otherwise.                                                                         |
| `--vscode`       | Write `.vscode/settings.json` with a `yaml-language-server` schema association. Defaults output to `.vscode/oscilla-schemas/` when `--output` is not provided. |

**Examples**

```bash
# Print the adventure schema to stdout
oscilla content schema adventure

# Write all schemas to a directory
oscilla content schema --output schemas/

# Configure VS Code editor validation with a single command (default output path)
oscilla content schema --vscode

# Configure VS Code with a custom output directory
oscilla content schema --output my-schemas/ --vscode
```

**What `--vscode` does**

Running `--vscode` writes two things:

1. All per-kind JSON schemas (e.g., `adventure.json`, `item.json`) plus a `manifest.json` umbrella schema that covers every manifest kind using a `kind`-discriminated union.
2. A `yaml.schemas` entry in `.vscode/settings.json` that associates `**/*.yaml` with `manifest.json`.

The resulting entry in `.vscode/settings.json` looks like this:

```json
{
  "yaml.schemas": {
    ".vscode/oscilla-schemas/manifest.json": "**/*.yaml"
  }
}
```

Because `manifest.json` uses an `if/then` guard on `apiVersion: oscilla/v1`, files that are not Oscilla manifests receive no spurious validation errors — the glob is safe for projects that contain non-Oscilla YAML files.

Once configured, your YAML editor validates manifest fields inline as you type and narrows validation to the correct schema branch based on the `kind` field. You can still add a `# yaml-language-server: $schema=./schemas/adventure.json` comment to a specific file to pin it to a single kind schema.

---

## `oscilla content test`

Run schema validation and semantic checks on one or all game packages.

```bash
oscilla content test [--game NAME] [--strict]
```

**Options**

| Option         | Description                                                               |
| -------------- | ------------------------------------------------------------------------- |
| `--game`, `-g` | Test only this game package. Defaults to all.                             |
| `--strict`     | Treat semantic warnings as errors (exits non-zero if any warnings found). |

Semantic checks include:

- Undefined adventure, enemy, item, and skill references
- Circular region parent chains
- Adventures not referenced in any location pool (warning)
- Unreachable adventures behind conditions that can never be met (warning)

**Examples**

```bash
# Validate all game packages
oscilla content test

# Validate with strict mode (warnings are errors)
oscilla content test --game myworld --strict
```

---

## `oscilla content trace`

Trace all execution paths through an adventure — without running the game or modifying any character state.

The tracer is a **static analysis tool**. It branches at every `choice`, `combat`, and `stat_check` step and records all possible paths from start to end. It does not evaluate conditions or simulate stat values — every branch is treated as reachable.

```bash
oscilla content trace <adventure-name> [--game NAME] [--format text|json|yaml]
```

**Examples**

```bash
# Trace an adventure and print all paths
oscilla content trace find-sword

# Export trace as JSON for tooling integration
oscilla content trace find-sword --format json
```

**Output includes**

- All paths from start to an `end_adventure` effect (or a note if none is found)
- The step sequence and recorded effects on each path
- The outcome name (`completed`, `defeated`, `fled`, or custom) at the end of each path

Use this to verify that:

- Every branch ends with an explicit `end_adventure` effect
- All intended outcomes (`completed`, `defeated`, `fled`) are reachable
- No path is accidentally missing an ending

---

## `oscilla content create`

Scaffold a new manifest YAML file at the conventional directory path.

```bash
oscilla content create <kind> [--game NAME] [--name NAME] [--display-name TEXT]
                       [--description TEXT] [--region NAME] [--location NAME]
                       [--parent NAME] [--no-interactive]
```

**Supported kinds**

`region`, `location`, `adventure`, `enemy`, `item`, `quest`

**Options**

| Option             | Description                                                               |
| ------------------ | ------------------------------------------------------------------------- |
| `--game`, `-g`     | Target game package                                                       |
| `--name`           | Manifest name (`metadata.name`), used as the directory/file name          |
| `--display-name`   | Human-readable display name                                               |
| `--description`    | Short description                                                         |
| `--region`         | Parent region name (required for `location` and `adventure`)              |
| `--location`       | Parent location name (required for `adventure`)                           |
| `--parent`         | Parent region name (optional for `region`, creates a nested sub-region)   |
| `--no-interactive` | Disable interactive prompts; all required options must be passed as flags |

**Examples**

```bash
# Interactive scaffolding (prompts for missing fields)
oscilla content create adventure --game myworld

# Non-interactive scaffolding with all fields supplied
oscilla content create region \
  --game myworld \
  --name dark-forest \
  --display-name "Dark Forest" \
  --description "A dense forest shrouded in shadow." \
  --no-interactive
```

The created file contains a minimal but schema-valid manifest. Open it in your editor and fill in the details.

---

## Testlandia — Developer QA Game

The `testlandia` game package (in `content/testlandia/`) is a developer test environment for manually exercising engine features. It contains a **Tooling Lab** region with adventures designed to produce predictable trace outputs for validating author CLI tools.

To run a trace on the demo adventure:

```bash
oscilla content trace trace-demo --game testlandia
```

The `trace-demo` adventure branches at a choice step, then again at a stat check — producing three traceable execution paths.
