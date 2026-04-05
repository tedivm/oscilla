## Why

Content authors currently have almost no CLI tooling beyond `oscilla validate`, which only reports schema errors and manifest counts. Authors discover semantic problems — broken references, orphaned content, unreachable adventures — at runtime while playing the game, often deep into a session. There is no way to inspect a loaded content package, visualize world structure or adventure flow, generate graphs of content relationships, or scaffold new manifests without writing YAML from scratch.

## What Changes

- **New `oscilla content` subcommand group** containing all author-facing tooling
- **`oscilla content list`** — tabular listing of all manifests of a given kind (regions, locations, adventures, enemies, items, skills, buffs, quests, recipes, classes, loot-tables), with optional `--format json|yaml` output
- **`oscilla content show`** — human-readable description of one manifest with its references and referenced-by relationships, with optional `--format json|yaml` output
- **`oscilla content graph`** — generates graph visualizations in DOT (via `pydot`), Mermaid, or ASCII formats for three graph types:
  - `world` — region/location/adventure-pool hierarchy
  - `adventure` — flowchart of steps, branches, and goto jumps within one adventure
  - `deps` — cross-manifest dependency graph (what is referenced by what), with optional `--focus` scoping and `--include-kinds`/`--exclude-kinds` filtering
- **`oscilla content schema`** — outputs JSON Schema for one or all manifest kinds, enabling editor autocomplete and external tooling; `--vscode` flag writes `.vscode/settings.json` associations
- **`oscilla content test`** — semantic validation beyond schema checks: undefined references, circular region parent chains, orphaned content (defined but never referenced), unreachable adventures; subsumes and extends the roadmap's "Content Validation CLI Improvements"
- **`oscilla content trace`** — headless adventure execution that traces all step transitions and effects without modifying any saved character state; reports branch coverage
- **`oscilla content create`** — interactive or non-interactive scaffold generation for all manifest kinds; places files in the conventional directory layout; `--no-interactive` flag for scripted use
- **Extend `oscilla validate`** with semantic checks running by default; `--no-semantic` flag skips them for faster schema-only runs
- **`--format text|json|yaml` output flag** on list, show, test, and trace commands for machine-readable output

## Capabilities

### New Capabilities

- `author-cli-inspect`: Content listing and description commands (`list`, `show`) exposing the loaded registry as queryable tables and structured descriptions
- `author-cli-graph`: Graph generation for world topology, adventure flow, and content dependency graphs in DOT, Mermaid, and ASCII formats
- `author-cli-schema`: JSON Schema export for all manifest kinds
- `author-cli-semantic-validation`: Semantic validation engine that catches undefined references, circular chains, orphaned content, and unreachable adventures
- `author-cli-trace`: Headless adventure execution tracer with branch coverage reporting
- `author-cli-create`: Interactive and non-interactive content scaffolding for all manifest kinds

### Modified Capabilities

- `cli-game-loop`: The top-level CLI gains a `content` subapp; the existing `validate` command runs semantic checks by default (opt-out with `--no-semantic`)

## Impact

- **New dependency**: `pydot` (for DOT graph generation)
- **New CLI module**: `oscilla/cli_content.py` (or `oscilla/cli/content.py`) registered as a Typer subapp in `oscilla/cli.py`
- **New engine module**: `oscilla/engine/graph.py` — pure graph construction functions that walk `ContentRegistry` and return a format-agnostic node+edge structure
- **New engine module**: `oscilla/engine/semantic_validator.py` — semantic validation checks beyond schema validation
- **New engine module**: `oscilla/engine/tracer.py` — headless pipeline runner that records step transitions without real effects or TUI
- **New engine module**: `oscilla/engine/schema_export.py` — generates JSON Schema from Pydantic models
- **Affected**: `oscilla/cli.py` gains a `content_app` subapp registration
- **Affected**: `oscilla/engine/loader.py` may need to expose additional cross-reference data for semantic validation
- **No breaking changes** — all new commands; existing `validate` behavior unchanged by default
- **Testlandia QA content**: New adventure `test-trace-adventure` exercising a multi-branch adventure (choice step → two outcomes with different effects) for use with `content trace`; new location `trace-lab` in a new region `tooling-lab` hosting it; this region and its content exist solely to demonstrate and manually QA the new CLI tooling
- **Future work**: Interactive step-by-step adventure building (create/edit for adventure steps) is explicitly out of scope for this change; a roadmap item must be added at archive time
