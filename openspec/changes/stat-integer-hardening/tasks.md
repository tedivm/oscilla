## 1. Database Migration

- [x] 1.1 Create an Alembic migration with `make create_migration MESSAGE="replace float stat column with integer"` that changes `character_iteration_stat_values.stat_value` from `Float` (REAL) to `Integer`, using `ROUND(stat_value)::INTEGER` in the PostgreSQL `USING` clause and Alembic batch mode for SQLite compatibility

## 2. Engine Models

- [x] 2.1 Update `oscilla/engine/models/character_config.py`: add `StatBounds` Pydantic model with `min: int | None = None` and `max: int | None = None`; add `model_validator` to `StatBounds` that raises `ValidationError` if `min > max`; add `bounds: StatBounds | None = None` field to `StatDefinition`; add `model_validator` to `StatDefinition` that raises `ValidationError` if `bounds` is set on a `bool` stat; update `StatType` to `Literal["int", "bool"]`; update `StatDefinition.default` type to `int | bool | None`
- [x] 2.2 Update `oscilla/engine/models/adventure.py`: change `StatChangeEffect.amount` type from `int | float` to `int`; change `StatSetEffect.value` type from `int | float | bool | None` to `int | bool | None`

## 3. CharacterState

- [x] 3.1 Update `CharacterState.stats` type annotation in `oscilla/engine/character.py` from `Dict[str, int | float | bool | None]` to `Dict[str, int | bool | None]`
- [x] 3.2 Add `set_stat(name: str, value: int) -> None` method to `CharacterState` that clamps `value` to INT32_MIN–INT32_MAX, logs a `WARNING` if clamping occurs, and stores the clamped value in `self.stats[name]`
- [x] 3.3 Update `CharacterState.effective_stats()` return type annotation to `Dict[str, int | bool | None]`
- [x] 3.4 Update the `_type_map` in `CharacterState.from_dict()` to remove the `"float": float` entry; update the `reconciled_stats` type annotation accordingly
- [x] 3.5 Update `CharacterState.create()` `initial_stats` type annotation to `Dict[str, int | bool | None]`

## 4. Effects Layer — Bounds Enforcement

- [x] 4.1 Update `oscilla/engine/steps/effects.py` `StatChangeEffect` handler: after computing the new value, look up the stat's `StatDefinition` from the registry's `CharacterConfig`; retrieve effective bounds (defaulting to INT32 range when `bounds` is absent or a bound is `None`); if the result would exceed the bounds, clamp it, call `logger.warning(...)`, and call `await tui.show_text(f"[yellow]Warning: stat {stat!r} clamped to {clamped} (attempted {new_value}).[/yellow]")`; use `CharacterState.set_stat()` to store the value
- [x] 4.2 Update `oscilla/engine/steps/effects.py` `StatSetEffect` handler: apply the same bounds lookup, clamp-log-notify pattern from 4.1; use `CharacterState.set_stat()` to store the value
- [x] 4.3 Remove the `isinstance(old_value, (int, float))` guard in the `StatChangeEffect` handler — all `int` stats are now always `int`

## 5. Content Loader Updates

- [x] 5.1 Update `oscilla/engine/loader.py`: remove the `stat_type in ("int", "float")` branches and all float-specific validation paths; they are replaced by `stat_type == "int"` checks; ensure the bounds-on-bool error from `StatDefinition` propagates as a `LoadError` at manifest parse time

## 6. SQLAlchemy Model

- [x] 6.1 Update `oscilla/models/character_iteration.py`: change `CharacterIterationStatValue.stat_value` column from `Mapped[float | None] = mapped_column(Float, nullable=True)` to `Mapped[int | None] = mapped_column(Integer, nullable=True)`; remove `Float` and `REAL` imports if no longer used elsewhere in the file

## 7. Character Service

- [x] 7.1 Rename `_stat_to_float()` to `_stat_to_int()` in `oscilla/services/character.py` and update its implementation: return `int(value)` for `int` stats, `int(bool(value))` for `bool` stats (True→1, False→0), `None` for `None`; update the return type annotation to `int | None`
- [x] 7.2 Update all call sites of the renamed function within `services/character.py`

## 8. Conditions

- [x] 8.1 Update `oscilla/engine/conditions.py`: change `isinstance(value, (int, float))` checks to `isinstance(value, int)` (booleans are a subclass of int so `isinstance(True, int)` is True — no special case needed); update type annotations on `_numeric_compare` from `int | float` to `int`

## 9. Testlandia Content

- [x] 9.1 Update `content/testlandia/character_config.yaml`: change the `speed` stat from `type: float` / `default: 1.0` to `type: int` / `default: 1`; update the description to reflect it is now an int stat used to test integer delta and set operations
- [x] 9.2 Update `content/testlandia/regions/character/locations/bump-speed/adventures/bump-speed.yaml`: change `amount: 0.5` to `amount: 1` and update the display name and description to match
- [x] 9.3 Update `content/testlandia/regions/choices/locations/nested-choice/adventures/nested-choice.yaml`: change the `speed` gain amount from the float value to an integer equivalent

## 10. Tests

- [x] 10.1 Create `tests/engine/test_character_config.py`: add `test_stat_bounds_min_gt_max_raises`, `test_stat_bounds_on_bool_stat_raises`, `test_stat_bounds_absent_is_valid`, `test_stat_bounds_min_only_is_valid`, `test_stat_bounds_max_only_is_valid`, `test_float_stat_type_rejected`
- [x] 10.2 Add to `tests/engine/test_character.py` (or create it): `test_set_stat_clamps_above_int32_max`, `test_set_stat_clamps_below_int32_min`, `test_set_stat_within_range_is_unchanged`
- [x] 10.3 Update `tests/engine/test_stat_effects.py`: delete or replace `test_stat_change_float_negative` with an int equivalent; add `test_stat_change_clamps_to_content_max`, `test_stat_change_clamps_to_content_min`, `test_stat_set_clamps_to_content_max`, `test_stat_change_within_bounds_is_unchanged`, `test_stat_change_clamp_shows_tui_message`
- [x] 10.4 Add to `tests/engine/test_loader.py`: `test_loader_rejects_bounds_on_bool_stat`, `test_loader_rejects_float_stat_type`
- [x] 10.5 Run `make pytest` and confirm all tests pass

## 11. Documentation

- [x] 11.1 Update `docs/authors/content-authoring.md`: remove `float` from the stat type reference table; add a `bounds` subsection under stat definitions with YAML syntax, the default INT32 range behavior, the clamp+notify runtime behavior, a concrete gold-stat example with `min: 0`, and a note that `bounds` on a `bool` stat is a load error
- [x] 11.2 Update `docs/dev/game-engine.md`: update the stat type system section to document `StatType` as `Literal["int", "bool"]`; describe the `StatBounds` model and fields; explain the two-tier enforcement (effects.py + CharacterState backstop); document the INT32 default range and the reason for that choice

## 12. Final Checks

- [x] 12.1 Run `make tests` (pytest + ruff + black + mypy + dapperdata + tomlsort) and confirm all checks pass
- [x] 12.2 Run `make check_ungenerated_migrations` to confirm no pending model changes lack a migration
