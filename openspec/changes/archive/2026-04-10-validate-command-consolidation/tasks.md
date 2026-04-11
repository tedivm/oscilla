## 1. Loader Changes

- [x] 1.1 Change `LoadError.file` from `Path` to `Path | None` and update `__str__` to handle `None`
- [x] 1.2 Change `LoadWarning.file` from `Path` to `Path | None` and update `__str__` to handle `None`
- [x] 1.3 Extract `_parse_text(text: str, source: Path) -> Tuple[List[ManifestEnvelope], List[LoadError]]` from the inner loop of `parse()`, reusing identical per-document parsing logic
- [x] 1.4 Extract `_run_pipeline(manifests, parse_errors, skip_references) -> Tuple[ContentRegistry, List[LoadWarning]]` from the body of `load_from_disk()` — this becomes the single implementation of all post-parse validation steps
- [x] 1.5 Rename `load()` → `load_from_disk()` in `oscilla/engine/loader.py` and update every caller listed in the D1 rename table in `design.md`: `load_games()` (internal call in loader.py), `oscilla/cli.py`, `oscilla/cli_content.py`, all test files that import `load`, `tests/fixtures/content/trigger_tests/__init__.py`, and the code sample in `docs/dev/game-engine.md`
- [x] 1.6 Add `load_from_text(text: str, skip_references: bool = False) -> Tuple[ContentRegistry, List[LoadWarning]]` as a thin wrapper: `_parse_text` + `_run_pipeline`

## 2. CLI — `validate` Command

- [x] 2.1 Add `io` and `json` imports to `oscilla/cli.py`
- [x] 2.2 Add `--format / -F` parameter to the `validate` command (default `"text"`)
- [x] 2.3 Add `--no-references` parameter to the `validate` command
- [x] 2.4 Add `--stdin` flag to `validate`; dispatch to `_validate_stdin()` or `_validate_games()` based on whether `stdin=True`
- [x] 2.5 Implement `_validate_stdin(output_format, strict, no_semantic, no_references)` using `load_from_text`
- [x] 2.6 Implement `_validate_games(game_name, output_format, strict, no_semantic, no_references)` refactored from existing validate body
- [x] 2.7 Implement `_render_validate_output(output_format, strict, pkg_summaries, error_list, warning_list)` shared renderer
- [x] 2.8 Implement `_registry_summary(registry) -> Dict[str, int]` helper
- [x] 2.9 Implement `_emit_structured_output(data, output_format)` helper (json/yaml serialization)

## 3. CLI — `content test` Alias

- [x] 3.1 Replace the body of `content_test` in `oscilla/cli_content.py` with a call to `_validate_games` imported from `oscilla.cli`, keeping the existing command signature (`--game`, `--strict`, `--format`)

## 4. Tests

- [x] 4.1 Add `test_validate_format_flag_in_help` — asserts `--format` and `-F` appear in `validate --help` output
- [x] 4.2 Add `test_validate_no_references_flag_in_help` — asserts `--no-references` appears in `validate --help` output
- [x] 4.3 Add `test_validate_json_format_disk_mode` — asserts exit 0, valid JSON, keys `errors`/`warnings`/`summary` present, at least one game package in summary
- [x] 4.4 Add `test_validate_yaml_format_disk_mode` — asserts exit 0, parseable YAML, same keys
- [x] 4.5 Add `test_validate_stdin_valid_manifest` — pipes a valid Item YAML with `--no-semantic --no-references`, asserts exit 0
- [x] 4.6 Add `test_validate_stdin_invalid_yaml` — pipes malformed YAML, asserts exit 1 and parse error in output
- [x] 4.7 Add `test_validate_stdin_unknown_kind` — pipes `kind: Nonexistent`, asserts exit 1
- [x] 4.8 Add `test_validate_stdin_empty` — pipes empty string, asserts exit 1
- [x] 4.9 Add `test_validate_stdin_json_output` — pipes valid Item YAML with `--format json --no-semantic --no-references`, asserts valid JSON with `summary["<stdin>"]["items"] == 1`
- [x] 4.10 Add `test_validate_game_flag_ignored_in_stdin_mode` — pipes valid manifest with `--game nonexistent-game --no-semantic --no-references`, asserts exit 0
- [x] 4.11 Add `test_content_test_still_works_as_alias` — invokes `content test` on testlandia content, asserts exit 0
- [x] 4.12 Add `test_content_test_json_format` — invokes `content test --format json`, asserts valid JSON with `errors`/`warnings`/`summary`
- [x] 4.13 Run `uv run pytest tests/test_cli.py tests/test_cli_content.py -x` and confirm all pass

## 5. Documentation

- [x] 5.1 Update `docs/dev/cli.md`: add `--format`, `--no-references`, `--stdin` to the `validate` section; document stdin mode; describe `content test` as a backwards-compat alias; show example JSON output shape
- [x] 5.2 Update `docs/authors/cli.md`: add `--format`, `--no-references`, `--stdin` flag descriptions to `oscilla validate`; add a "Validating standalone manifests" section with a `--stdin` piping example; document `--no-references` use case for isolated doc snippets
- [x] 5.3 Update `.github/skills/oscilla-content-cli/SKILL.md`: update the command reference table to note `--stdin` support on `validate`; update the "Common options" block to include `--stdin`, `--no-references`, `--format`; update the `content test` description to reflect it is now a backwards-compat alias; add a note that `--stdin` and `--no-references` are only available on `validate`, not on `content test`

## 6. Final Verification

- [x] 6.1 Run `make tests` and confirm all checks pass (pytest, ruff, mypy, black, dapperdata, tomlsort)
- [x] 6.2 Manually verify: `uv run oscilla validate` shows testlandia summary
- [x] 6.3 Manually verify: `uv run oscilla validate --format json | python3 -m json.tool` emits valid JSON with `summary.testlandia`
- [x] 6.4 Manually verify: `echo "kind: Item\nmetadata:\n  name: t\nspec:\n  category: weapon\n  labels: []" | uv run oscilla validate --stdin --no-references --no-semantic` exits 0
- [x] 6.5 Manually verify: `uv run oscilla content test` and `uv run oscilla content test --format json` both work as before
