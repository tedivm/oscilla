## Why

Content authors frequently want to group closely related manifests — a family of item tiers, a set of region locations, multiple enemy variants — in a single file, but today every manifest requires its own YAML file. This creates unnecessary file proliferation for content packages and also surfaces a gap in editor validation: the current schema CLI generates filename-based globs that don't match the free-form file names authors actually use, meaning VS Code YAML schema validation silently does nothing for most content files.

## What Changes

- **Multi-document YAML loading**: The manifest loader accepts files containing multiple YAML documents separated by `---` dividers. A single-document file continues to work identically; no authored content changes are needed.
- **Single-file content path**: `load()` accepts either a directory path (existing behavior, unchanged) or a path to a single YAML file (all documents in the file are treated as the full content package).
- **Umbrella union schema**: A new `manifest.json` schema is generated alongside the existing per-kind schemas. It is a `oneOf` union discriminated by the `kind` field, covering all registered manifest kinds.
- **VS Code schema CLI update**: `oscilla content schema --vscode` writes schema associations using a project-wide glob (`**/*.yaml`) pointing at the umbrella schema, instead of the previous filename-pattern approach. The umbrella schema uses an `if/then` guard on `apiVersion: oscilla/v1` so it is a strict no-op for non-Oscilla YAML files. The default output directory is `.vscode/oscilla-schemas/` to avoid collisions with any other editor tooling.
- **`apiVersion` rename** (**BREAKING**): `apiVersion: game/v1` is renamed to `apiVersion: oscilla/v1` across all manifests, engine models, scaffold templates, tests, and documentation. Clarifies ownership and aligns the version field with the library name.
- **Error attribution**: Load errors in multi-document files include the document index within the file (e.g., `myitems.yaml [doc 2]`) to make debugging precise.

## Capabilities

### New Capabilities

- `multi-manifest-loading`: Multi-document YAML file support in the content loader — `load_all()` parsing, single-file path mode, and per-document error attribution.

### Modified Capabilities

- `manifest-system`: The loader requirement for "one manifest per file" is removed. The `load()` function signature gains single-file path support. Schema export gains a union schema (`manifest.json`). The `content schema --vscode` CLI command changes its default output path and association glob pattern. The `apiVersion` accepted value changes from `game/v1` to `oscilla/v1`.

## Impact

- **`oscilla/engine/models/base.py`** — `apiVersion` field changes from `Literal["game/v1"]` to `Literal["oscilla/v1"]`. **BREAKING** for any existing saved content or manifests using the old value.
- **`oscilla/engine/loader.py`** — `parse()` switches to `load_all()`; `load()` detects `is_file()` vs `is_dir()`.
- **`oscilla/engine/schema_export.py`** — new `export_union_schema()` function with `if/then` `apiVersion` guard.
- **`oscilla/engine/scaffolder.py`** — scaffold templates updated to emit `oscilla/v1`.
- **`oscilla/cli_content.py`** — `content schema --vscode` default output path and `**/*.yaml` glob updated.
- **All content YAML files** — `apiVersion: game/v1` → `apiVersion: oscilla/v1`.
- **All tests** — `apiVersion` strings updated.
- **All documentation** — examples updated.
- No database changes.

## Testlandia Updates

A new file `content/testlandia/regions/tooling-lab/multi-manifest-demo.yaml` is added containing at least three manifests of two different kinds (e.g., two `Item` manifests and one `Location`) separated by `---` dividers. The tooling-lab region (already present in testlandia) surfaces these items/locations as part of the existing authoring tooling demo so a developer can verify that:

1. `oscilla content list items` shows the items defined in the multi-manifest file.
2. `oscilla content list locations` shows the location defined in the same file.
3. `oscilla validate` reports no errors.
4. VS Code shows schema validation hints after running `oscilla content schema --vscode`.
