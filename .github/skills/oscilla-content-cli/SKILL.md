---
name: oscilla-content-cli
description: "Use the Oscilla CLI to assist content authors writing YAML manifests. Use when: setting up JSON schema validation for YAML manifests, running validate or oscilla content test, inspecting manifest content with list/show, tracing adventure paths, graphing world structure, scaffolding new manifests with oscilla content create, debugging content errors, checking cross-references. Knows all oscilla content subcommands: schema, test, list, show, graph, trace, create. Also covers oscilla validate."
---

# Oscilla Content CLI

A workflow for using the `oscilla` CLI to assist content authors who write YAML manifests for game packages.

All commands run via `uv run oscilla ...`. Never invoke `oscilla` directly — it must go through `uv run` to pick up the virtual environment.

---

## Command Reference Overview

| Command                              | Purpose                                                             |
| ------------------------------------ | ------------------------------------------------------------------- |
| `oscilla validate`                   | Validate all game packages (schema + semantic checks)               |
| `oscilla content schema`             | Export JSON Schema for manifest kinds; configure VS Code validation |
| `oscilla content test`               | Run semantic checks on content packages                             |
| `oscilla content list <kind>`        | List all manifests of a given kind                                  |
| `oscilla content show <kind> <name>` | Inspect one manifest with cross-references                          |
| `oscilla content graph <type>`       | Visualize world/adventure/dependency graphs                         |
| `oscilla content trace <adventure>`  | Trace all execution paths through an adventure                      |
| `oscilla content create <kind>`      | Scaffold a new manifest file                                        |

---

## Manifest Kinds

Content authors write YAML manifests. The following `kind` values are used by the engine and CLI:

**Listable kinds (plural for `list`, singular for `show`/`create`)**:
`regions`, `locations`, `adventures`, `enemies`, `items`, `skills`, `quests`, `recipes`, `loot-tables`, `buffs`, `classes`, `games`, `character-configs`

Every manifest follows the standard structure:

```yaml
apiVersion: game/v1
kind: <Kind> # e.g. Adventure, Region, Item, Enemy
metadata:
  name: my-manifest # kebab-case identifier; used for all cross-references
spec: ... # kind-specific fields
```

---

## Known Quirks and Gotchas

### Names are `metadata.name`, not display names

All CLI commands that take a manifest name (`show`, `trace`, graph `adventure`, etc.) use the **`metadata.name`** value — the kebab-case identifier in the YAML, not the human-readable `displayName`. Always use `list` first if you're unsure:

```bash
# Find the correct name
uv run oscilla content list adventures --game myworld

# Then use the name column value, NOT the display name
uv run oscilla content trace my-adventure-name   # ✓ correct
uv run oscilla content trace "My Adventure Name"  # ✗ will fail
```

### Deprecation warnings appear before output

Some older content files trigger load-time deprecation warnings that print to stderr before the command output:

```
Adventure uses deprecated 'cooldown_adventures' — use 'cooldown_ticks' instead.
✓ testlandia: 11 regions, 54 locations ...
```

This is informational, not a failure. The actual command output follows immediately after. When helping authors, note the distinction and suggest updating deprecated fields when convenient.

### Orphaned adventure warnings are expected for utility content

Adventures that aren't wired to any location pool produce a warning:

```
⚠  Adventure 'full-reset' is not referenced in any location's pool
```

This is expected for utility adventures (dev tools, special resets) intentionally excluded from the normal world map. If it's not intentional, the author needs to add the adventure to a location's `adventure_pool`.

### Clean validate output

A fully passing validate run looks like:

```
✓ myworld: 3 regions, 8 locations, 12 adventures, 2 enemies, 5 items, 0 quests
```

---

## Validation Workflow

When a content author asks you to validate their content, or when you need to confirm content is correct after editing:

### 1. Run top-level validation

```bash
uv run oscilla validate
```

This is the primary validation command. It runs both schema validation and semantic checks (undefined references, circular chains, orphaned adventures) across all game packages.

**Common options:**

```bash
uv run oscilla validate --game myworld          # validate one game only
uv run oscilla validate --strict                # treat warnings as errors
uv run oscilla validate --no-semantic           # skip semantic checks (schema only)
```

### 2. Interpret output

- **Errors**: Schema violations or missing required fields. Must be fixed.
- **Warnings**: Semantic issues like orphaned adventures or unreachable paths. Advisory; use `--strict` to treat as errors.

### 3. For more detail: use `oscilla content test`

`oscilla content test` is the content-focused alias with identical semantics:

```bash
uv run oscilla content test --game myworld
uv run oscilla content test --game myworld --strict
uv run oscilla content test --game myworld --format json   # machine-readable output
```

---

## Schema Setup Workflow

When an author asks about YAML editor validation, schema generation, or VS Code YAML support:

### Option A — Configure VS Code automatically (recommended)

```bash
uv run oscilla content schema --output schemas/ --vscode
```

This writes one JSON Schema file per manifest kind into `schemas/` **and** updates `.vscode/settings.json` with `yaml-language-server` associations. After this, the YAML editor validates manifest fields inline.

### Option B — Write schemas without VS Code config

```bash
uv run oscilla content schema --output schemas/
```

### Option C — Per-file schema comment

Add a comment at the top of any YAML manifest file to enable schema validation for that file only:

```yaml
# yaml-language-server: $schema=./schemas/adventure.json
apiVersion: game/v1
kind: Adventure
...
```

### Option D — Inspect a single kind's schema

```bash
# Print adventure schema to stdout
uv run oscilla content schema adventure

# Print all schemas as one JSON object
uv run oscilla content schema
```

### Option E — Generate the combined schema file (project convention)

The project maintains `game_object_schema.json` at the repo root:

```bash
uv run oscilla content schema > game_object_schema.json
```

---

## Inspecting Content

### List all manifests of a kind

```bash
uv run oscilla content list adventures
uv run oscilla content list adventures --game myworld
uv run oscilla content list items --format json        # for scripting/parsing
```

The text table output truncates long values. If you need full field values or are processing output programmatically, always use `--format json`.

### Inspect a specific manifest

```bash
uv run oscilla content show adventure find-sword
uv run oscilla content show item rusty-sword --game myworld
uv run oscilla content show adventure find-sword --format json   # all fields + cross-refs
```

The `show` output renders the manifest as a Python object repr followed by a `Referenced by:` section listing everything that points to this manifest. Cross-references use `← kind:name` format:

```
Adventure: bless
  displayName: Blessing Set True
  ...

Referenced by:
  ← location:bless
```

This cross-reference section is the primary reason to use `show` over `list` — use it whenever an author asks "what uses this item/enemy/adventure?" or when debugging a missing-reference error.

---

## Tracing Adventures

Use `trace` to statically verify all execution paths through an adventure — no game session needed.

```bash
uv run oscilla content trace find-sword
uv run oscilla content trace find-sword --format json
```

**What the tracer checks:**

- Every branch from every `choice`, `combat`, and `stat_check` step
- Whether all paths end with an explicit `end_adventure` effect
- Which outcomes (`completed`, `defeated`, `fled`, custom) are reachable

The tracer does **not** evaluate conditions or simulate stat values — every branch is treated as reachable. Use it to catch missing endings and verify outcome coverage.

### Reading trace output

Each path is listed with an internal path ID, the outcome label, and the step sequence:

```
Tracing: binary-choice
Total steps (all branches): 3
Paths found: 2

── path-2  outcome: completed
   choice   Choose one option:
   narrative  'You chose option A.'
      → strength +1
      → end_adventure

── path-4  outcome: (no explicit end)
   choice   Choose one option:
   narrative  'You chose option B.'
      → gold +25
```

**Key signals:**

- `outcome: (no explicit end)` — this path is missing an `end_adventure` effect. The author must add one.
- `outcome: completed` / `outcome: defeated` / `outcome: fled` — explicitly set outcomes via `end_adventure` effects.
- Path IDs (`path-2`, `path-4`) are internal node IDs, not sequential path numbers — gaps are normal.
- Effects on each step appear as `→ effect_type value` indented under the step.

---

## Graphing World Structure

```bash
# World map: game → regions → locations → adventures
uv run oscilla content graph world
uv run oscilla content graph world --format mermaid
uv run oscilla content graph world --format dot --output world.dot

# Adventure flow diagram
uv run oscilla content graph adventure find-sword --format mermaid

# Dependency graph (items, loot tables, enemies, skills, buffs, recipes, quests)
uv run oscilla content graph deps
uv run oscilla content graph deps --focus item:rusty-sword   # "kind:name" format
uv run oscilla content graph deps --include-kinds item,enemy
```

The `--focus` flag uses `kind:name` syntax where `kind` is the singular lowercase kind slug (e.g., `item`, `enemy`, `skill`, `quest`). Use `list` to find the exact `metadata.name` value to use here.

---

## Scaffolding New Manifests

When an author needs a new YAML file for a manifest kind:

```bash
# Interactive (prompts for missing fields)
uv run oscilla content create adventure --game myworld

# Non-interactive (all fields as flags)
uv run oscilla content create region \
  --game myworld \
  --name dark-forest \
  --display-name "Dark Forest" \
  --description "A dense forest shrouded in shadow." \
  --no-interactive

# Location requires --region
uv run oscilla content create location \
  --game myworld \
  --name darkwood-clearing \
  --region dark-forest \
  --no-interactive

# Adventure requires --region and --location
uv run oscilla content create adventure \
  --game myworld \
  --name gather-herbs \
  --region dark-forest \
  --location darkwood-clearing \
  --no-interactive
```

**Supported kinds for `create`:** `region`, `location`, `adventure`, `enemy`, `item`, `quest`

The created file is a minimal but schema-valid stub. The author opens it and fills in the details.

---

## Common Author Workflows

### "Help me set up YAML validation in my editor"

1. Run `uv run oscilla content schema --output schemas/ --vscode`
2. Confirm `.vscode/settings.json` was updated
3. Optionally add `# yaml-language-server: $schema=./schemas/<kind>.json` to individual files

### "My content has errors — help me fix them"

1. Run `uv run oscilla validate --game <name>` and show the output
2. For each error, identify the manifest file and the failing field
3. Use `uv run oscilla content show <kind> <name>` to inspect cross-references if the error involves a missing reference
4. After edits, re-run `uv run oscilla validate` to confirm clean

### "I want to check my adventure has no dead ends"

1. Run `uv run oscilla content trace <adventure-name>`
2. Look for paths that don't end with `end_adventure`
3. Fix any missing endings, then re-trace to confirm

### "Show me how my world is connected"

1. `uv run oscilla content graph world` for a full ASCII map
2. `uv run oscilla content graph world --format mermaid` the Mermaid diagram format (renderable in GitHub/VS Code)
3. `uv run oscilla content graph deps --focus item:<name>` to trace a specific item's dependencies

### "I need to add a new adventure"

1. `uv run oscilla content create adventure --game <name>` (interactive) or supply all flags with `--no-interactive`
2. Open the generated file and fill in steps, outcomes, and rewards
3. Validate: `uv run oscilla validate --game <name>`
4. Trace: `uv run oscilla content trace <adventure-name>`

### "What fields are valid for this manifest kind?"

Use `schema` to get the JSON Schema for any manifest kind and inspect it, or point the author toward VS Code validation:

```bash
# Print the full JSON Schema for adventure manifests
uv run oscilla content schema adventure

# For interactive field-by-field validation while editing, set up VS Code
uv run oscilla content schema --output schemas/ --vscode
```

Once VS Code is configured, hover over any field in a manifest YAML to see valid values, required fields, and descriptions inline.

### "I added an adventure but it's not showing up in the game"

Adventures must be wired to a location's `adventure_pool` to appear in gameplay. Use `show` on the location to inspect its pool, then check whether your adventure is included:

```bash
# See what adventures a location currently has in its pool
uv run oscilla content show location <location-name>
```

Output will show the `adventures:` list including each entry's ref, weight, and any `requires` condition. If your adventure isn't listed, add it to the location's YAML under `spec.adventures`. If the location itself isn't listed under any region, check its `spec.region` field.

The `validate` orphaned-adventure warning is also useful here:

```
⚠  Adventure 'my-adventure' is not referenced in any location's pool
```

This warning fires precisely when an adventure exists but hasn't been wired to any location.

### "I renamed a manifest — how do I find all broken references?"

After changing a `metadata.name`, validation will surface broken cross-references immediately:

```bash
uv run oscilla validate --game <name>
```

Errors like `undefined adventure reference: old-name` point directly to the manifests that still use the old name. The `deps` graph can show you everything that referenced the old name before you rename:

```bash
# Before renaming, map all dependents
uv run oscilla content graph deps --focus adventure:old-name
uv run oscilla content graph deps --focus item:old-name
```

### "I want to visualize a single adventure's branching logic"

The `graph adventure` command generates a step-by-step flow diagram. Mermaid format is renderable in GitHub PRs, VS Code preview, and most documentation sites:

```bash
uv run oscilla content graph adventure <adventure-name> --format mermaid
```

Example output for a combat adventure:

```
flowchart LR
    start(["start"])
    step_1[/"combat: glass-dummy"/]
    step_2["narrative: 'You won.'"]
    step_3["narrative: 'You lost.'"]
    step_4["narrative: 'You fled.'"]

    step_1 -- on_win --> step_2
    step_1 -- on_defeat --> step_3
    step_1 -- on_flee --> step_4
    start --> step_1
```

Use this to review branching before writing — paste the Mermaid block into a GitHub comment or `docs/` file to share the design with collaborators.

### "What does this item/adventure affect? Show me everything connected to it"

Use `show` for the direct cross-references and `deps --focus` for the full dependency neighborhood:

```bash
# Direct references: what points to this manifest and what does it point to
uv run oscilla content show item battle-axe

# Full dependency neighborhood: all transitive connections
uv run oscilla content graph deps --focus item:battle-axe
```

`show` shows one hop in both directions. `deps --focus` shows the full subgraph — useful for understanding cascading effects before removing or renaming something.

### "I want to verify all my adventures are reachable"

Run validation and check for orphaned-adventure warnings:

```bash
uv run oscilla validate --game <name>
```

All warnings with `is not referenced in any location's pool` are adventures that exist in the content package but can't be reached by players. Review each one and either add it to a location pool or confirm it's intentionally a utility adventure (and document why in its `description`).

---

## Author Documentation

When the author asks about manifest structure and fields, refer them to or consult these docs:

| Topic                              | File                                 |
| ---------------------------------- | ------------------------------------ |
| Getting started / first game       | `docs/authors/getting-started.md`    |
| Conditions (all types)             | `docs/authors/conditions.md`         |
| Effects (all types)                | `docs/authors/effects.md`            |
| Templates (Jinja2 in text)         | `docs/authors/templates.md`          |
| Game configuration                 | `docs/authors/game-configuration.md` |
| World building (regions/locations) | `docs/authors/world-building.md`     |
| Adventures                         | `docs/authors/adventures.md`         |
| Items                              | `docs/authors/items.md`              |
| Enemies                            | `docs/authors/enemies.md`            |
| Skills & Buffs                     | `docs/authors/skills.md`             |
| Passive effects                    | `docs/authors/passive-effects.md`    |
| Quests                             | `docs/authors/quests.md`             |
| Recipes                            | `docs/authors/recipes.md`            |
| In-game time / calendar            | `docs/authors/ingame-time.md`        |
| CLI reference                      | `docs/authors/cli.md`                |
