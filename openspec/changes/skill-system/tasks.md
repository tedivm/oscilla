## 1. Data Models

- [x] 1.1 Create `oscilla/engine/models/skill.py` with `SkillCost`, `SkillCooldown`, `SkillSpec`, and `SkillManifest`; no `PeriodicEffect` or modifier classes (those live in `buff.py`)
- [x] 1.1a Create `oscilla/engine/models/buff.py` with `DamageReductionModifier`, `DamageAmplifyModifier`, `DamageReflectModifier`, `DamageVulnerabilityModifier` (each with `percent: int | str` and per-type `_validate_percent` field validator), `CombatModifier` (discriminated union), `BuffSpec` (including `variables: Dict[str, int]`, `modifiers`, `per_turn_effects`, `require_tick_or_modifier` validator, and `validate_variable_refs` validator), and `BuffManifest`
- [x] 1.2 Add `SkillGrantEffect`, `DispelEffect`, and `ApplyBuffEffect` (with `target` and `variables: Dict[str, int]` fields) to `oscilla/engine/models/adventure.py` and update the `Effect` union
- [x] 1.3 Add `target: Literal["player", "enemy"] = "player"` to `StatChangeEffect` and `HealEffect` in `adventure.py`
- [x] 1.4 Add `target: Literal["player"] = "player"` to `StatSetEffect` (enemy targeting forbidden) in `adventure.py`
- [x] 1.5 Add `SkillCondition` to `oscilla/engine/models/base.py` and update the `Condition` union
- [x] 1.6 Add `SkillResourceBinding` and `SkillCategoryRule` classes to `oscilla/engine/models/character_config.py`
- [x] 1.7 Add `skill_resources` and `skill_category_rules` fields to `CharacterConfigSpec`
- [x] 1.8 Add `grants_skills_equipped`, `grants_skills_held` (both `List[str]`) and `grants_buffs_equipped`, `grants_buffs_held` (both `List[BuffGrant]`) to `ItemSpec` in `oscilla/engine/models/item.py`; add `BuffGrant` model (`buff_ref: str`, `variables: Dict[str, int] = {}`)
- [x] 1.9 Add `EnemySkillEntry` class and `skills` and `skill_resources` fields to `EnemySpec` in `oscilla/engine/models/enemy.py`

## 2. Character State

- [x] 2.1 Add `known_skills: Set[str]` and `skill_cooldowns: Dict[str, int]` fields to `CharacterState` in `oscilla/engine/character.py`
- [x] 2.2 Implement `available_skills(registry) -> Set[str]` method on `CharacterState`
- [x] 2.3 Implement `grant_skill(skill_ref, registry) -> bool` method with category rule enforcement
- [x] 2.4 Implement `tick_skill_cooldowns() -> None` method
- [x] 2.5 Update `CharacterState.to_dict()` to include `known_skills` and `skill_cooldowns`
- [x] 2.6 Update `CharacterState.from_dict()` to restore `known_skills` and `skill_cooldowns` with empty defaults

## 3. Combat Context

- [x] 3.1 Create `oscilla/engine/combat_context.py` with `ActiveCombatEffect` (including `label` set from `buff_manifest.metadata.name` and `modifiers: List[CombatModifier]` fields; import `CombatModifier` from `buff.py`) and `CombatContext` dataclasses
- [x] 3.2 Write unit tests for `CombatContext` initialization from `EnemySpec.skill_resources`

## 4. Content Registry

- [x] 4.1 Add `buffs: KindRegistry[BuffManifest]` and `skills: KindRegistry[SkillManifest]` to `ContentRegistry` in `oscilla/engine/registry.py`
- [x] 4.2 Add `"Skill"` and `"Buff"` cases to `ContentRegistry.build()` to register Skill and Buff manifests

## 5. Conditions

- [x] 5.1 Add `SkillCondition` import and `case SkillCondition(...)` handler to `oscilla/engine/conditions.py`
- [x] 5.2 Implement `mode: "learned"` branch (checks `known_skills` directly)
- [x] 5.3 Implement `mode: "available"` branch (calls `available_skills(registry)`)

## 6. Effect Dispatcher

- [x] 6.1 Add `combat: CombatContext | None = None` parameter to `run_effect()` in `oscilla/engine/steps/effects.py`
- [x] 6.2 Add `SkillGrantEffect` handler in `run_effect()`
- [x] 6.3 Update `StatChangeEffect` handler to route `target="enemy"` through `CombatContext.enemy_hp`
- [x] 6.4 Update `HealEffect` handler to route `target="enemy"` through `CombatContext.enemy_hp`
- [x] 6.5 Add warning + skip behavior when `target="enemy"` and `combat=None`
- [x] 6.6 Add `DispelEffect` handler in `run_effect()` that removes matching entries from `CombatContext.active_effects` by `label` and `target`; log DEBUG and skip when `combat=None`
- [x] 6.7 Add `ApplyBuffEffect` handler in `run_effect()` that: (1) merges `buff_spec.variables` with `effect.variables`; (2) resolves string `percent` refs to concrete ints via `_resolve_percent`; (3) constructs an `ActiveCombatEffect` with resolved modifiers; (4) logs WARNING and skips when `combat=None`

## 7. Combat Loop

- [x] 7.1 Restructure `run_combat()` in `oscilla/engine/steps/combat.py` to construct and use `CombatContext`
- [x] 7.2 Implement `_tick_active_effects()` helper and integrate periodic effect ticking at the top of each round
- [x] 7.3 Implement `_use_skill_in_combat()` helper with all validation checks (cooldown, resource, requires condition); dispatch `use_effects` via `run_effect()` (buffs granted through `apply_buff` effect, not inline `periodic_effect`)
- [x] 7.4 Extend combat menu to include available combat skills between Attack and Flee
- [x] 7.5 Implement `_enemy_skill_phase()` helper and integrate at end of each round; dispatch enemy `use_effects` via `run_effect()` (buffs granted through `apply_buff` effect)
- [x] 7.6 Mirror `CombatContext.enemy_hp` back to `step_state` each round for persistence
- [x] 7.7 Implement `_apply_damage_amplify()`, `_apply_incoming_modifiers()`, and `_apply_reflect()` pure helpers in `oscilla/engine/steps/combat.py`
- [x] 7.8 Integrate modifier helpers into `run_combat()` basic attack (amplify) and enemy retaliation (reduction, vulnerability, reflect) paths
- [x] 7.9 At combat entry in `run_combat()`, iterate `grants_buffs_equipped` and `grants_buffs_held` (now `List[BuffGrant]`) from player's equipped and held items; call `run_effect(ApplyBuffEffect(buff_ref=grant.buff_ref, target="player", variables=grant.variables))` for each
- [x] 7.10 Add `_resolve_percent(v: int | str, resolved_vars: Dict[str, int]) -> int` helper in `run_effect()` or a shared utility

## 8. Loader Updates

- [x] 8.1 Add `"Skill"` and `"Buff"` manifest kinds to `MANIFEST_REGISTRY` / kind dispatch in `oscilla/engine/loader.py`
- [x] 8.2 Implement `_validate_skill_refs()` in `loader.py` checking items, enemies, and effects
- [x] 8.3 Call `_validate_skill_refs()` at the end of `validate_references()`
- [x] 8.4 Add `skill_resource` binding validation in `CharacterConfig` (stat and max_stat must reference declared stats)
- [x] 8.5 Implement `_validate_buff_refs()` in `loader.py` checking: (a) `apply_buff` refs in skill/item `use_effects` against known buffs; (b) variable override keys against the buff's declared `variables`; (c) `grants_buffs_equipped`/`grants_buffs_held` buff refs and variable override keys; call at end of `validate_references()`
- [x] 8.6 Add `validate_variable_refs` model validator on `BuffSpec` (mode="after") ensuring all string `percent` refs in `modifiers` are declared in `variables`

## 9. TUI Protocol

- [x] 9.1 Add `show_skill_menu(skills: List[Dict[str, Any]]) -> int | None` to `TUICallbacks` protocol in `oscilla/engine/pipeline.py`
- [x] 9.2 Add `show_skill_menu` stub to `MockTUI` in `tests/engine/conftest.py`
- [x] 9.3 Implement `open_actions_screen(player, registry, tui)` async function in `oscilla/engine/session.py` (or new `oscilla/engine/actions.py`)

## 10. Database

- [x] 10.1 Run `make create_migration MESSAGE="add skill system tables"` to generate migration file
- [x] 10.2 Edit the generated migration to add `character_iteration_skills` and `character_iteration_skill_cooldowns` tables
- [x] 10.3 Add `CharacterIterationSkill` and `CharacterIterationSkillCooldown` ORM models to `oscilla/models/character_iteration.py`
- [x] 10.4 Add `skill_rows` and `skill_cooldown_rows` relationships to `CharacterIterationRecord`
- [x] 10.5 Update the character persistence service in `oscilla/services/character.py` to save/load `known_skills` and `skill_cooldowns`

## 11. Tests — Unit

- [x] 11.1 Create `tests/engine/test_skill_unit.py` with model validation tests (`SkillSpec`, `SkillCooldown`, `BuffSpec`)
- [x] 11.1a Add `BuffSpec` validator tests: reject empty `per_turn_effects` AND empty `modifiers`; accept modifier-only; accept tick-only; accept both combined
- [x] 11.1b Add `CombatModifier` discriminated union tests for all four types (`damage_reduction`, `damage_amplify`, `damage_reflect`, `damage_vulnerability`)
- [x] 11.1c Add `_apply_damage_amplify`, `_apply_incoming_modifiers`, `_apply_reflect` unit tests covering: no active modifiers, single modifier, stacked modifiers, reduction + vulnerability combined, zero base damage, and reflect target=enemy
- [x] 11.1d Add `BuffSpec.variables` unit tests: `percent: int` resolves directly; `percent: variable_name` resolves from variables dict; undeclared variable name in modifier raises `validate_variable_refs` error
- [x] 11.1e Add `CombatModifier` field validator tests: `percent: str` passes (variable name); `percent: int` within range passes; `percent: int` out of range raises error
- [x] 11.2 Add `SkillCondition` default mode test and mode validation tests
- [x] 11.3 Add `CharacterState.grant_skill()` tests (new skill, duplicate, category max_known, exclusive_with)
- [x] 11.4 Add `available_skills()` tests (no registry, multiple sources)
- [x] 11.5 Add `tick_skill_cooldowns()` tests (decrement, expiry, multiple skills)
- [x] 11.6 Add `CharacterState` serialization roundtrip tests for `known_skills` and `skill_cooldowns`

## 12. Tests — Integration Fixtures

- [x] 12.1 Create `tests/fixtures/content/skill-combat/` directory with test manifests: `test-buff-dot.yaml` (per_turn_effects), `test-buff-shield.yaml` (damage_reduction), `test-buff-rage.yaml` (damage_amplify), `test-buff-thorns.yaml` (damage_reflect), `test-skill-fireball.yaml` (apply_buff), `test-skill-shield.yaml` (apply_buff), `test-skill-overworld.yaml`, `test-skill-poison.yaml`, `test-skill-curse.yaml`
- [x] 12.2 Add `test-enemy.yaml` with `skills` list referencing `test-poison` and `skill_resources`
- [x] 12.3 Add `test-character-config.yaml` with `skill_resources` binding `mana` to stats
- [x] 12.4 Add `test-game.yaml`, `test-region-root.yaml`, `test-location.yaml`, and `test-combat.yaml` adventure for this fixture set

## 13. Tests — Integration

- [x] 13.1 Create `tests/engine/test_skill_integration.py` with loader, SkillGrantEffect via run_effect, SkillCondition evaluation, and enemy-targeting effect tests
- [x] 13.2 Add test for stat_change `target="enemy"` with CombatContext reduces enemy HP
- [x] 13.3 Add test for stat_change `target="enemy"` without CombatContext is skipped
- [x] 13.4 Add test for loader rejecting items with unknown skill refs
- [x] 13.5 Add test for loader rejecting `apply_buff` refs pointing to non-existent Buff manifests
- [x] 13.5a Add test for loader rejecting `apply_buff` effects with unknown variable override keys
- [x] 13.6 Add test for loader rejecting `grants_buffs_equipped`/`grants_buffs_held` refs pointing to non-existent Buff manifests
- [x] 13.6a Add test for loader rejecting `grants_buffs_equipped`/`grants_buffs_held` with unknown variable override keys

## 14. Tests — Combat Pipeline

- [x] 14.1 Create `tests/engine/test_combat_skills.py` with combat loop skill use tests
- [x] 14.2 Add test for player using skill in combat (damage applied, resource deducted)
- [x] 14.3 Add test for turn-scope cooldown blocking reuse
- [x] 14.4 Add test for buff ticking (enemy HP reduced each tick, effect expires)
- [x] 14.5 Add test for enemy skill firing on scheduled turn
- [x] 14.6 Add test for `apply_buff` effect granting buff with correct `label` matching buff manifest name
- [x] 14.7 Add test for `dispel` removing active buff by label
- [x] 14.8 Add test for `grants_buffs_equipped` — equipped item applies buff at combat start
- [x] 14.9 Add test for `grants_buffs_held` — held (unequipped) item applies buff at combat start
- [x] 14.10 Add test for `grants_buffs_equipped` with `variables` override — buff resolves overridden percent at combat start (e.g. `master-thorns-sword` with `reflect_percent: 60` produces modifier with `percent=60`)
- [x] 14.11 Add test for `apply_buff` effect with `variables` override — buff resolves overridden percent during combat (dispatch `ApplyBuffEffect(buff_ref="thorns", variables={"reflect_percent": 60})`)

## 15. Documentation

- [x] 15.1 Create `docs/authors/skills.md` covering the Skill manifest reference, Buff manifest reference, YAML examples, `grants_skills_equipped`/`held` and `grants_buffs_equipped`/`held` on items, CharacterConfig `skill_resources` and `skill_category_rules`, enemy skills, and equipment buff grants
- [x] 15.2 Update `docs/authors/content-authoring.md` to add a Skills section and update the manifest kinds table
- [x] 15.3 Update `docs/dev/game-engine.md` to cover CombatContext lifecycle, `available_skills()` contract, cooldown tracking, SkillCondition modes, and `run_effect()` combat parameter
- [x] 15.4 Add `skills.md` row to the table of contents in `docs/authors/README.md`
