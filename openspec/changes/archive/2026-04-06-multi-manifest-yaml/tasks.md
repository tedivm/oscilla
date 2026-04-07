## 0. Breaking Change: `apiVersion` Rename (COMPLETED)

- [x] 0.1 In `oscilla/engine/models/base.py`, change `ManifestEnvelope.apiVersion` from `Literal["game/v1"]` to `Literal["oscilla/v1"]`.
- [x] 0.2 In `oscilla/engine/scaffolder.py`, update all 6 scaffold template dicts from `"apiVersion": "game/v1"` to `"apiVersion": "oscilla/v1"`.
- [x] 0.3 Bulk-rename all content YAML files (`content/**/*.yaml`): replace `apiVersion: game/v1` with `apiVersion: oscilla/v1`.
- [x] 0.4 Bulk-rename all test files (`tests/**/*.py`): replace `apiVersion="game/v1"` with `apiVersion="oscilla/v1"`.
- [x] 0.5 Bulk-rename all documentation (`docs/**/*.md`, `openspec/**/*.md`): update all code block examples.

## 1. Loader: Multi-Document YAML Parsing

- [x] 1.1 In `oscilla/engine/loader.py`, replace `_yaml.load()` with `_yaml.load_all()` in `parse()`. Wrap in `list()` to eagerly evaluate the generator. Iterate with `enumerate(docs)` and prefix error messages with `[doc N]` when `len(docs) > 1`.
- [x] 1.2 In `parse()`, handle the `None` case for empty documents between `---` dividers: if `raw is None`, emit `LoadError` with "Manifest must be a YAML mapping" and continue.
- [x] 1.3 Update `load()` to rename the parameter from `content_dir` to `content_path`. Add an `is_file()` branch: when true, set `paths = [content_path]`; otherwise call `scan(content_path)` as before.

## 2. Schema Export: Union Schema

- [x] 2.1 In `oscilla/engine/schema_export.py`, add `export_union_schema()`. Build a `RootModel` with a discriminated `Union` of all manifest kind models (discriminator field: `kind`). Call `model_json_schema()`, extract the inner schema, then wrap it in a JSON Schema `if/then` guard (`if: {properties: {apiVersion: {const: "oscilla/v1"}}, required: ["apiVersion"]}`) so the schema is a no-op for non-Oscilla YAML files. Annotate with `$schema`, `$id`, and `title`. Keep `$defs` at the top level so `$ref` paths resolve correctly.

## 3. CLI: `content schema --vscode` Updates

- [x] 3.1 In `oscilla/cli_content.py`, update the `content_schema` command: resolve `effective_output = output or (".vscode/oscilla-schemas" if vscode else None)`. Remove the hard error for `--vscode` without `--output`.
- [x] 3.2 Update the all-schemas branch to always write `manifest.json` (via `export_union_schema()`) when an output directory is used.
- [x] 3.3 Rewrite `_write_vscode_schema_associations()` to remove the `schemas: dict` parameter (no longer needed) and write a single `yaml.schemas` entry: `manifest_schema_path → "**/*.yaml"`. The `if/then` guard in `manifest.json` makes this glob safe for projects containing non-Oscilla YAML files.

## 4. Tests: Loader

- [x] 4.1 In `tests/engine/test_loader.py`, add `test_parse_multi_document_file`: two valid `Item` documents in one `tmp_path` file; asserts two manifests, no errors.
- [x] 4.2 Add `test_parse_multi_document_mixed_kinds`: one `Item` and one `Enemy` in one file; asserts both load.
- [x] 4.3 Add `test_parse_multi_document_error_attribution`: valid doc 1, invalid doc 2; asserts `[doc 2]` in error message.
- [x] 4.4 Add `test_parse_single_document_no_doc_index_suffix`: one invalid document; asserts no `[doc` in error messages.
- [x] 4.5 Add `test_parse_empty_document_in_multi_doc_file`: valid doc, empty doc, valid doc; asserts two manifests loaded, one error, "Manifest must be a YAML mapping" in error message.
- [x] 4.6 Add `test_load_single_file_path`: call `load()` with a `tmp_path` file containing minimal inline `Game` + `CharacterConfig` YAML; assert `registry.game is not None`.

## 5. Tests: Schema Export

- [x] 5.1 Create `tests/engine/test_schema_export.py`. Add `test_export_union_schema_structure`: asserts `$schema`, title, and presence of `oneOf` or `anyOf`.
- [x] 5.2 Add `test_export_union_schema_all_kinds_present`: calls `valid_kinds()` and checks each kind slug appears in the schema string representation.

## 6. Tests: CLI Schema Command

- [x] 6.1 In `tests/test_cli_content.py`, add `test_schema_vscode_default_output`: runs `["schema", "--vscode"]` with `monkeypatch.chdir(tmp_path)`; asserts `.vscode/oscilla-schemas/manifest.json` and `.vscode/oscilla-schemas/adventure.json` exist.
- [x] 6.2 Add `test_schema_vscode_updates_settings_json`: runs `--vscode`; reads `settings.json`; asserts a `yaml.schemas` entry maps to `./content/**/*.yaml` and points at `manifest.json`.
- [x] 6.3 Add `test_schema_vscode_preserves_existing_settings`: pre-creates `settings.json` with `{"peacock.color": "#ff0000"}`; runs `--vscode`; asserts `peacock.color` is still present.

## 7. Documentation

- [x] 7.1 In `docs/authors/getting-started.md`, add a short section ("Multi-Manifest Files") showing the `---` divider syntax with a two-item example. Note that file naming is unrestricted and single-manifest files continue to work unchanged.
- [x] 7.2 In `docs/authors/cli.md`, update the `oscilla content schema` documentation: reflect that `--vscode` no longer requires `--output`, document the `.vscode/oscilla-schemas/` default, explain what `manifest.json` is, and show the resulting `settings.json` entry.

## 8. Testlandia Content

- [x] 8.1 Create `content/testlandia/regions/tooling-lab/manifests/multi-item-demo.yaml` containing three `Item` manifests (`demo-bronze-coin`, `demo-silver-coin`, `demo-gold-coin`) separated by `---` dividers.
- [x] 8.2 Run `oscilla validate` to confirm all three coins load without errors.
- [x] 8.3 Run `oscilla content list items` to confirm all three names appear in the output.
