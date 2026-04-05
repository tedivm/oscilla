## 1. Dependencies and Module Skeleton

- [x] 1.1 Add `pydot>=4,<5` to production dependencies in `pyproject.toml` and run `make lock` to update `uv.lock`
- [x] 1.2 Create empty module stubs with module docstrings: `oscilla/engine/graph.py`, `oscilla/engine/graph_renderers.py`, `oscilla/engine/semantic_validator.py`, `oscilla/engine/tracer.py`, `oscilla/engine/schema_export.py`, `oscilla/engine/scaffolder.py`, `oscilla/engine/kinds.py`, `oscilla/cli_content.py`
- [x] 1.3 Register the `content_app` subapp in `oscilla/cli.py` (`app.add_typer(content_app, name="content")`) and verify `oscilla --help` shows `content`
- [x] 1.4 Add graph color settings fields (`graph_color_game`, `graph_color_region`, etc.) to `oscilla/conf/settings.py` using `pydantic.Field` with hex defaults and `OSCILLA_GRAPH_COLOR_*` env-var names

## 1b. Manifest Kind Registry (`oscilla/engine/kinds.py`)

- [x] 1b.1 Define `ManifestKind` as a frozen dataclass with fields: `slug: str`, `label: str`, `plural: str`, `model_class: type`
- [x] 1b.2 Define `ALL_KINDS: List[ManifestKind]` listing all 13 manifest kinds
- [x] 1b.3 Add convenience dicts `KIND_BY_SLUG` and `KIND_BY_LABEL` derived from `ALL_KINDS`
- [x] 1b.4 Verify all slugs match the existing `_KIND_MAP` in `cli_content.py` and `_MANIFEST_MODELS` in `schema_export.py`

- [x] 2.1 Implement the `GraphNode`, `GraphEdge`, and `ContentGraph` dataclasses with `add_node`, `add_edge`, and `has_node` helpers
- [x] 2.2 Implement `_condition_summary(condition)` and `_walk_all_steps(steps)` helpers
- [x] 2.3 Implement `_walk_all_effects(steps)` helper
- [x] 2.4 Implement `build_world_graph(registry) -> ContentGraph`
- [x] 2.5 Implement `build_adventure_graph(manifest, registry) -> ContentGraph`
- [x] 2.6 Implement `build_deps_graph(registry, focus=None, include_kinds=None, exclude_kinds=None) -> ContentGraph` including `_filter_to_neighborhood`
- [x] 2.7 Implement `build_manifest_xrefs(manifest, registry) -> Dict[str, list]`
- [x] 2.8 Write unit tests in `tests/engine/test_graph.py` covering world graph nodes/edges, adventure graph branching, deps graph focus filtering, and xrefs output

## 3. Graph Renderers (`oscilla/engine/graph_renderers.py`)

- [x] 3.1 Implement `_kind_colors() -> dict[str, str]` loading hex colors from settings; implement `render_dot(graph) -> str` using `pydot` with per-kind colors; verify output begins with `digraph`
- [x] 3.2 Implement `_sanitize_mermaid_label(text) -> str`; implement `render_mermaid(graph) -> str` using sanitized labels; verify output contains `flowchart LR`
- [x] 3.3 Implement `render_ascii(graph) -> str` tree renderer with box-drawing characters
- [x] 3.4 Implement `render(graph, fmt) -> str` dispatch function
- [x] 3.5 Write unit tests in `tests/engine/test_graph_renderers.py` asserting DOT/Mermaid/ASCII output structure from a fixed `ContentGraph`

## 4. Semantic Validator (`oscilla/engine/semantic_validator.py`)

- [x] 4.1 Implement the `SemanticIssue` dataclass with `kind`, `message`, `manifest`, and `severity` fields
- [x] 4.2 Implement `_check_undefined_adventure_refs(registry) -> List[SemanticIssue]`
- [x] 4.3 Implement `_check_undefined_enemy_refs(registry) -> List[SemanticIssue]`
- [x] 4.4 Implement `_check_undefined_item_refs(registry) -> List[SemanticIssue]`
- [x] 4.5 Implement `_check_undefined_skill_refs(registry) -> List[SemanticIssue]`
- [x] 4.6 Implement `_check_circular_region_parents(registry) -> List[SemanticIssue]`
- [x] 4.7 Implement `_check_orphaned_adventures(registry) -> List[SemanticIssue]` (severity: warning)
- [x] 4.8 Implement `_check_unreachable_adventures(registry) -> List[SemanticIssue]` (severity: warning)
- [x] 4.9 Implement `validate_semantic(registry) -> List[SemanticIssue]` aggregator
- [x] 4.10 Write unit tests in `tests/engine/test_semantic_validator.py` with dedicated test for each check function: clean registry, error case, warning case

## 5. Adventure Tracer (`oscilla/engine/tracer.py`)

- [x] 5.1 Implement the `TracedEffect`, `TracedNode`, `TracedPath`, and `TraceResult` dataclasses
- [x] 5.2 Implement `_record_node(path, step, branch)` helper
- [x] 5.3 Implement `_summarise_effects(effects) -> List[TracedEffect]` covering all effect types
- [x] 5.4 Implement `_trace_from_start(steps, label_map, new_path_id, result)` recursive walker with forking at choice/combat/stat_check nodes
- [x] 5.5 Implement the public `trace_adventure(manifest) -> TraceResult` entry point
- [x] 5.6 Verify tracer does not import or instantiate any database session, character state, or TUI component
- [x] 5.7 Write unit tests in `tests/engine/test_tracer.py`: linear adventure (1 path), two-choice adventure (2 paths), combat step (3 paths: win/defeat/flee), nested branches (correct path count), correct effect recording

## 6. Schema Export (`oscilla/engine/schema_export.py`)

- [x] 6.1 Build `_MANIFEST_MODELS` derived from `ALL_KINDS` (import from `oscilla.engine.kinds`); verify it maps all 13 kind slugs correctly
- [x] 6.2 Implement `export_schema(kind) -> Dict[str, Any]` with `$schema`, `$id`, and `title` additions
- [x] 6.3 Implement `export_all_schemas() -> Dict[str, Dict[str, Any]]` and `valid_kinds() -> list[str]`
- [x] 6.4 Write unit tests in `tests/engine/test_schema_export.py`: each known kind returns a dict with `$schema` and `properties`; unknown kind raises `ValueError`; all-schemas keys match `valid_kinds()`

## 7. Scaffolder (`oscilla/engine/scaffolder.py`)

- [x] 7.1 Implement `scaffold_region(games_path, game_name, name, display_name, description, parent) -> Path`
- [x] 7.2 Implement `scaffold_location(games_path, game_name, name, display_name, region, description) -> Path`
- [x] 7.3 Implement `scaffold_adventure(games_path, game_name, name, display_name, region, location, description) -> Path`
- [x] 7.4 Implement `scaffold_enemy(games_path, game_name, name, display_name, hp, attack, defense, xp_reward, description) -> Path`
- [x] 7.5 Implement `scaffold_item(games_path, game_name, name, display_name, category, description) -> Path`
- [x] 7.6 Implement `scaffold_quest(games_path, game_name, name, display_name, entry_stage, description) -> Path`
- [x] 7.7 Write unit tests in `tests/engine/test_scaffolder.py` using `tmp_path` fixture: each scaffold function creates a YAML file at the expected path; the YAML parses without error; directory auto-creation verified

## 8. Content CLI Commands (`oscilla/cli_content.py`)

- [x] 8.1 Implement `_resolve_registry(game_name) -> tuple[str, ContentRegistry]` helper
- [x] 8.2 Implement `content_list` command with Rich table and `--format text|json|yaml` output
- [x] 8.3 Implement `_manifest_summary(manifest, kind_label) -> Dict[str, str]` with kind-specific field extraction for all 11 kinds
- [x] 8.4 Implement `content_show` command with Rich display and `--format text|json|yaml` output
- [x] 8.5 Implement `content_graph` command dispatching to all three graph types and all three formats with `--output`, `--focus`, `--include-kinds`, and `--exclude-kinds` support for deps type
- [x] 8.6 Implement `content_schema` command with single-kind and all-kinds paths; directory output for all-kinds with `--output`; `.vscode/settings.json` associations with `--vscode`
- [x] 8.7 Implement `content_test` command with per-severity formatting, `--strict` mode, `--format text|json|yaml` output, and correct exit codes
- [x] 8.8 Implement `content_trace` command with Rich display and `--format text|json|yaml` output
- [x] 8.9 Implement `content_create` command with interactive prompts, `--no-interactive` mode, all six supported kinds, and output path confirmation

## 9. Validate Command Extension (`oscilla/cli.py`)

- [x] 9.1 Add `--no-semantic` flag to `oscilla validate` command signature (semantic checks run by default; `--no-semantic` opts out)
- [x] 9.2 Add post-summary semantic check block inside `validate()` that calls `validate_semantic(registry)` per game unless `--no-semantic` is set
- [x] 9.3 Verify `oscilla validate --no-semantic` behavior is unchanged from old baseline (run existing validate tests)

## 10. Integration Tests

- [x] 10.1 Create `tests/test_cli_content.py` with a `cli_runner` fixture and `testlandia_registry` fixture
- [x] 10.2 Test `content list adventures` returns table output containing adventure names
- [x] 10.3 Test `content list adventures --format json` returns valid JSON array
- [x] 10.4 Test `content show adventure trace-demo` exits with code 0
- [x] 10.5 Test `content graph world --format ascii` exits with code 0 and contains region name
- [x] 10.6 Test `content graph adventure trace-demo --format mermaid` exits with code 0 and contains `flowchart LR`
- [x] 10.7 Test `content graph deps --format dot` exits with code 0 and output contains `digraph`
- [x] 10.8 Test `content schema adventure` outputs valid JSON with `$schema` field
- [x] 10.9 Test `content test` exits with code 0 against clean testlandia content
- [x] 10.10 Test `content trace trace-demo` exits with code 0 and output contains path information
- [x] 10.11 Test `content trace trace-demo --format json` outputs valid JSON with `paths` array containing at least 3 elements
- [x] 10.12 Test `content create region` in `--no-interactive` mode creates a file at the expected path (use `tmp_path` fixture for `games_path`)
- [x] 10.13 Test `oscilla validate` (without `--no-semantic`) exits with code 0 against clean testlandia content

## 11. Testlandia QA Content

- [x] 11.1 Create `content/testlandia/regions/tooling-lab/tooling-lab.yaml` — Region manifest with `displayName: "Tooling Lab"` and no parent or unlock condition
- [x] 11.2 Create `content/testlandia/regions/tooling-lab/locations/trace-demo/trace-demo.yaml` — Location manifest in region `tooling-lab` with one adventure pool entry: `ref: trace-demo, weight: 1`
- [x] 11.3 Create `content/testlandia/regions/tooling-lab/locations/trace-demo/adventures/trace-demo.yaml` — Adventure manifest with: one narrative step, then a choice step with two options (Left path → stat_check fork → two end_adventure outcomes; Right path → passive step → narrative step → end_adventure); this structure exercises choice, stat_check, passive, and narrative step types in one adventure
- [x] 11.4 Run `oscilla validate --game testlandia` and confirm no new errors introduced by the three new manifest files
- [x] 11.5 Run `oscilla content trace trace-demo --game testlandia` and confirm at least 3 distinct paths are reported (Left→pass, Left→fail, Right)
- [x] 11.6 Run `oscilla content graph adventure trace-demo --game testlandia --format mermaid` and verify all step nodes appear in the output
- [x] 11.7 Run `oscilla content graph world --game testlandia --format ascii` and verify `Tooling Lab` region appears

## 12. Documentation

- [x] 12.1 Create `docs/authors/cli.md` covering all `oscilla content` commands with example output for each; include interactive and non-interactive `create` examples; include `yaml-language-server` directive example for `schema` output
- [x] 12.2 Add `cli.md` row to `docs/authors/README.md` table of contents under the "Building Your Game" section
- [x] 12.3 Update `docs/dev/cli.md` with a "Content Subapp" section documenting `cli_content.py` module structure, `_resolve_registry()` helper pattern, and the `--no-semantic` flag on `validate` (semantic runs by default)

## 13. Code Quality

- [x] 13.1 Run `make mypy_check` and fix all type errors in new modules
- [x] 13.2 Run `make ruff_check` and `make black_check`; fix any formatting issues with `make chores`
- [x] 13.3 Run `make pytest` and verify all tests pass with no regressions
- [x] 13.4 Run `make dapperdata_check` and verify all new YAML files in `content/testlandia/` are properly formatted; run `make dapperdata_fixes` if needed
