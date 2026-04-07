# Design: Multi-Manifest YAML Files

## Context

Content authors frequently want to group related manifests — item tiers, region sub-locations, enemy variants — in a single file, but today every manifest is required to be in its own YAML file. This creates unnecessary file proliferation and forces authors to fragment closely related content across dozens of files.

A secondary issue surfaced during exploration: the existing `oscilla content schema --vscode` command generates filename-based schema associations (e.g., `**/adventure.yaml`) that don't match the free-form filenames authors actually use (`character-creation.yaml`, `goblin-cave-items.yaml`, etc.). This means VS Code YAML schema validation silently does nothing for nearly all authored content. The multi-document feature creates the natural forcing function to fix this properly.

**Current state:**

| Area                      | Problem                                                                                                                                   |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Loader `parse()`          | Calls `_yaml.load()` — processes exactly one document per file                                                                            |
| Loader `load()`           | Accepts only a directory path; no single-file mode                                                                                        |
| `schema_export.py`        | Generates per-kind schemas only; no union schema covering all kinds                                                                       |
| `content schema --vscode` | Generates filename-based globs (`**/adventure.yaml`) that never match real content filenames; `--output` is required even with `--vscode` |
| `LoadError`               | Reports only file path; no document-index attribution for multi-doc files                                                                 |

---

## Goals / Non-Goals

**Goals:**

- Parse files containing multiple `---`-separated YAML documents; each document is validated as an independent manifest.
- Allow `load()` to accept either a directory or a path to a single YAML file.
- Generate a `manifest.json` umbrella schema that is a `kind`-discriminated `oneOf` union of all registered manifest kinds.
- Fix `content schema --vscode` to write a content-path glob association pointing at `manifest.json`, defaulting output to `.vscode/oscilla-schemas/`.
- Attribute load errors in multi-document files to `filename [doc N]` for precise debugging.

**Non-Goals:**

- Content compilation / archive format — single-file path support is added now to preserve optionality, but there is no `compile` command in this change.
- Validating or enforcing inter-document dependencies within a single file.
- Any constraint on which kinds may appear together in one file — authors can mix freely.
- Changes to the VS Code extension itself or how it handles multi-document files (the YAML extension already validates each `---` document independently).

---

## Decisions

### Decision 1 — `parse()` switches to `load_all()` with per-document error attribution

`ruamel.yaml`'s `YAML.load_all()` is a generator that yields one parsed object per `---`-separated document. Each document is processed identically to the current single-document flow: kind lookup, model validation, error accumulation.

Error messages for documents beyond the first include a document index suffix so authors can locate the broken document without counting `---` dividers manually.

**Before:**

```python
def parse(paths: List[Path]) -> Tuple[List[ManifestEnvelope], List[LoadError]]:
    """Parse YAML files and validate against Pydantic models. Accumulates errors."""
    manifests: List[ManifestEnvelope] = []
    errors: List[LoadError] = []

    for path in paths:
        try:
            raw = _yaml.load(path.read_text(encoding="utf-8"))
        except YAMLError as exc:
            errors.append(LoadError(file=path, message=f"YAML parse error: {exc}"))
            continue
        except OSError as exc:
            errors.append(LoadError(file=path, message=f"File read error: {exc}"))
            continue

        if not isinstance(raw, dict):
            errors.append(LoadError(file=path, message="Manifest must be a YAML mapping"))
            continue

        kind = raw.get("kind", "<missing>")
        model_cls = MANIFEST_REGISTRY.get(str(kind))
        if model_cls is None:
            errors.append(LoadError(file=path, message=f"Unknown kind: {kind!r}"))
            continue

        try:
            manifests.append(model_cls.model_validate(raw))
        except ValidationError as exc:
            for err in exc.errors():
                loc = " → ".join(str(x) for x in err["loc"])
                errors.append(LoadError(file=path, message=f"{loc}: {err['msg']}"))

    return manifests, errors
```

**After:**

```python
def parse(paths: List[Path]) -> Tuple[List[ManifestEnvelope], List[LoadError]]:
    """Parse YAML files and validate against Pydantic models. Accumulates errors.

    Each path may contain multiple YAML documents separated by '---' dividers.
    Every document is validated independently. Errors include a document index
    suffix (e.g. '[doc 2]') for files with more than one document.
    """
    manifests: List[ManifestEnvelope] = []
    errors: List[LoadError] = []

    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(LoadError(file=path, message=f"File read error: {exc}"))
            continue

        try:
            # load_all() is a generator; wrap in list to catch parse errors eagerly
            # so that a malformed document in the middle of a file is attributed correctly.
            docs = list(_yaml.load_all(text))
        except YAMLError as exc:
            errors.append(LoadError(file=path, message=f"YAML parse error: {exc}"))
            continue

        for doc_index, raw in enumerate(docs):
            # Suffix added only when there is more than one document to keep
            # single-document error messages identical to the existing format.
            label = f"{path} [doc {doc_index + 1}]" if len(docs) > 1 else str(path)

            if not isinstance(raw, dict):
                errors.append(LoadError(file=path, message=f"{label}: Manifest must be a YAML mapping"))
                continue

            kind = raw.get("kind", "<missing>")
            model_cls = MANIFEST_REGISTRY.get(str(kind))
            if model_cls is None:
                errors.append(LoadError(file=path, message=f"{label}: Unknown kind: {kind!r}"))
                continue

            try:
                manifests.append(model_cls.model_validate(raw))
            except ValidationError as exc:
                for err in exc.errors():
                    loc = " → ".join(str(x) for x in err["loc"])
                    errors.append(LoadError(file=path, message=f"{label}: {loc}: {err['msg']}"))

    return manifests, errors
```

**Edge cases:**

| Case                                                                 | Handling                                                                                                                          |
| -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| File with a single document                                          | `len(docs) == 1` → label is plain path; error messages unchanged from current format                                              |
| File with a `---` but only one non-empty document (trailing divider) | `load_all()` yields one document; behaves as single-document                                                                      |
| File with an entirely empty document between `---` dividers          | `ruamel.yaml` yields `None` for an empty document; the `isinstance(raw, dict)` check rejects it with a clear error                |
| YAML parse error mid-file                                            | `list(_yaml.load_all(text))` raises, caught as a single file-level error; document-level attribution is not possible in this case |

---

### Decision 2 — `load()` accepts directory or single file

When `content_path` is a file, it is placed in a one-element list and passed directly to `parse()`. The entire downstream pipeline (validation, registry build, template validation) is unchanged.

This preserves full optionality for a future `compile` command that would produce a single `.yaml` archive of a content package. Such a file, passed directly to `load()`, would process all documents in sequence — no new logic required.

**Before:**

```python
def load(content_dir: Path) -> Tuple[ContentRegistry, List[LoadWarning]]:
    """Orchestrate scan → parse → validate_references → build_effective_conditions → template validation."""
    from oscilla.engine.templates import GameTemplateEngine

    t0 = time.perf_counter()
    paths = scan(content_dir)
    manifests, parse_errors = parse(paths)
    ...
```

**After:**

```python
def load(content_path: Path) -> Tuple[ContentRegistry, List[LoadWarning]]:
    """Orchestrate scan → parse → validate_references → build_effective_conditions → template validation.

    content_path may be either a directory (scanned recursively for .yaml/.yml files)
    or a path to a single YAML file (all documents in that file are used directly).
    Single-file mode is the path taken by compiled content archives.
    """
    from oscilla.engine.templates import GameTemplateEngine

    t0 = time.perf_counter()
    # Single-file mode: treat the file itself as the complete manifest list.
    if content_path.is_file():
        paths = [content_path]
    else:
        paths = scan(content_path)
    manifests, parse_errors = parse(paths)
    ...
```

**Call sites:** Every call to `load()` passes a directory today, so this change is backward-compatible. The parameter is renamed from `content_dir` to `content_path` — callers using keyword argument `content_dir=...` will get a `TypeError` at runtime. A search confirms no internal callers use it as a keyword argument; external consumers of the library using keyword arguments will need to update.

---

### Decision 3 — Umbrella union schema in `schema_export.py`

The umbrella schema is a JSON Schema `oneOf` array over all registered manifest kind models. Pydantic's discriminated union support generates a clean schema with a `discriminator` annotation on the `kind` field, which the yaml-language-server uses to narrow validation to the correct branch while the author types.

The schema is wrapped in an `if/then` guard on `apiVersion: oscilla/v1`. This makes the schema a strict no-op for any YAML file that does not carry the Oscilla API version header, which in turn makes the `**/*.yaml` project-wide glob safe — non-Oscilla files in the workspace receive no spurious validation errors.

The existing `export_schema()` and `export_all_schemas()` functions are unchanged. The new `export_union_schema()` function builds the union at call time, so new manifest kinds added to `kinds.py` are automatically included.

**New function added to `oscilla/engine/schema_export.py`:**

```python
def export_union_schema() -> Dict[str, Any]:
    """Return a JSON Schema that accepts any valid Oscilla manifest.

    The schema is a 'kind'-discriminated oneOf union of all registered manifest
    kind models wrapped in an if/then guard on apiVersion: oscilla/v1. The guard
    makes the schema a no-op for non-Oscilla YAML files, enabling the **/*.yaml
    project-wide glob without generating spurious validation errors in files that
    don't belong to Oscilla.

    The yaml-language-server uses the kind discriminator to narrow validation to
    the correct model branch while the author is editing.
    """
    from typing import Annotated, Union

    from pydantic import Field, RootModel

    from oscilla.engine.models.adventure import AdventureManifest
    from oscilla.engine.models.buff import BuffManifest
    from oscilla.engine.models.character_config import CharacterConfigManifest
    from oscilla.engine.models.enemy import EnemyManifest
    from oscilla.engine.models.game import GameManifest
    from oscilla.engine.models.game_class import ClassManifest
    from oscilla.engine.models.item import ItemManifest
    from oscilla.engine.models.location import LocationManifest
    from oscilla.engine.models.loot_table import LootTableManifest
    from oscilla.engine.models.quest import QuestManifest
    from oscilla.engine.models.recipe import RecipeManifest
    from oscilla.engine.models.region import RegionManifest
    from oscilla.engine.models.skill import SkillManifest

    # The discriminator field is 'kind'; every manifest model uses Literal["<KindName>"]
    # for its kind field, so Pydantic can generate a proper discriminated oneOf.
    AnyManifest = RootModel[
        Annotated[
            Union[
                AdventureManifest,
                BuffManifest,
                CharacterConfigManifest,
                ClassManifest,
                EnemyManifest,
                GameManifest,
                ItemManifest,
                LocationManifest,
                LootTableManifest,
                QuestManifest,
                RecipeManifest,
                RegionManifest,
                SkillManifest,
            ],
            Field(discriminator="kind"),
        ]
    ]

    inner_schema: Dict[str, Any] = dict(AnyManifest.model_json_schema())

    # Wrap in if/then so the schema is a no-op for files that lack apiVersion: oscilla/v1.
    # $defs must stay at the top level so $ref paths resolve correctly.
    then_body = {k: v for k, v in inner_schema.items() if k != "$defs"}
    schema: Dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://oscilla.tedivm.com/schemas/manifest.json",
        "title": "Oscilla Manifest",
        "if": {
            "properties": {"apiVersion": {"const": "oscilla/v1"}},
            "required": ["apiVersion"],
        },
        "then": then_body,
    }
    if "$defs" in inner_schema:
        schema["$defs"] = inner_schema["$defs"]
    return schema
```

**Note on `Union` ordering:** Pydantic serializes `$defs` in the order the union members are listed. Alphabetical order is used here for determinism. The discriminator means ordering has no effect on runtime validation behavior.

**Why `if/then` instead of a content-path glob:** A content-path glob (e.g. `./content/**/*.yaml`) would break any project that stores Oscilla content outside `content/`, and would miss content in monorepo sub-directories. The `apiVersion: oscilla/v1` guard is a semantic contract that travels with each document and works regardless of where the files live on disk.

---

### Decision 4 — `content schema --vscode` CLI changes

Three changes to the existing command:

1. `--vscode` no longer requires `--output`; when `--vscode` is passed without `--output`, the output directory defaults to `.vscode/oscilla-schemas/`.
2. The generated `manifest.json` union schema is written alongside the per-kind schemas.
3. The association written to `.vscode/settings.json` uses a project-wide glob (`**/*.yaml`) pointing at `manifest.json` instead of the previous per-filename approach. The `if/then` guard in `manifest.json` ensures this is safe for projects that contain non-Oscilla YAML files.

**Before (`_write_vscode_schema_associations`):**

```python
def _write_vscode_schema_associations(
    schema_dir: Path,
    schemas: dict,
) -> None:
    """Update .vscode/settings.json with yaml-language-server schema associations."""
    import json as _json

    settings_path = Path(".vscode") / "settings.json"
    settings_path.parent.mkdir(exist_ok=True)
    try:
        existing: dict = _json.loads(settings_path.read_text()) if settings_path.exists() else {}
    except Exception:
        existing = {}
    associations = {f"**/{k}.yaml": str(schema_dir / f"{k}.json") for k in sorted(schemas)}
    existing.setdefault("yaml.schemas", {}).update(associations)
    settings_path.write_text(_json.dumps(existing, indent=2))
    _console.print(f"[green]Updated {settings_path} with {len(associations)} schema associations.[/green]")
```

**After:**

```python
def _write_vscode_schema_associations(
    schema_dir: Path,
) -> None:
    """Update .vscode/settings.json with a content-path glob pointing at manifest.json.

    A single glob covers all content files regardless of their filename, and works
    correctly with multi-document YAML files. The yaml-language-server validates
    each document independently against the discriminated union schema.

    Creates .vscode/settings.json if it does not exist. Merges into any existing
    yaml.schemas dict so that other schema associations are preserved.
    """
    import json as _json

    settings_path = Path(".vscode") / "settings.json"
    settings_path.parent.mkdir(exist_ok=True)
    try:
        existing: dict = _json.loads(settings_path.read_text()) if settings_path.exists() else {}
    except Exception:
        existing = {}
    # Use a relative path so the association is portable across machines.
    manifest_schema_path = str(schema_dir / "manifest.json")
    # **/*.yaml is safe because manifest.json uses an if/then guard on
    # apiVersion: oscilla/v1 — non-Oscilla files receive no validation.
    existing.setdefault("yaml.schemas", {})[manifest_schema_path] = "**/*.yaml"
    settings_path.write_text(_json.dumps(existing, indent=2))
    _console.print(f"[green]Updated {settings_path} with content glob → {manifest_schema_path}[/green]")
```

**Updated `content_schema` command signature** (the `--vscode` / `--output` coupling is relaxed):

```python
@content_app.command("schema")
def content_schema(
    kind: Annotated[
        Optional[str],
        typer.Argument(help="Manifest kind slug. Omit to export all kinds."),
    ] = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Write to file (or directory for all kinds)."),
    ] = None,
    vscode: Annotated[
        bool,
        typer.Option(
            "--vscode",
            help=(
                "Write .vscode/settings.json yaml-language-server schema associations. "
                "Defaults output to .vscode/oscilla-schemas/ when --output is not provided."
            ),
        ),
    ] = False,
) -> None:
    """Export JSON Schema for Oscilla manifest kinds.

    With no KIND argument, all schemas are printed as a single JSON object keyed by kind.
    With --output and no KIND, writes one file per kind into the specified directory.
    With --vscode, also writes manifest.json and updates .vscode/settings.json with a
    content-path glob association. Output defaults to .vscode/oscilla-schemas/.
    """
    from oscilla.engine.schema_export import export_all_schemas, export_schema, export_union_schema

    # Resolve effective output: --vscode has a default; without --vscode, --output is optional.
    effective_output = output or (".vscode/oscilla-schemas" if vscode else None)

    if kind is not None:
        # Single-kind export: --vscode is not applicable here.
        try:
            schema = export_schema(kind)
        except ValueError as exc:
            _err_console.print(f"[red]{exc}[/red]")
            raise SystemExit(1)
        result = json.dumps(schema, indent=2)
        if effective_output:
            Path(effective_output).write_text(result)
            _console.print(f"[green]Written to {effective_output}[/green]")
        else:
            typer.echo(result)
        return

    # All schemas
    all_schemas = export_all_schemas()
    if effective_output:
        out_dir = Path(effective_output)
        out_dir.mkdir(parents=True, exist_ok=True)
        for k, schema in all_schemas.items():
            (out_dir / f"{k}.json").write_text(json.dumps(schema, indent=2))
        # Always write the union schema alongside per-kind schemas.
        (out_dir / "manifest.json").write_text(json.dumps(export_union_schema(), indent=2))
        _console.print(f"[green]Wrote {len(all_schemas) + 1} schema files to {out_dir}/[/green]")
        if vscode:
            _write_vscode_schema_associations(out_dir)
    else:
        typer.echo(json.dumps(all_schemas, indent=2))
```

**Edge cases:**

| Case                                               | Handling                                                                                            |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `--vscode` with no `--output`                      | Defaults to `.vscode/oscilla-schemas/`; directory created if absent                                 |
| `--output` without `--vscode`                      | Writes per-kind schemas and `manifest.json`; does not touch `settings.json`                         |
| `--vscode` with a KIND argument                    | KIND + `--output` writes a single file; `--vscode` is silently ignored (no union schema applicable) |
| `settings.json` contains other `yaml.schemas` keys | Merged; existing keys are preserved                                                                 |
| `settings.json` is malformed JSON                  | Caught, treated as empty dict, overwritten cleanly                                                  |

---

### Decision 5 — Rename `apiVersion: game/v1` → `apiVersion: oscilla/v1` (BREAKING)

**Problem:** The value `game/v1` implied the version string belonged to a specific game, not to the Oscilla library itself. This caused confusion for library consumers writing multi-game content packages and misrepresented the provenance of the API contract.

**Decision:** Rename the literal value to `oscilla/v1` everywhere — the model, all content YAML, all tests, and all documentation. This is a breaking change for any existing content packages that were pinned to `apiVersion: game/v1`.

**Impact surface:**

| Location                        | Change                                                                          |
| ------------------------------- | ------------------------------------------------------------------------------- |
| `oscilla/engine/models/base.py` | `Literal["game/v1"]` → `Literal["oscilla/v1"]` on `ManifestEnvelope.apiVersion` |
| `oscilla/engine/scaffolder.py`  | 6 template dicts: `"apiVersion": "game/v1"` → `"oscilla/v1"`                    |
| `content/testlandia/**/*.yaml`  | ~282 YAML files updated                                                         |
| `tests/**/*.py`                 | ~100 `apiVersion=` keyword arguments updated                                    |
| `docs/**/*.md`                  | All code blocks and examples updated                                            |
| `openspec/`                     | All specs and proposal examples updated                                         |

**Migration path for existing content authors:** A one-line `sed` replacement is sufficient:

```bash
find . -name "*.yaml" -exec sed -i '' 's/apiVersion: game\/v1/apiVersion: oscilla\/v1/g' {} +
```

**Status:** This rename was executed as part of the initial change branch and all 922 tests pass with the new value.

---

## Documentation Plan

### `docs/authors/getting-started.md`

**Audience:** Content authors new to Oscilla.
**Topics to cover:**

- Show a multi-manifest file example with two Items and a Region.
- Explain the `---` divider syntax and that file naming is unrestricted.
- Note that single-manifest files continue to work exactly as before.

### `docs/authors/cli.md`

**Audience:** Content authors using the CLI.
**Topics to cover:**

- Update `oscilla content schema` documentation to reflect `--vscode` no longer requiring `--output`.
- Document the new default output path (`.vscode/oscilla-schemas/`).
- Explain what `manifest.json` is and why VS Code needs it for free-form filenames.
- Show the resulting `settings.json` entry so authors can verify it manually.

No new developer documentation is required; the loader and schema export changes are internal.

---

## Testing Philosophy

### Tier 1 — Unit tests for `parse()`

**File:** `tests/engine/test_loader.py` (extends existing test file)

Fixtures: in-memory `Path`-like strings via `tmp_path`; no real content files needed.

```python
def test_parse_multi_document_file(tmp_path: Path) -> None:
    """Two valid documents in one file both load successfully."""
    multi = tmp_path / "items.yaml"
    multi.write_text(
        "apiVersion: game/v1\nkind: Item\nmetadata:\n  name: sword\nspec:\n  displayName: Sword\n"
        "---\n"
        "apiVersion: game/v1\nkind: Item\nmetadata:\n  name: shield\nspec:\n  displayName: Shield\n"
    )
    manifests, errors = parse([multi])
    assert errors == []
    assert len(manifests) == 2
    names = {m.metadata.name for m in manifests}
    assert names == {"sword", "shield"}


def test_parse_multi_document_mixed_kinds(tmp_path: Path) -> None:
    """Documents of different kinds in one file both load."""
    multi = tmp_path / "mixed.yaml"
    multi.write_text(
        "apiVersion: game/v1\nkind: Item\nmetadata:\n  name: potion\nspec:\n  displayName: Potion\n"
        "---\n"
        "apiVersion: game/v1\nkind: Enemy\nmetadata:\n  name: goblin\n"
        "spec:\n  displayName: Goblin\n  hp: 10\n  damage: 2\n"
    )
    manifests, errors = parse([multi])
    assert errors == []
    assert len(manifests) == 2


def test_parse_multi_document_error_attribution(tmp_path: Path) -> None:
    """An error in doc 2 of a multi-doc file cites [doc 2] in the error message."""
    multi = tmp_path / "items.yaml"
    multi.write_text(
        "apiVersion: game/v1\nkind: Item\nmetadata:\n  name: sword\nspec:\n  displayName: Sword\n"
        "---\n"
        "apiVersion: game/v1\nkind: Item\nmetadata:\n  name: bad\nspec:\n  displayName: 999\n"
        # displayName must be a string; 999 is invalid
    )
    manifests, errors = parse([multi])
    assert len(errors) >= 1
    assert "[doc 2]" in errors[0].message


def test_parse_single_document_no_doc_index_suffix(tmp_path: Path) -> None:
    """Single-document files do not include [doc N] in error messages."""
    single = tmp_path / "item.yaml"
    single.write_text(
        "apiVersion: game/v1\nkind: Item\nmetadata:\n  name: bad\nspec:\n  displayName: 999\n"
    )
    _, errors = parse([single])
    assert all("[doc" not in e.message for e in errors)


def test_parse_empty_document_in_multi_doc_file(tmp_path: Path) -> None:
    """An empty document between --- dividers is reported as an error, not silently skipped."""
    multi = tmp_path / "items.yaml"
    multi.write_text(
        "apiVersion: game/v1\nkind: Item\nmetadata:\n  name: sword\nspec:\n  displayName: Sword\n"
        "---\n"
        "---\n"
        "apiVersion: game/v1\nkind: Item\nmetadata:\n  name: shield\nspec:\n  displayName: Shield\n"
    )
    manifests, errors = parse([multi])
    # The empty document produces an error; the valid ones still load.
    assert len(manifests) == 2
    assert len(errors) == 1
    assert "Manifest must be a YAML mapping" in errors[0].message
```

### Tier 2 — Unit tests for `load()` single-file mode

**File:** `tests/engine/test_loader.py`

```python
def test_load_single_file_path(tmp_path: Path) -> None:
    """load() with a path to a single file works end-to-end."""
    # Minimal valid content: a Game manifest and a CharacterConfig.
    # Use the minimal fixture set from tests/fixtures/content/.
    # Alternatively, construct the minimum viable file inline.
    content_file = tmp_path / "content.yaml"
    content_file.write_text(_MINIMAL_GAME_YAML + "---\n" + _MINIMAL_CHAR_CONFIG_YAML)
    registry, warnings = load(content_file)
    assert registry.game is not None
    assert registry.character_config is not None
```

A `_MINIMAL_GAME_YAML` / `_MINIMAL_CHAR_CONFIG_YAML` helper string constant (or small fixture) is introduced in the test module to avoid depending on testlandia content.

### Tier 3 — Unit tests for `export_union_schema()`

**File:** `tests/engine/test_schema_export.py` (new file)

```python
from oscilla.engine.schema_export import export_union_schema


def test_export_union_schema_structure() -> None:
    """Union schema has oneOf, discriminator, and covers all registered kinds."""
    schema = export_union_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "oneOf" in schema or "anyOf" in schema  # Pydantic may use either
    assert schema.get("title") == "Oscilla Manifest"


def test_export_union_schema_all_kinds_present() -> None:
    """Every registered kind appears as a discriminator value in the union schema."""
    from oscilla.engine.schema_export import valid_kinds
    schema = export_union_schema()
    schema_str = str(schema)  # Quick check — all kind names appear somewhere in schema text
    for kind_slug in valid_kinds():
        # kind slugs are lowercase; model kind values are TitleCase. Check both.
        assert kind_slug in schema_str.lower()
```

### Tier 4 — Integration tests for `content schema --vscode` CLI

**File:** `tests/test_cli_content.py` (extends existing)

```python
from typer.testing import CliRunner
from oscilla.cli_content import content_app

runner = CliRunner()


def test_schema_vscode_default_output(tmp_path: Path, monkeypatch: Any) -> None:
    """--vscode with no --output writes to .vscode/oscilla-schemas/ by default."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(content_app, ["schema", "--vscode"])
    assert result.exit_code == 0
    assert (tmp_path / ".vscode" / "oscilla-schemas" / "manifest.json").exists()
    assert (tmp_path / ".vscode" / "oscilla-schemas" / "adventure.json").exists()


def test_schema_vscode_updates_settings_json(tmp_path: Path, monkeypatch: Any) -> None:
    """--vscode writes a content glob association into settings.json."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(content_app, ["schema", "--vscode"])
    import json
    settings = json.loads((tmp_path / ".vscode" / "settings.json").read_text())
    schemas = settings.get("yaml.schemas", {})
    # One of the keys should point at manifest.json and map to the content glob
    manifest_entries = {k: v for k, v in schemas.items() if "manifest.json" in k}
    assert manifest_entries
    assert "./content/**/*.yaml" in manifest_entries.values()


def test_schema_vscode_preserves_existing_settings(tmp_path: Path, monkeypatch: Any) -> None:
    """Existing settings.json content (e.g. peacock colors) is preserved."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".vscode").mkdir()
    (tmp_path / ".vscode" / "settings.json").write_text('{"peacock.color": "#ff0000"}')
    runner.invoke(content_app, ["schema", "--vscode"])
    import json
    settings = json.loads((tmp_path / ".vscode" / "settings.json").read_text())
    assert settings.get("peacock.color") == "#ff0000"
    assert "yaml.schemas" in settings
```

### Fixture constraints

- Multi-manifest loader tests use `tmp_path` and inline YAML strings — no dependency on `content/testlandia/`.
- CLI tests use `monkeypatch.chdir(tmp_path)` so no real `.vscode/` directory is touched.
- The `test_load_single_file_path` test constructs minimal inline YAML rather than loading testlandia.

---

## Testlandia Integration

**File:** `content/testlandia/regions/tooling-lab/manifests/multi-item-demo.yaml`

Contains three manifests in one file:

```yaml
apiVersion: game/v1
kind: Item
metadata:
  name: demo-bronze-coin
spec:
  displayName: "Bronze Coin"
  description: "A plain coin. One of three defined in a single multi-manifest file."
  item_type: currency
---
apiVersion: game/v1
kind: Item
metadata:
  name: demo-silver-coin
spec:
  displayName: "Silver Coin"
  description: "A silver coin. Defined in the same file as the bronze and gold coins."
  item_type: currency
---
apiVersion: game/v1
kind: Item
metadata:
  name: demo-gold-coin
spec:
  displayName: "Gold Coin"
  description: "A gold coin. All three coins live in multi-item-demo.yaml."
  item_type: currency
```

A developer can manually verify the feature by:

1. Running `oscilla content list items` — all three coins appear.
2. Running `oscilla validate` — no errors.
3. Running `oscilla content schema --vscode` — `.vscode/oscilla-schemas/manifest.json` is created and `.vscode/settings.json` has the content glob association.
4. Opening `multi-item-demo.yaml` in VS Code — schema validation squiggles should appear for any intentional typo in a field.

---

## Risks / Trade-offs

| Risk                                                                                                                   | Mitigation                                                                                                                                                                                        |
| ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `load_all()` is lazy; a parse error mid-file doesn't surface until iteration                                           | Wrapped in `list()` eagerly before the doc loop; file-level parse errors are caught as one error rather than failing silently                                                                     |
| Pydantic's `model_json_schema()` on a discriminated union may produce `anyOf` rather than `oneOf` depending on version | The test checks for either; the yaml-language-server handles both                                                                                                                                 |
| Authors mixing singleton kinds (`Game`, `CharacterConfig`) in multi-doc files                                          | The loader and registry already silently overwrite on duplicate kind+name registration; two `Game` docs in one file would exhibit that existing behavior. No extra guard is added in this change. |
| The `content_path` parameter rename (from `content_dir`) breaks callers using keyword argument                         | Documented in the decision; no internal callers are affected; external library consumers are warned                                                                                               |
