# Tasks

## 1. Models — new `CombatSystem` manifest and supporting types

- [x] 1.1 Create `oscilla/engine/models/combat_system.py`. Add `CombatStatEntry` (`name: str`, `default: int = 0`); `SystemSkillEntry` (`skill: str`, `condition: "Condition | None" = None`); `ThresholdEffectBand` (`min: int | None = None`, `max: int | None = None`, `effects: List["Effect"]` — at least one bound required, validated by a model validator); `DamageFormulaEntry` (`target_stat: str | None = None`, `target: Literal["player", "enemy", "combat"] | None = None`, `formula: str`, `display: str | None = None`, `threshold_effects: List[ThresholdEffectBand] = []` — `target_stat: null` with empty `threshold_effects` is a model-level hard error); `CombatSystemSpec` (all fields per design.md Decision 1 — `player_defeat_condition`, `enemy_defeat_condition`, `player_damage_formulas`, `enemy_damage_formulas`, `resolution_formulas`, `player_turn_mode`, `turn_order`, `player_initiative_formula`, `enemy_initiative_formula`, `initiative_tie`, `skill_contexts`, `system_skills`, `on_combat_start`, `on_combat_end`, `on_combat_victory`, `on_combat_defeat`, `on_round_end`, `combat_stats`, `simultaneous_defeat_result`); `CombatSystemManifest` (extends `ManifestEnvelope`, `kind: Literal["CombatSystem"]`, `spec: CombatSystemSpec`); `CombatStepOverrides` (all optional fields mirroring `CombatSystemSpec` — any field absent means "do not override"). Use `TYPE_CHECKING` guards for `Condition` and `Effect` to avoid circular imports.
- [x] 1.2 Add `from oscilla.engine.models.combat_system import CombatSystemManifest` to `oscilla/engine/models/__init__.py`. Add `"CombatSystem": CombatSystemManifest` to `MANIFEST_REGISTRY`. Add `"CombatSystemManifest"` to `__all__`.
- [x] 1.3 Update `EnemySpec` in `oscilla/engine/models/enemy.py`: remove `hp: int`, `attack: int`, `defense: int`, `xp_reward: int`; add `stats: Dict[str, int] = Field(default_factory=dict)` and `on_defeat_effects: List["Effect"] = []`. Update the docstring to reflect the change. Import `Effect` under `TYPE_CHECKING`.
- [x] 1.4 Add `combat_system: str | None = None` and `combat_overrides: "CombatStepOverrides | None" = None` to `CombatStep` in `oscilla/engine/models/adventure.py`. Import `CombatStepOverrides` under `TYPE_CHECKING`.
- [x] 1.5 Update `SkillSpec` in `oscilla/engine/models/skill.py`: relax `contexts` from a fixed enum to `List[str]` (keeping `"overworld"` as a semantically reserved value, enforced at validation time, not at model level); add `combat_damage_formulas: List[DamageFormulaEntry] = []`. Import `DamageFormulaEntry` from `oscilla.engine.models.combat_system` (or lazily under `TYPE_CHECKING` if circular).
- [x] 1.6 Update `ItemSpec` in `oscilla/engine/models/item.py`: add `contexts: List[str] = []` and `combat_damage_formulas: List[DamageFormulaEntry] = []`. Update `EquipSpec` (same file): add `combat_damage_formulas: List[DamageFormulaEntry] = []`.
- [x] 1.7 Add `default_combat_system: str | None = None` to `GameSpec` in `oscilla/engine/models/game.py`.

## 2. Condition models — `EnemyStatCondition` and `CombatStatCondition`

- [x] 2.1 Add `EnemyStatCondition` to `oscilla/engine/models/base.py` with `type: Literal["enemy_stat"]`, `stat: str`, and the standard comparator fields (`gte: int | None`, `lte: int | None`, `gt: int | None`, `lt: int | None`, `eq: int | None`). Add `CombatStatCondition` with `type: Literal["combat_stat"]` and the same comparator fields.
- [x] 2.2 Add `EnemyStatCondition` and `CombatStatCondition` to the `Condition` union member list in `base.py` (after `CustomConditionRef`, before the closing bracket). Keep the existing member order otherwise unchanged.

## 3. Condition evaluator — `evaluate()` signature extension

- [x] 3.1 Add `enemy_stats: Dict[str, int] | None = None` and `combat_stats: Dict[str, int] | None = None` keyword parameters to `evaluate()` in `oscilla/engine/conditions.py`. Update all recursive calls inside the function to forward these parameters. The new parameters are optional to preserve the existing call sites (overworld conditions, passive effects, skill gate checks).
- [x] 3.2 Add a `case EnemyStatCondition(stat=s, ...)` arm: evaluate the named key in `enemy_stats` against the comparator fields; return `False` with a `logger.warning` when `enemy_stats is None` (called outside combat context).
- [x] 3.3 Add a `case CombatStatCondition(stat=s, ...)` arm: evaluate the named key in `combat_stats` against the comparator fields; return `False` with a `logger.warning` when `combat_stats is None` (called outside combat context).
- [x] 3.4 Update all existing non-combat `evaluate()` call sites in `oscilla/engine/` that currently pass positional args to use keyword arguments so the new parameters are not accidentally shifted. Verify with `mypy`.

## 4. Registry — `combat_systems` collection and auto-default logic

- [x] 4.1 Add `from oscilla.engine.models.combat_system import CombatSystemManifest` to the imports in `oscilla/engine/registry.py`. Add `self.combat_systems: KindRegistry[CombatSystemManifest] = KindRegistry()` to `ContentRegistry.__init__()`.
- [x] 4.2 Add a `case "CombatSystem":` arm to the `build()` match block: `registry.combat_systems.register(cast(CombatSystemManifest, m))`.
- [x] 4.3 Implement `resolve_combat_system(self, name: str | None) -> CombatSystemManifest | None` on `ContentRegistry`. Resolution order: (1) use `name` if provided; (2) use `self.game.spec.default_combat_system` if set; (3) if exactly one `CombatSystem` is registered, auto-promote it. Return `None` if no system can be resolved.
- [x] 4.4 Add `get_default_combat_system(self) -> CombatSystemManifest | None` as a convenience property that calls `resolve_combat_system(name=None)`. (Used by the semantic validator load-time checks without an explicit step reference.)

## 5. `CombatContext` — `enemy_stats` dict and `combat_stats` dict

- [x] 5.1 Replace `enemy_hp: int` with `enemy_stats: Dict[str, int]` in `CombatContext` in `oscilla/engine/combat_context.py`. Remove the `enemy_hp` docstring comment that references `step_state["enemy_hp"]` and replace it with a note about `step_state["enemy_stats"]`.
- [x] 5.2 Add `combat_stats: Dict[str, int] = field(default_factory=dict)` to `CombatContext`. This mirrors `step_state["combat_stats"]`; discarded (not written to player stats) when combat ends.

## 6. Template context — `CombatContextView`, `CombatFormulaContext`, formula globals

- [x] 6.1 Update `CombatContextView` in `oscilla/engine/templates.py`: remove `enemy_hp: int`; add `enemy_stats: Dict[str, int]` and `combat_stats: Dict[str, int]`. Update `_MockCombatContext` (or wherever the mock is constructed) to set both dicts to empty dicts `{}`.
- [x] 6.2 Add a `CombatFormulaContext` dataclass (or named tuple) to `oscilla/engine/templates.py` (or a new `oscilla/engine/formula.py` module if cleanly separable). Fields: `player: Dict[str, int]` (effective stats), `enemy_stats: Dict[str, int]`, `combat_stats: Dict[str, int]`, `turn_number: int`.
- [x] 6.3 Implement `render_formula(formula: str, ctx: CombatFormulaContext) -> int` — a function that renders a Jinja2 template string in `CombatFormulaContext` and returns an `int`. The function must: (a) support `{% set %}` blocks before the `{{ }}` output expression; (b) expose `player`, `enemy_stats`, `combat_stats`, and `turn_number` from the context; (c) include all existing `SAFE_GLOBALS`; (d) return the rendered result coerced to `int`; (e) raise `FormulaRenderError` (new exception class) on type error or Jinja2 error.
- [x] 6.4 Add `rollpool(n: int, sides: int, threshold: int) -> int` to `SAFE_GLOBALS` — roll `n` dice of `sides` sides and return the count of dice whose result is ≥ `threshold`. Raise `ValueError` on invalid inputs (`n < 1`, `sides < 2`, `threshold < 1`).
- [x] 6.5 Add `rollsum(n: int, sides: int) -> int` to `SAFE_GLOBALS` — roll `n` dice of `sides` sides and return their sum. Raise `ValueError` on invalid inputs.
- [x] 6.6 Add `keephigh(n: int, sides: int, k: int) -> int` to `SAFE_GLOBALS` — roll `n` dice of `sides` sides and return the sum of the highest `k`. Raise `ValueError` when `k > n` or other invalid inputs.
- [x] 6.7 Add `clamp(x: int, lo: int, hi: int) -> int` to `SAFE_GLOBALS` — return `x` clamped to `[lo, hi]` inclusive.

## 7. Effects — `stat_change` enemy fix, `combat` target, `heal` deprecation

- [x] 7.1 Fix the `stat_change target='enemy'` case in `oscilla/engine/steps/effects.py`: it must now use `effect.stat` as the key into `combat.enemy_stats` and update that dict (not a hardcoded vital field). Raise `KeyError` (logged as a warning) if the named stat is absent from `enemy_stats` — do not crash.
- [x] 7.2 Add `stat_change target='combat'` and `stat_set target='combat'` handling in `effects.py`: mutate the named key in `combat.combat_stats`. Initialize the key with value `0` if absent (do not raise on missing — `combat_stats` can be extended at runtime by effect chains).
- [x] 7.3 Add the `heal target='enemy'` deprecation warning to `oscilla/engine/semantic_validator.py` as a `SemanticIssue` with `severity="warning"` and `kind="deprecated_heal_enemy"`. Add a `_check_heal_enemy_deprecation()` function and wire it into `validate_semantic()`.

## 8. Combat loop — full refactor

- [x] 8.1 Add `def merge_overrides(base: CombatSystemSpec, overrides: CombatStepOverrides | None) -> CombatSystemSpec` to `oscilla/engine/steps/combat.py` (or a helper module). A `None` override passes through unchanged. The merge produces a new `CombatSystemSpec` where every non-`None` field in `overrides` replaces the corresponding field in `base`; absent override fields leave `base` values intact.
- [x] 8.2 Add `def resolve_turn_order(spec: CombatSystemSpec, formula_ctx: CombatFormulaContext) -> Literal["player_first", "enemy_first", "simultaneous"]` to `combat.py`. Handles `"player_first"`, `"enemy_first"`, `"simultaneous"` directly. For `"initiative"` mode: renders both formula fields; higher result returns `"player_first"` or `"enemy_first"`; equal result resolved by `initiative_tie`; logs the initiative values at DEBUG.
- [x] 8.3 Rename `_enemy_skill_phase()` to `enemy_action_phase()` in `combat.py`. Make it a first-class async function (not a nested helper). Update its signature to accept a `CombatSystemSpec` parameter (for future AI hook compatibility).
- [x] 8.4 Implement `async def player_action_phase(spec: CombatSystemSpec, ctx: CombatContext, player: CharacterState, registry: ContentRegistry, tui: UICallbacks, formula_ctx: CombatFormulaContext) -> None` in `combat.py`. Dispatch based on `spec.player_turn_mode`: `"auto"` — run each `DamageFormulaEntry` in `spec.player_damage_formulas` via `apply_damage_formula()`; `"choice"` — build the action menu from `spec.system_skills` (filtered by `condition`) + player-owned skills whose `contexts` intersects `spec.skill_contexts` + player-owned combat items + always-present "Do Nothing" option; present the menu; run the chosen skill or item effects.
- [x] 8.5 Implement `def apply_damage_formula(entry: DamageFormulaEntry, formula_ctx: CombatFormulaContext, ctx: CombatContext) -> None` — renders the formula, applies the result to the correct stat namespace via `resolve_target()`, evaluates `threshold_effects` bands (if any) and runs matched effects, logs the display label (if set).
- [x] 8.6 Implement `def resolve_target(entry: DamageFormulaEntry, ctx: CombatContext) -> Dict[str, int]` — returns the dict to mutate based on `entry.target` (`"player"` → `player.stats`, `"enemy"` → `ctx.enemy_stats`, `"combat"` → `ctx.combat_stats`). Falls back to `enemy_stats` when `entry.target is None` and `entry.target_stat` is set.
- [x] 8.7 Refactor `run_combat()` in `combat.py`:
  - Resolve the `CombatSystem` manifest via `registry.resolve_combat_system(step.combat_system)`.
  - Merge overrides via `merge_overrides(system.spec, step.combat_overrides)`.
  - Initialize `enemy_stats` from `step_state["enemy_stats"]` (resume) or `enemy.spec.stats` (new).
  - Initialize `combat_stats` from `step_state["combat_stats"]` (resume) or derived from `spec.combat_stats` defaults (new).
  - Fire `spec.on_combat_start` effects only on new combat (not resume); detect resume by presence of `step_state["enemy_stats"]`.
  - Build `CombatFormulaContext` fresh each round.
  - Per-round loop: (1) `_tick_active_effects()`; (2) `resolve_turn_order()` → dispatch first-actor phase; (3) defeat check (sequential modes only) — if defeated, skip second actor and `resolution_formulas`; (4) dispatch second-actor phase; (5) defeat check (sequential modes only); (6) `resolution_formulas` phase (always in `"simultaneous"`, only if no mid-round defeat in sequential modes); (7) `spec.on_round_end` effects; (8) defeat check after `on_round_end`.
  - `"simultaneous"` mode: both actor phases always complete; defeat check only after `resolution_formulas` and `on_round_end`; handle mutual defeat via `spec.simultaneous_defeat_result`.
  - After combat ends: fire `spec.on_combat_end`; then `spec.on_combat_victory` (win) or `spec.on_combat_defeat` (loss/flee).
  - On victory: run `enemy.spec.on_defeat_effects`, then loot, then `on_win` branch.
  - Persist `step_state["enemy_stats"]` and `step_state["combat_stats"]` each round.
  - Discard `combat_stats` (do not write to `player.stats`) when combat ends.
- [x] 8.8 Implement the `resolution_formulas` phase inside the round loop: iterate `spec.resolution_formulas`, call `apply_damage_formula()` for each entry, then re-check defeat conditions.
- [x] 8.9 Pass `enemy_stats` and `combat_stats` from `CombatContext` into the `evaluate()` call used for defeat condition checks so that `EnemyStatCondition` and `CombatStatCondition` resolve correctly.

## 9. Semantic validator — new load-time checks

- [x] 9.1 Add `_check_combat_system_required()`: error if any adventure contains a `CombatStep` and no `CombatSystem` is resolvable from the registry (i.e., `registry.get_default_combat_system()` returns `None`). Wire into `validate_semantic()`.
- [x] 9.2 Add `_check_player_turn_mode_conflict()`: error if a `CombatSystemSpec` (or any merged override result) has `player_turn_mode == "choice"` and `player_damage_formulas` is non-empty. Wire into `validate_semantic()`.
- [x] 9.3 Add `_check_initiative_formula_requirements()`: error if `turn_order == "initiative"` and either initiative formula is absent; warning if initiative formulas are present and `turn_order != "initiative"`. Wire into `validate_semantic()`.
- [x] 9.4 Add `_check_enemy_stat_coverage()`: for each `EnemyManifest`, resolve its applicable `CombatSystem` (via the game default or per-adventure step reference) and verify the enemy's `stats` dict contains every stat key referenced as `target_stat` in `player_damage_formulas` and `enemy_damage_formulas`. Emit an error for each missing stat. Wire into `validate_semantic()`.
- [x] 9.5 Add `_check_combat_stat_condition_refs()`: for each `EnemyStatCondition` or `CombatStatCondition` appearing inside a `player_defeat_condition` or `enemy_defeat_condition`, verify the referenced `stat` key is declared in the system's `combat_stats` list (for `CombatStatCondition`) or that the key is structurally plausible as an enemy stat (for `EnemyStatCondition` — a warning, not an error, since enemy stat keys are dynamic). Wire into `validate_semantic()`.
- [x] 9.6 Add `_check_system_skill_refs()`: for each `SystemSkillEntry.skill` in a `CombatSystemSpec`, verify the named skill is registered in `registry.skills`. Wire into `validate_semantic()`.
- [x] 9.7 Add `_check_target_stat_null_validity()`: error if any `DamageFormulaEntry` has `target_stat == None` and an empty `threshold_effects` list — this is a no-op formula and should be caught at load time. Wire into `validate_semantic()`.
- [x] 9.8 Add `_check_formula_mock_render()`: mock-render every `DamageFormulaEntry.formula` in all `CombatSystem` manifests using a zeroed `CombatFormulaContext` to catch syntax errors at load time. Emit a `SemanticIssue` with `severity="error"` for any formula that raises. Wire into `validate_semantic()`.
- [x] 9.9 Add `_check_dynamic_stat_change_value()`: when a `stat_change` effect inside a `ThresholdEffectBand` has `value` as a string, mock-render it in a zeroed `CombatFormulaContext` to validate it. Emit an error if it fails. Emit a hard error if a string `value` appears on a `stat_change` outside a `threshold_effects` context (not yet supported). Wire into `validate_semantic()`.

## 10. Character state — `step_state` type widening

- [x] 10.1 Widen the `step_state` type annotation in `oscilla/engine/character.py` from `Dict[str, scalar]` (or however it is currently typed) to `Dict[str, Any]`. Update the `from typing import` line if needed.

## 11. Scaffolder — enemy scaffold update

- [x] 11.1 Update `oscilla/engine/scaffolder.py` enemy scaffold to use the new `EnemySpec` shape: replace the hardcoded `hp`/`attack`/`defense`/`xp_reward` fields with a `stats: {}` stub and an empty `on_defeat_effects: []`. Add a comment pointing authors to the CombatSystem manifest for defeat conditions.

## 12. Content migration — testlandia

- [x] 12.1 Update every enemy manifest in `content/testlandia/` to the new `EnemySpec` schema: remove the `spec.hp`, `spec.attack`, `spec.defense`, and `spec.xp_reward` fields; add `spec.stats` with equivalent values mapped to the stat names used by the testlandia `CombatSystem` (`hp`, `attack`, `defense`); add `spec.on_defeat_effects` with an `xp_reward` equivalent as a `grant_xp` effect (or `stat_change` to an xp stat, whichever matches the testlandia convention).
- [x] 12.2 Create `content/testlandia/combat-systems/standard-combat.yaml` — a `CombatSystem` manifest (`metadata.name: standard-combat`) that reproduces the current testlandia combat behavior: `player_defeat_condition` checks `player.stats['hp'] <= 0`; `enemy_defeat_condition` checks `enemy_stats['hp'] <= 0`; `player_damage_formulas` using `strength` and `dexterity` as before; `enemy_damage_formulas` using `attack` and `defense`; `turn_order: "player_first"`.
- [x] 12.3 Add `default_combat_system: standard-combat` to `content/testlandia/game.yaml` under the `spec` block.
- [x] 12.4 Run `oscilla content validate testlandia` and confirm zero errors after the migration.

## 13. Tests — unit tests

- [x] 13.1 Create `tests/engine/test_combat_system.py`. Add a `make_character_state()` factory helper matching the style in `tests/engine/test_combat_skills.py`.
- [x] 13.2 Add `test_evaluate_enemy_stat_condition_true()` and `test_evaluate_enemy_stat_condition_false()` — construct `EnemyStatCondition` with a `lte` bound; call `evaluate()` with `enemy_stats={"hp": value}`; assert correct boolean.
- [x] 13.3 Add `test_evaluate_enemy_stat_condition_outside_combat()` — call `evaluate(EnemyStatCondition(...), player, enemy_stats=None)`; assert `False` and that a warning was logged.
- [x] 13.4 Add `test_evaluate_combat_stat_condition()` — parallel tests for `CombatStatCondition`.
- [x] 13.5 Add `test_resolve_turn_order_player_first()`, `test_resolve_turn_order_enemy_first()`, `test_resolve_turn_order_simultaneous()` — construct minimal `CombatSystemSpec` objects with the corresponding `turn_order` values; call `resolve_turn_order()`; assert the returned literal.
- [x] 13.6 Add `test_resolve_turn_order_initiative_player_wins()` and `test_resolve_turn_order_initiative_enemy_wins()` — use deterministic formula strings (`"{{ 10 }}"` vs `"{{ 5 }}"`) to test initiative dispatch; verify tie-breaking via `initiative_tie`.
- [x] 13.7 Add `test_merge_overrides_none_passthrough()` — `merge_overrides(base, None)` returns the same spec unchanged.
- [x] 13.8 Add `test_merge_overrides_replaces_fields()` — override a single field (e.g. `turn_order`) and verify all other fields are preserved.
- [x] 13.9 Add `test_render_formula_basic()` — `render_formula("{{ 2 + 3 }}", ctx)` returns `5`.
- [x] 13.10 Add `test_render_formula_set_block()` — `render_formula("{% set x = 3 %}{{ x * 2 }}", ctx)` returns `6`.
- [x] 13.11 Add `test_rollpool_counts_successes()`, `test_rollsum_returns_int()`, `test_keephigh_returns_sum()`, `test_clamp_clamps_value()` — test each new `SAFE_GLOBALS` function with boundary cases.
- [x] 13.12 Add `test_stat_change_enemy_uses_stat_field()` — construct a minimal `CombatContext` with `enemy_stats={"hp": 50}`, run a `StatChangeEffect(target="enemy", stat="hp", value=-10)` through `run_effect()`, assert `enemy_stats["hp"] == 40`.
- [x] 13.13 Add `test_stat_change_combat_target()` — same pattern for `target="combat"` against `combat_stats`.
- [x] 13.14 Add `test_combat_system_registry_auto_default()` — register exactly one `CombatSystemManifest` in a fresh `ContentRegistry`; call `get_default_combat_system()`; assert it returns that manifest.
- [x] 13.15 Add `test_combat_system_registry_no_default_returns_none()` — call `get_default_combat_system()` on an empty registry; assert `None`.

## 14. Tests — semantic validator

- [x] 14.1 Add `test_validate_combat_system_required_error()` to `tests/engine/test_semantic_validator.py` — build a minimal content set with an adventure containing a `CombatStep` but no `CombatSystem` manifest; assert a `SemanticIssue` with `kind="no_combat_system"` is emitted.
- [x] 14.2 Add `test_validate_choice_mode_with_player_damage_formulas_error()` — `CombatSystemSpec(player_turn_mode="choice", player_damage_formulas=[...])` must produce an error.
- [x] 14.3 Add `test_validate_initiative_missing_formula_error()` — `turn_order="initiative"` with no initiative formula fields must produce an error.
- [x] 14.4 Add `test_validate_enemy_stat_coverage_error()` — enemy manifest missing a stat key that appears in the system's `player_damage_formulas[*].target_stat` must produce an error.
- [x] 14.5 Add `test_validate_heal_enemy_deprecation_warning()` — `HealEffect(target="enemy")` in any adventure step must produce a `severity="warning"` issue.
- [x] 14.6 Add `test_validate_formula_syntax_error()` — a `DamageFormulaEntry.formula` with invalid Jinja2 must produce a `severity="error"` issue.
- [x] 14.7 Add `test_validate_target_stat_null_no_threshold_error()` — `DamageFormulaEntry(target_stat=None, threshold_effects=[])` must produce a hard error.

## 15. Tests — fixtures

- [x] 15.1 Create `tests/fixtures/content/combat-system-auto/` with a minimal valid `game.yaml`, `character_config.yaml`, one `CombatSystem` manifest (auto-default), and one enemy manifest using the new `stats` dict schema. This fixture is the baseline for combat loop integration tests.
- [x] 15.2 Create `tests/fixtures/content/combat-system-choice/` — same as above but with `player_turn_mode: "choice"`, a sample `SystemSkillEntry`, and at least one `Skill` manifest with `contexts: ["combat"]`.
- [x] 15.3 Create `tests/fixtures/content/combat-system-initiative/` — same baseline but with `turn_order: "initiative"` and both initiative formula fields.

## 16. Documentation

- [x] 16.1 Create `docs/authors/combat-systems.md` — full `CombatSystem` manifest reference: all `CombatSystemSpec` fields, `DamageFormulaEntry`, `CombatStatEntry`, `SystemSkillEntry`, `CombatStepOverrides`, lifecycle hooks, `turn_order` modes, initiative, `"simultaneous"` mode, `resolution_formulas`, `combat_stats`, formula globals, and per-step override syntax.
- [x] 16.2 Create `docs/authors/cookbook/combat-system-patterns.md` — five annotated patterns: (1) classic HP-based combat (auto mode); (2) choice-mode skill menu; (3) initiative-based turn order; (4) simultaneous-resolution (RPS example); (5) dice-pool mechanics using `rollpool`.
- [x] 16.3 Update `docs/authors/enemies.md`: replace the `hp`/`attack`/`defense`/`xp_reward` fields section with a **Combat Stats** section explaining `spec.stats` (dict of stat names to integer values) and `spec.on_defeat_effects`; add migration guidance for authors updating existing manifests.
- [x] 16.4 Update `docs/authors/skills.md`: add a **Combat Damage Formulas** subsection for `combat_damage_formulas`; update the `contexts` field description from a fixed enum to an arbitrary string list with a note that `"overworld"` is reserved.
- [x] 16.5 Update `docs/authors/items.md`: document the new `contexts: List[str]` field on `ItemSpec`, `combat_damage_formulas` on `ItemSpec`, and `combat_damage_formulas` on `EquipSpec`.
- [x] 16.6 Update `docs/authors/conditions.md`: add `enemy_stat` and `combat_stat` to the leaf condition types table; add a section explaining combat-context-only conditions and the `false`-with-warning behavior outside combat.
- [x] 16.7 Update `docs/authors/adventures.md`: document the new `combat_system` and `combat_overrides` fields on `CombatStep`; update the template context reference to replace `combat.enemy_hp` with `combat.enemy_stats`.
- [x] 16.8 Update `docs/authors/game-configuration.md`: document the `default_combat_system: str | None` field on `GameSpec`.
- [x] 16.9 Update `docs/dev/game-engine.md`: replace the current combat section with a description of the new `CombatSystem`-driven architecture; document `resolve_turn_order()`, `player_action_phase()`, `enemy_action_phase()`, `merge_overrides()`, and `resolution_formulas`; update the `CombatContext` fields table (`enemy_stats`, `combat_stats`); document the `CombatFormulaContext` dataclass.
- [x] 16.10 Update `docs/system-overview.md`: add `CombatSystem` to the manifest kinds table; update the combat step description to reference the manifest-driven architecture.
- [x] 16.11 Add `docs/authors/combat-systems.md` and `docs/authors/cookbook/combat-system-patterns.md` to the table of contents in `docs/authors/README.md`.
- [x] 16.12 Add entries for updated dev documentation to `docs/dev/README.md` as appropriate.
