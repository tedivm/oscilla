# Design: Validate Command Consolidation

## Context

`oscilla validate` and `oscilla content test` both load a game package and run validation, but they are split across two CLI locations with inconsistent options:

| Feature               | `validate`                    | `content test`                |
| --------------------- | ----------------------------- | ----------------------------- |
| Structural validation | ✓                             | ✓ (via `_resolve_registry`)   |
| Reference validation  | ✓ (inside `load_from_disk()`) | ✓ (inside `load_from_disk()`) |
| Semantic validation   | ✓ (default on)                | ✓ (always on)                 |
| Skip semantic         | `--no-semantic`               | ✗                             |
| Skip references       | ✗                             | ✗                             |
| Structured output     | ✗                             | `--format json\|yaml\|text`   |
| Summary               | ✓ (text only)                 | ✗                             |
| Stdin input           | ✗                             | ✗                             |

The loader pipeline in `oscilla/engine/loader.py` is already cleanly separated into phases:

```
scan(dir) / read stdin
    ↓
parse(paths) — YAML + Pydantic schema
    ↓
validate_references(manifests) — cross-manifest name refs
    ↓
build_effective_conditions(manifests) — template compilation
    ↓
template / derived stat validation
    ↓
ContentRegistry.build(manifests)     ← registry available here
    ↓
semantic validation (validate_semantic)
```

Adding a `load_from_text()` entry point that skips the disk-scan phase while reusing all downstream steps is the minimal change needed.

## Goals / Non-Goals

**Goals:**

- Extend `oscilla validate` with `--format`, `--no-references`, and `--stdin`
- Add `load_from_text(text, skip_references)` to `loader.py` as the stdin entry point
- Make `LoadError.file` and `LoadWarning.file` optional (`Path | None`) so errors from text input serialize cleanly
- Reduce `oscilla content test` to a thin backwards-compatible wrapper
- Structured output always includes `{"errors": [...], "warnings": [...], "summary": {...}}`

**Non-Goals:**

- Any changes to the validation logic itself (no new checks, no changed semantics)
- Markdown extraction or doc-example tooling (use external tooling to pipe YAML to stdin)
- Deprecation warnings on `content test` — it stays silently aliased forever

## Decisions

### D1: Rename `load()` → `load_from_disk()` and extract `_run_pipeline()`

**The existing function is called `load()`.** It currently lives in `oscilla/engine/loader.py` and is the sole disk-based entry point into the validation pipeline. This proposal renames it to `load_from_disk()` to make its role unambiguous alongside the new `load_from_text()` entry point, and simultaneously refactors it into a thin wrapper (see below).

**Callers that must be updated as part of the rename:**

| File                                               | Current import / call                                    |
| -------------------------------------------------- | -------------------------------------------------------- |
| `oscilla/engine/loader.py`                         | `load_games()` calls `load(subdir)` internally           |
| `oscilla/cli.py`                                   | `from oscilla.engine.loader import ..., load, ...`       |
| `oscilla/cli_content.py`                           | `from oscilla.engine.loader import ..., load, ...`       |
| `tests/test_cli_content.py`                        | `from oscilla.engine.loader import load`                 |
| `tests/engine/test_loader.py`                      | `from oscilla.engine.loader import ..., load, ...`       |
| `tests/engine/test_character_persistence.py`       | `from oscilla.engine.loader import load`                 |
| `tests/engine/test_skill_integration.py`           | `from oscilla.engine.loader import ..., load`            |
| `tests/engine/test_stat_effects.py`                | `from oscilla.engine.loader import ..., load`            |
| `tests/engine/test_template_integration.py`        | `from oscilla.engine.loader import ..., load`            |
| `tests/engine/test_combat_skills.py`               | `from oscilla.engine.loader import load` (local import)  |
| `tests/engine/test_adventure_ticks.py`             | `from oscilla.engine.loader import load` (local imports) |
| `tests/engine/test_item_enhancements.py`           | `from oscilla.engine.loader import ..., load`            |
| `tests/engine/test_derived_stat_validation.py`     | `from oscilla.engine.loader import ..., load`            |
| `tests/engine/test_loot_ref.py`                    | `from oscilla.engine.loader import ..., load`            |
| `tests/engine/test_quest_stage_condition.py`       | `from oscilla.engine.loader import ..., load`            |
| `tests/services/test_character_service.py`         | `from oscilla.engine.loader import load`                 |
| `tests/fixtures/content/trigger_tests/__init__.py` | `from oscilla.engine.loader import ..., load`            |
| `docs/dev/game-engine.md`                          | `from oscilla.engine.loader import load, ...`            |

**Extract `_run_pipeline()` — single implementation of the validation pipeline:**

**Decision:** Extract the entire post-parse validation pipeline from `load_from_disk()` into a private `_run_pipeline(manifests, parse_errors, skip_references)` function. `load_from_disk()` is then refactored to call `parse()` and hand off to `_run_pipeline`. `load_from_text()` is added as a trivially thin entry point that parses a string with a sentinel path and calls the same `_run_pipeline`. Neither entry point duplicates any pipeline logic.

**Alternatives considered:**

- Duplicate the pipeline in `load_from_text()` as originally designed — rejected. Two large functions that are 95% identical diverge over time, have separate bugs, and double the maintenance cost of every future pipeline extension.
- Write stdin to a named temp file and call `load_from_disk()` — rejected. It touches disk for no reason and creates non-obvious error message paths.
- Refactor `load_from_disk()` to accept a `text: str | None` parameter — rejected. Mixing two input modes into one function complicates the signature; two thin public entry points calling one shared private pipeline is cleaner.

**Refactored `load_from_disk()` (after):**

```python
# Before: load() is the existing function name, containing the full pipeline inline (~80 lines)

# After: renamed to load_from_disk() and refactored to a thin entry point
def load_from_disk(content_path: Path) -> Tuple[ContentRegistry, List[LoadWarning]]:
    """Orchestrate scan → parse → validate_references → build_effective_conditions → template validation.

    content_path may be either a directory (scanned recursively for .yaml/.yml
    files) or a path to a single YAML file (all documents in that file are used
    directly). Single-file mode is the path taken by compiled content archives.
    """
    if content_path.is_file():
        paths = [content_path]
    else:
        paths = scan(content_path)
    manifests, parse_errors = parse(paths)
    return _run_pipeline(manifests=manifests, parse_errors=parse_errors, skip_references=False)
```

**New public entry point `load_from_text()`:** (Note: the existing `load_from_disk()` above is also a thin entry point after this refactor.)

```python
def load_from_text(
    text: str,
    skip_references: bool = False,
) -> Tuple[ContentRegistry, List[LoadWarning]]:
    """Load and validate manifests from a YAML string rather than the filesystem.

    skip_references disables cross-manifest reference checks, useful when
    validating isolated manifest snippets that intentionally omit referenced
    content (e.g. documentation examples).

    Raises ContentLoadError on hard errors; returns (registry, warnings) on success.
    """
    manifests, parse_errors = _parse_text(text, source=Path("<stdin>"))
    return _run_pipeline(manifests=manifests, parse_errors=parse_errors, skip_references=skip_references)
```

**New private `_parse_text()` helper** — extracts YAML parsing from a string using the same per-document loop as `parse()`, so error format is identical:

```python
def _parse_text(
    text: str,
    source: Path,
) -> Tuple[List[ManifestEnvelope], List[LoadError]]:
    """Parse all YAML documents from a string.

    Uses source as the Path label in errors so messages are identifiable.
    Mirrors the per-path inner loop of parse() exactly.
    """
    manifests: List[ManifestEnvelope] = []
    errors: List[LoadError] = []

    try:
        docs = list(_yaml.load_all(text))
    except YAMLError as exc:
        errors.append(LoadError(file=source, message=f"YAML parse error: {exc}"))
        return manifests, errors

    for doc_index, raw in enumerate(docs):
        label = f"{source} [doc {doc_index + 1}]" if len(docs) > 1 else str(source)

        if not isinstance(raw, dict):
            errors.append(LoadError(file=source, message=f"{label}: Manifest must be a YAML mapping"))
            continue

        kind = raw.get("kind", "<missing>")
        model_cls = MANIFEST_REGISTRY.get(str(kind))
        if model_cls is None:
            errors.append(LoadError(file=source, message=f"{label}: Unknown kind: {kind!r}"))
            continue

        try:
            manifests.append(model_cls.model_validate(raw))
        except ValidationError as exc:
            for err in exc.errors():
                loc = " → ".join(str(x) for x in err["loc"])
                errors.append(LoadError(file=source, message=f"{label}: {loc}: {err['msg']}"))

    return manifests, errors
```

**New private `_run_pipeline()` — the shared pipeline body** (currently inlined in `load_from_disk()`):

```python
def _run_pipeline(
    manifests: List[ManifestEnvelope],
    parse_errors: List[LoadError],
    skip_references: bool,
) -> Tuple[ContentRegistry, List[LoadWarning]]:
    """Run the full post-parse validation and registry-build pipeline.

    Called by both load_from_disk() and load_from_text(). All validation logic lives
    here exactly once; adding a new pipeline step requires touching only
    this function.
    """
    from oscilla.engine.templates import GameTemplateEngine

    t0 = time.perf_counter()

    ref_errors = validate_references(manifests) if (manifests and not skip_references) else []
    manifests, compile_errors = build_effective_conditions(manifests)

    all_errors = parse_errors + ref_errors + compile_errors
    if all_errors:
        raise ContentLoadError(all_errors)

    char_config = next((m for m in manifests if m.kind == "CharacterConfig"), None)
    stat_names: List[str] = []
    if char_config is not None:
        cc = cast(CharacterConfigManifest, char_config)
        all_stats = cc.spec.public_stats + cc.spec.hidden_stats
        stat_names = [s.name for s in all_stats]

    game_manifest = next((m for m in manifests if m.kind == "Game"), None)
    has_ingame_time = False
    if game_manifest is not None:
        gm = cast(GameManifest, game_manifest)
        has_ingame_time = gm.spec.time is not None

    template_engine = GameTemplateEngine(stat_names=stat_names, has_ingame_time=has_ingame_time)

    derived_errors: List[LoadError] = []
    derived_eval_order: List[Any] = []
    if char_config is not None:
        cc = cast(CharacterConfigManifest, char_config)
        derived_eval_order = _build_derived_eval_order(cc, derived_errors)
        for stat_def in derived_eval_order:
            assert stat_def.derived is not None
            template_id = f"__derived_{stat_def.name}"
            try:
                template_engine.precompile_and_validate(
                    raw=stat_def.derived,
                    template_id=template_id,
                    context_type="adventure",
                )
            except Exception as exc:
                derived_errors.append(
                    LoadError(
                        file=Path("<CharacterConfig>"),
                        message=f"Derived stat {stat_def.name!r} formula failed validation: {exc}",
                    )
                )

    pronoun_errors = _validate_pronoun_set_names(manifests)
    template_errors = _validate_templates(manifests, template_engine)
    if pronoun_errors or template_errors or derived_errors:
        raise ContentLoadError(pronoun_errors + template_errors + derived_errors)

    registry = ContentRegistry.build(manifests, template_engine=template_engine)
    registry.derived_eval_order = derived_eval_order

    loot_ref_errors = _validate_loot_refs(registry)
    derived_write_errors: List[LoadError] = []
    _validate_no_derived_stat_writes(registry=registry, warnings=[], errors=derived_write_errors)
    all_post_errors = loot_ref_errors + derived_write_errors
    if all_post_errors:
        raise ContentLoadError(all_post_errors)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info("Content loaded in %.1f ms (%d manifests)", elapsed_ms, len(manifests))

    warnings: List[LoadWarning] = []
    warnings.extend(_validate_labels(manifests))
    warnings.extend(_validate_passive_effects(manifests))
    warnings.extend(_validate_trigger_adventures(registry))

    if registry.game is not None:
        registry.trigger_index = _build_trigger_index(registry.game)
        registry.stat_threshold_index = _build_stat_threshold_index(registry.game)

    return registry, warnings
```

The net result: `load_from_disk()` shrinks from ~80 lines to ~7. `load_from_text()` is 4 lines. The pipeline lives exactly once in `_run_pipeline()`. Any future extension to the pipeline requires touching only one function.

### D2: `LoadError.file` and `LoadWarning.file` become `Path | None`

**Decision:** Both dataclasses change `file: Path` to `file: Path | None`. The `__str__` methods handle `None` by omitting the file prefix (rendering just the message). The sentinel approach (`Path("<stdin>")`) used elsewhere stays valid; `None` is used only when there genuinely is no meaningful source path (not expected in practice but required for type correctness when constructing errors without a path).

**Before:**

```python
@dataclass
class LoadError:
    file: Path
    message: str

    def __str__(self) -> str:
        return f"{self.file}: {self.message}"


@dataclass
class LoadWarning:
    file: Path
    message: str
    suggestion: str = ""

    def __str__(self) -> str:
        base = f"{self.file}: {self.message}"
        return f"{base} — {self.suggestion}" if self.suggestion else base
```

**After:**

```python
@dataclass
class LoadError:
    file: Path | None
    message: str

    def __str__(self) -> str:
        return f"{self.file}: {self.message}" if self.file is not None else self.message


@dataclass
class LoadWarning:
    file: Path | None
    message: str
    suggestion: str = ""

    def __str__(self) -> str:
        base = f"{self.file}: {self.message}" if self.file is not None else self.message
        return f"{base} — {self.suggestion}" if self.suggestion else base
```

**Call sites:** All existing `LoadError(file=path, ...)` and `LoadWarning(file=path, ...)` calls are unchanged — `Path` is still valid for `Path | None`. No call sites require modification.

### D3: `validate` command refactored into two branches, both delegating to loader

**Decision:** The `validate` Typer command adds `--format`, `--no-references`, and an explicit `--stdin` flag. The body dispatches to `_validate_stdin()` or `_validate_games()` based on whether `--stdin` was passed, both of which call loader functions and feed results to a shared `_render_validate_output()` helper.

**Before:**

```python
@app.command(help="Validate all game packages and report any errors or warnings.")
def validate(
    game_name: Annotated[str | None, typer.Option("--game", "-g", help="Validate only this game package.")] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Treat warnings as errors and exit with code 1 if any are found."),
    ] = False,
    no_semantic: Annotated[
        bool,
        typer.Option(
            "--no-semantic",
            help="Skip semantic checks (undefined refs, circular chains, orphaned/unreachable content).",
        ),
    ] = False,
) -> None:
    """Load and validate all manifests in GAMES_PATH, then print a summary, warnings, or error list."""
    from rich.console import Console
    from oscilla.engine.loader import ContentLoadError, LoadWarning, load_from_disk, load_games

    _console = Console()
    all_pkg_warnings: Dict[str, List[LoadWarning]] = {}
    # ... (existing implementation)
```

**After:**

```python
@app.command(help="Validate game packages or manifest content and report errors and warnings.")
def validate(
    game_name: Annotated[
        str | None,
        typer.Option("--game", "-g", help="Validate only this game package (ignored when --stdin is used)."),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Treat warnings as errors and exit with code 1 if any are found."),
    ] = False,
    no_semantic: Annotated[
        bool,
        typer.Option(
            "--no-semantic",
            help="Skip semantic checks (undefined refs, circular chains, orphaned/unreachable content).",
        ),
    ] = False,
    no_references: Annotated[
        bool,
        typer.Option(
            "--no-references",
            help="Skip cross-manifest reference validation.",
        ),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-F", help="Output format: text | json | yaml."),
    ] = "text",
    stdin: Annotated[
        bool,
        typer.Option(
            "--stdin",
            help="Read YAML manifest content from stdin instead of from GAMES_PATH. Ignores --game.",
        ),
    ] = False,
) -> None:
    """Load and validate manifests from disk or stdin, then report errors and warnings."""
    if stdin:
        _validate_stdin(
            output_format=output_format,
            strict=strict,
            no_semantic=no_semantic,
            no_references=no_references,
        )
    else:
        _validate_games(
            game_name=game_name,
            output_format=output_format,
            strict=strict,
            no_semantic=no_semantic,
            no_references=no_references,
        )
```

````

**`_validate_stdin` helper:**

```python
def _validate_stdin(
    output_format: str,
    strict: bool,
    no_semantic: bool,
    no_references: bool,
) -> None:
    """Validate YAML manifests piped to stdin."""
    from oscilla.engine.loader import ContentLoadError, load_from_text
    from oscilla.engine.semantic_validator import validate_semantic

    _console = Console()

    text = sys.stdin.read()
    if not text.strip():
        _console.print("[bold red]✗ No content provided on stdin.[/bold red]", file=sys.stderr)
        raise SystemExit(1)

    try:
        registry, load_warnings = load_from_text(text, skip_references=no_references)
    except ContentLoadError as exc:
        error_list = [{"message": str(e)} for e in exc.errors]
        _render_validate_output(
            output_format=output_format,
            strict=strict,
            pkg_summaries={"<stdin>": {}},
            error_list=error_list,
            warning_list=[],
        )
        raise SystemExit(1)

    pkg_summaries: Dict[str, Dict[str, int]] = {"<stdin>": _registry_summary(registry)}
    warning_list: List[Dict[str, Any]] = [{"message": str(w)} for w in load_warnings]
    error_list = []

    if not no_semantic:
        for issue in validate_semantic(registry):
            if issue.severity == "error":
                error_list.append({"kind": issue.kind, "message": issue.message, "manifest": issue.manifest})
            else:
                warning_list.append({"kind": issue.kind, "message": issue.message, "manifest": issue.manifest})

    _render_validate_output(
        output_format=output_format,
        strict=strict,
        pkg_summaries=pkg_summaries,
        error_list=error_list,
        warning_list=warning_list,
    )
    if error_list or (strict and warning_list):
        raise SystemExit(1)
````

**`_validate_games` helper:**

```python
def _validate_games(
    game_name: str | None,
    output_format: str,
    strict: bool,
    no_semantic: bool,
    no_references: bool,
) -> None:
    """Validate game packages from disk."""
    from oscilla.engine.loader import ContentLoadError, LoadWarning, load_from_disk, load_games
    from oscilla.engine.semantic_validator import validate_semantic

    _console = Console()
    all_pkg_warnings: Dict[str, List[LoadWarning]] = {}

    if game_name is not None:
        game_path = settings.games_path / game_name
        if not game_path.is_dir():
            error_list = [{"message": f"Game package {game_name!r} not found in GAMES_PATH"}]
            _render_validate_output(output_format, strict, {}, error_list, [])
            raise SystemExit(1)
        try:
            registry, warnings = load_from_disk(game_path)
        except ContentLoadError as exc:
            error_list = [{"message": str(e)} for e in exc.errors]
            _render_validate_output(output_format, strict, {}, error_list, [])
            raise SystemExit(1)
        games = {game_name: registry}
        all_pkg_warnings[game_name] = warnings
    else:
        try:
            games, all_pkg_warnings = load_games(settings.games_path)
        except ContentLoadError as exc:
            error_list = [{"message": str(e)} for e in exc.errors]
            _render_validate_output(output_format, strict, {}, error_list, [])
            raise SystemExit(1)

    pkg_summaries: Dict[str, Dict[str, int]] = {}
    error_list = []
    warning_list: List[Dict[str, Any]] = []

    for pkg_name, registry in sorted(games.items()):
        pkg_summaries[pkg_name] = _registry_summary(registry)
        for w in all_pkg_warnings.get(pkg_name, []):
            warning_list.append({"message": str(w)})

    if not no_semantic:
        for pkg_name, registry in sorted(games.items()):
            for issue in validate_semantic(registry):
                entry: Dict[str, Any] = {
                    "kind": issue.kind,
                    "message": issue.message,
                    "manifest": issue.manifest,
                    "package": pkg_name,
                }
                if issue.severity == "error":
                    error_list.append(entry)
                else:
                    warning_list.append(entry)

    _render_validate_output(
        output_format=output_format,
        strict=strict,
        pkg_summaries=pkg_summaries,
        error_list=error_list,
        warning_list=warning_list,
    )
    if error_list or (strict and warning_list):
        raise SystemExit(1)
```

**Shared rendering helper:**

```python
def _render_validate_output(
    output_format: str,
    strict: bool,
    pkg_summaries: Dict[str, Dict[str, int]],
    error_list: List[Dict[str, Any]],
    warning_list: List[Dict[str, Any]],
) -> None:
    """Emit validation results in the requested format.

    For text output: prints per-package summary lines, then errors/warnings.
    For json/yaml: emits a single structured document to stdout.
    """
    _console = Console()

    if output_format != "text":
        _emit_structured_output(
            {"errors": error_list, "warnings": warning_list, "summary": pkg_summaries},
            output_format,
        )
        return

    # Text output: print one summary line per package.
    for pkg_name, counts in pkg_summaries.items():
        if counts:
            summary_str = ", ".join(f"{count} {kind}" for kind, count in counts.items())
            _console.print(f"[bold green]✓ {pkg_name}: {summary_str}[/bold green]")
        else:
            _console.print(f"[bold green]✓ {pkg_name}[/bold green]")

    for entry in warning_list:
        color = "bold red" if strict else "yellow"
        kind_tag = f"[{entry['kind']}] " if "kind" in entry else ""
        pkg_tag = f"[{entry['package']}] " if "package" in entry else ""
        _console.print(f"  [{color}]⚠[/{color}] {pkg_tag}{kind_tag}{entry['message']}")

    for entry in error_list:
        kind_tag = f"[{entry['kind']}] " if "kind" in entry else ""
        pkg_tag = f"[{entry['package']}] " if "package" in entry else ""
        _console.print(f"  [red]✗[/red] {pkg_tag}{kind_tag}{entry['message']}")

    if strict and warning_list:
        _console.print(f"\n[bold red]Strict mode: {len(warning_list)} warning(s) treated as errors.[/bold red]")


def _registry_summary(registry: "ContentRegistry") -> Dict[str, int]:
    """Build a non-zero count summary from a ContentRegistry."""
    counts = {
        "regions": len(registry.regions),
        "locations": len(registry.locations),
        "adventures": len(registry.adventures),
        "archetypes": len(registry.archetypes),
        "enemies": len(registry.enemies),
        "items": len(registry.items),
        "recipes": len(registry.recipes),
        "quests": len(registry.quests),
    }
    return {k: v for k, v in counts.items() if v > 0}


def _emit_structured_output(data: object, output_format: str) -> None:
    """Serialize data to stdout in the requested format."""
    if output_format == "json":
        typer.echo(json.dumps(data, indent=2, default=str))
    elif output_format == "yaml":
        from ruamel.yaml import YAML as _YAML
        _y = _YAML()
        _y.default_flow_style = False
        buf = io.StringIO()
        _y.dump(data, buf)
        typer.echo(buf.getvalue())
    else:
        Console(stderr=True).print(f"[red]Unknown format {output_format!r}. Valid: text, json, yaml.[/red]")
        raise SystemExit(1)
```

### D4: `content test` becomes a thin wrapper calling `validate` logic

**Decision:** `content test` is kept in `cli_content.py` but is reduced to a thin function that delegates to the shared helpers introduced in D3. It does not print its own output or run its own validation.

**Before:**

```python
@content_app.command("test")
def content_test(
    game: Annotated[Optional[str], typer.Option("--game", "-g")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors.")] = False,
    output_format: Annotated[str, typer.Option("--format", "-F", help="Output format: text | json | yaml.")] = "text",
) -> None:
    """Run semantic validation checks on the content package."""
    from oscilla.engine.semantic_validator import validate_semantic
    # ... (full implementation)
```

**After:**

```python
@content_app.command("test")
def content_test(
    game: Annotated[Optional[str], typer.Option("--game", "-g")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors.")] = False,
    output_format: Annotated[str, typer.Option("--format", "-F", help="Output format: text | json | yaml.")] = "text",
) -> None:
    """Alias for 'oscilla validate'. Runs full validation on the content package.

    Kept for backwards compatibility. Use 'oscilla validate' for the full
    feature set including --no-references and stdin support.
    """
    from oscilla.cli import _validate_games

    _validate_games(
        game_name=game,
        output_format=output_format,
        strict=strict,
        no_semantic=False,
        no_references=False,
    )
```

### D5: Structured output shape

**Decision:** All formats (both disk and stdin mode) emit the same document shape:

```json
{
  "errors": [
    {
      "kind": "undefined_ref",
      "message": "...",
      "manifest": "my-adventure",
      "package": "testlandia"
    }
  ],
  "warnings": [
    { "kind": "orphaned_location", "message": "...", "manifest": "my-location" }
  ],
  "summary": {
    "testlandia": {
      "regions": 3,
      "adventures": 12,
      "items": 8
    }
  }
}
```

In stdin mode, the summary key is `"<stdin>"`. Fields `"kind"`, `"manifest"`, and `"package"` are omitted on entries that don't have them (e.g., structural parse errors that only have a `"message"`).

### D6: `--game` is silently ignored when `--stdin` is used

**Decision:** If the user provides both `--game` and `--stdin`, `--game` is ignored without error or warning. The two flags target different input sources and `--stdin` takes precedence. Because the user has explicitly opted into stdin mode, silently ignoring the inapplicable flag is the least-surprising behavior.

## Edge Cases

| Scenario                                                             | Behavior                                                    |
| -------------------------------------------------------------------- | ----------------------------------------------------------- |
| stdin is empty or whitespace only                                    | Error: "No content provided on stdin." Exit 1               |
| stdin contains invalid YAML                                          | `ContentLoadError` via `_parse_text`; errors listed; Exit 1 |
| stdin contains unknown `kind:`                                       | Parse error: "Unknown kind: ..."; Exit 1                    |
| stdin references items not in the batch with `--no-references=False` | Reference validation error; Exit 1                          |
| stdin references items not in the batch with `--no-references`       | Passes reference phase; may still fail semantic phase       |
| `--no-semantic` + `--no-references` + valid schema                   | Schema-only pass; Exit 0                                    |
| `--format invalid_value`                                             | stderr: "Unknown format ..."; Exit 1                        |
| Multiple YAML docs in stdin via `---` separator                      | Parsed as batch; validated together                         |
| `--stdin` + `--game testlandia`                                      | `--game` silently ignored; stdin content validated          |

## Risks / Trade-offs

- **`content test` losing independent output logic**: The alias delegates to `_validate_games`, which now always prints the per-package summary. Pre-consolidation, `content test --format text` printed no summary. This is a deliberate behavior improvement — if any scripts depend on the old `content test` text output format exactly, they'll see the additional summary line. JSON/YAML output shape for `content test` is unchanged.

- **`--stdin` is explicit, not auto-detected**: stdin mode only activates when `--stdin` is passed. Authors can freely pipe data and still run disk-mode validation unless `--stdin` is present. This avoids surprising behavior in CI environments where stdin may be redirected but disk-based validation is still intended.

- **`_validate_games` and `_validate_stdin` are module-level functions in `cli.py`**: `content_test` in `cli_content.py` imports `_validate_games` from `oscilla.cli`. This is a cross-module private import. It is acceptable because `content_test` is explicitly a thin backwards-compat alias — not an independent feature.

## Migration Plan

1. Update `loader.py`: add `_parse_text()`, `load_from_text()`, update `LoadError`/`LoadWarning` field types
2. Update `cli.py`: refactor `validate`, add helpers
3. Update `cli_content.py`: replace `content_test` body with alias
4. Update tests
5. Update docs

No database migrations. No breaking changes to public Python API (loader functions are internal). The `content test` command signature is unchanged.

## Documentation Plan

| Document              | Audience            | Topics to cover                                                                                                                                             |
| --------------------- | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/dev/cli.md`     | Engine contributors | New `--format`, `--no-references` flags; stdin behavior; `content test` alias status; structured output shape                                               |
| `docs/authors/cli.md` | Content authors     | `oscilla validate` full flag reference; stdin usage examples (piping YAML snippets); when to use `--no-references` and `--no-semantic`; example JSON output |

Both documents already exist and need sections updated — no new files required.

## Testing Philosophy

Tests live in `tests/test_cli.py` (for `validate`) and `tests/test_cli_content.py` (for `content test` alias).

**What each tier verifies:**

| Tier                                           | What is tested                                                                               |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Unit: new validate flags in help               | `--format`, `--no-references` appear in `validate --help` output                             |
| Integration: text format (unchanged)           | `validate` still prints per-package summary lines for testlandia                             |
| Integration: JSON format (disk mode)           | `validate --format json` emits valid JSON with `errors`, `warnings`, `summary` keys          |
| Integration: YAML format (disk mode)           | `validate --format yaml` emits parseable YAML with same keys                                 |
| Integration: stdin valid batch                 | pipe two valid manifests; exit 0; summary includes both kinds                                |
| Integration: stdin invalid YAML                | pipe malformed YAML; exit 1; error message mentions parse error                              |
| Integration: stdin unknown kind                | pipe `kind: Nonexistent`; exit 1                                                             |
| Integration: stdin `--no-references`           | pipe adventure referencing unknown region; `--no-references` → exit 0; without flag → exit 1 |
| Integration: stdin `--no-semantic`             | pipe manifests with semantic issue; `--no-semantic` → exit 0                                 |
| Integration: stdin JSON output                 | pipe valid manifest with `--format json`; output includes `summary` with correct kind counts |
| Integration: `--game` + stdin                  | pipe valid manifest with `--game testlandia`; `--game` ignored; exit 0                       |
| Backwards compat: `content test` runs          | `content test` still exits 0 on valid testlandia content                                     |
| Backwards compat: `content test --format json` | produces JSON with same shape as `validate --format json`                                    |

**Complete test examples:**

```python
# All tests use this runner; TERM=dumb prevents Rich ANSI codes from
# breaking string assertions in CI (same pattern as existing test_cli.py).
runner = CliRunner(env={"TERM": "dumb"})

VALID_ITEM_YAML = """\
kind: Item
metadata:
  name: test-sword
spec:
  displayName: "Test Sword"
  description: "A sword for testing."
  category: weapon
  labels: []
"""

INVALID_YAML = "kind: [unclosed"

UNKNOWN_KIND_YAML = """\
kind: Nonexistent
metadata:
  name: test
spec: {}
"""


def test_validate_format_flag_in_help() -> None:
    result = runner.invoke(app, ["validate", "--help"])
    assert result.exit_code == 0
    assert "--format" in result.stdout
    assert "-F" in result.stdout


def test_validate_no_references_flag_in_help() -> None:
    result = runner.invoke(app, ["validate", "--help"])
    assert result.exit_code == 0
    assert "--no-references" in result.stdout


def test_validate_json_format_disk_mode() -> None:
    import json
    result = runner.invoke(app, ["validate", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "errors" in data
    assert "warnings" in data
    assert "summary" in data
    # summary should have at least one game package
    assert len(data["summary"]) >= 1


def test_validate_yaml_format_disk_mode() -> None:
    from ruamel.yaml import YAML
    result = runner.invoke(app, ["validate", "--format", "yaml"])
    assert result.exit_code == 0
    _y = YAML()
    data = _y.load(result.stdout)
    assert "errors" in data
    assert "summary" in data


def test_validate_stdin_valid_manifest() -> None:
    result = runner.invoke(app, ["validate", "--stdin", "--no-semantic", "--no-references"], input=VALID_ITEM_YAML)
    assert result.exit_code == 0


def test_validate_stdin_invalid_yaml() -> None:
    result = runner.invoke(app, ["validate", "--stdin"], input=INVALID_YAML)
    assert result.exit_code == 1
    assert "parse error" in result.stdout.lower() or "parse error" in result.stderr.lower()


def test_validate_stdin_unknown_kind() -> None:
    result = runner.invoke(app, ["validate", "--stdin"], input=UNKNOWN_KIND_YAML)
    assert result.exit_code == 1


def test_validate_stdin_json_output() -> None:
    import json
    result = runner.invoke(
        app,
        ["validate", "--stdin", "--format", "json", "--no-semantic", "--no-references"],
        input=VALID_ITEM_YAML,
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["errors"] == []
    # Summary for stdin mode uses "<stdin>" as the key
    assert "<stdin>" in data["summary"]
    assert data["summary"]["<stdin>"].get("items", 0) == 1


def test_validate_stdin_empty() -> None:
    result = runner.invoke(app, ["validate", "--stdin"], input="")
    assert result.exit_code == 1


def test_validate_game_flag_ignored_in_stdin_mode() -> None:
    # --game is silently ignored when --stdin is also provided
    result = runner.invoke(
        app,
        ["validate", "--stdin", "--game", "nonexistent-game", "--no-semantic", "--no-references"],
        input=VALID_ITEM_YAML,
    )
    assert result.exit_code == 0


def test_content_test_still_works_as_alias() -> None:
    from oscilla.cli_content import content_app
    content_runner = CliRunner(env={"TERM": "dumb"})
    result = content_runner.invoke(content_app, ["test"])
    assert result.exit_code == 0


def test_content_test_json_format() -> None:
    import json
    from oscilla.cli_content import content_app
    content_runner = CliRunner(env={"TERM": "dumb"})
    result = content_runner.invoke(content_app, ["test", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "errors" in data
    assert "warnings" in data
    assert "summary" in data
```

## Testlandia Integration

No testlandia content changes are required for this feature — it is a CLI tooling change, not a game engine change. The existing testlandia content serves as the integration test subject for disk-mode validation (`validate` and `content test`), and the new inline YAML fixtures in the test file serve as the subject for stdin-mode validation. Manual QA steps:

1. Run `uv run oscilla validate` — should succeed, show testlandia summary
2. Run `uv run oscilla validate --format json | python3 -m json.tool` — should emit valid JSON with `summary.testlandia`
3. Run `echo "kind: Item\nmetadata:\n  name: test\nspec:\n  category: weapon\n  labels: []" | uv run oscilla validate --stdin --no-references --no-semantic` — should exit 0
4. Run `uv run oscilla content test` — should behave identically to step 1
5. Run `uv run oscilla content test --format json` — should match shape from step 2

## Open Questions

None — all design decisions have been resolved through the exploration session prior to this document.
