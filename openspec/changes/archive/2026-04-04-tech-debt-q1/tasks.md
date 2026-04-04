# Tasks: Tech Debt Q1

## 1. Remove `base_adventure_count` (XS)

- [x] **1.1** Remove `base_adventure_count: int | None = None` field from `GameSpec` in `oscilla/engine/models/game.py`
  - _Acceptance: `GameSpec` no longer has the field; existing tests pass_
- [x] **1.2** Remove `base_adventure_count:` line from `content/testlandia/game.yaml`
- [x] **1.3** Remove `base_adventure_count:` line from `content/the-example-kingdom/game.yaml`
- [x] **1.4** Run `make tests` — confirm all checks pass

---

## 2. Remove Condition Shorthand Syntax (S)

- [x] **2.1** Delete `_LEAF_MAPPINGS`, `_DICT_LEAVES`, `_BRANCH_KEYS` constants and `normalise_condition()` function from `oscilla/engine/models/base.py`
  - _Acceptance: no `normalise_condition` symbol exists in `base.py`_
- [x] **2.2** Remove `normalise_condition` from the import line in `oscilla/engine/loader.py`
- [x] **2.3** Delete `_normalise_manifest_conditions()`, `_normalise_step()`, `_normalise_branch()` from `oscilla/engine/loader.py` and remove all call sites of `_normalise_manifest_conditions` in the parse loop
  - _Acceptance: loader.py no longer calls any normalisation helper on raw condition fields_
- [x] **2.4** Migrate `content/the-example-kingdom/regions/wilderness/wilderness.yaml`: replace `unlock: {level: 3}` with `unlock: {type: level, value: 3}`
- [x] **2.5** Audit all manifests in `content/` for any remaining bare-key conditions and migrate them to the explicit form
  - _Search: `grep -rn "^\s\+\(level\|milestone\|item\|class\|pronouns\|item_equipped\|item_held_label\|any_item_equipped\|character_stat\|iteration\|enemies_defeated\|locations_visited\|adventures_completed\|skill\):" content/ --include="*.yaml"`_
- [x] **2.6** Write test in `tests/engine/test_loader_condition_shorthand.py` verifying that a bare-key condition in a manifest produces a `LoadError` (not a silent load)
  - _See design.md "Complete test examples" for the full test function_
- [x] **2.7** Audit `docs/authors/conditions.md`: remove all shorthand examples, add explicit-form callout
- [x] **2.8** Audit `docs/authors/world-building.md`: replace any `unlock: {level: N}` shorthand examples with explicit form
- [x] **2.9** Audit `docs/authors/adventures.md`: replace any shorthand condition examples
- [x] **2.10** Audit all remaining files in `docs/authors/` for shorthand usage (`grep -rn "^\s\+level:\|^\s\+milestone:" docs/authors/`)
- [x] **2.11** Run `make tests` — confirm all checks pass

---

## 3. Shared Loot Tables and Enemy Loot Reference (S)

- [x] **3.1** Create `oscilla/engine/models/loot_table.py` with `LootEntry`, `LootTableSpec`, and `LootTableManifest` as specified in design.md
  - _Acceptance: `LootTableManifest` validates a correct YAML dict; `LootEntry` with `quantity` field validates_
- [x] **3.2** Update `oscilla/engine/models/enemy.py`: remove local `LootEntry` class, import `LootEntry` from `loot_table.py`
  - _Acceptance: `EnemySpec.loot` still uses `List[LootEntry]` from the unified schema_
- [x] **3.3** Update `oscilla/engine/models/adventure.py`:
  - Import `LootEntry` from `loot_table.py` (remove `ItemDropEntry` class)
  - Add `loot_ref: str | None` field to `ItemDropEffect`
  - Change `loot` to `List[LootEntry] | None` (defaulting to `None`)
  - Add `model_validator` enforcing exactly one of `loot` / `loot_ref`
  - _Acceptance: `ItemDropEffect(type="item_drop", loot_ref="x")` validates; both fields raises error; neither raises error_
- [x] **3.4** Add `loot_tables: KindRegistry[LootTableManifest]` to `ContentRegistry` in `oscilla/engine/registry.py`
- [x] **3.5** Add `LootTable` to the kind dispatch match block in `oscilla/engine/registry.py`
- [x] **3.6** Add `resolve_loot_entries(loot_ref)` method to `ContentRegistry` (see design.md for full implementation)
- [x] **3.7** Register `LootTable` kind in `oscilla/engine/loader.py` parse loop (alongside existing kind handlers)
- [x] **3.8** Add `_validate_loot_refs()` cross-reference validation function to `oscilla/engine/loader.py` and call it in the post-load validation pass (see design.md for full implementation)
- [x] **3.9** Update `oscilla/engine/steps/effects.py`:
  - Add `_resolve_loot_list()` helper function
  - Update template resolution block for `ItemDropEffect` to preserve `loot_ref`
  - Update `ItemDropEffect` match case to use `_resolve_loot_list()` and apply `entry.quantity`
- [x] **3.10** Write tests in `tests/engine/test_loot_ref.py` covering:
  - `loot_ref` resolving to a `LootTable` manifest
  - `loot_ref` resolving to an enemy
  - Unknown `loot_ref` logs error and skips drop
  - Both `loot` + `loot_ref` raises `ValidationError`
  - Neither raises `ValidationError`
  - `quantity > 1` grants correct item count
  - _See design.md "Complete test examples" for full test functions_
- [x] **3.11** Update `docs/authors/items.md`: document `loot_ref` field, named loot tables, enemy-name references, `quantity` field
- [x] **3.12** Run `make tests` — confirm all checks pass

---

## 4. Quest Activation Engine (S)

- [x] **4.1** Create `oscilla/engine/quest_engine.py` with `_advance_quests_silent()` and `evaluate_quest_advancements()` (see design.md for complete implementations)
- [x] **4.2** Add `completion_effects: List[Effect] = []` to `QuestStage` in `oscilla/engine/models/quest.py`
  - Add `model_rebuild()` call at module bottom to resolve `Effect` forward reference
  - Update `validate_stage_graph` to reject `completion_effects` on non-terminal stages
  - _Acceptance: non-terminal stage with completion_effects raises ValueError; terminal stage accepts them_
- [x] **4.3** Add `QuestActivateEffect` model to `oscilla/engine/models/adventure.py`
  - Add to `Effect` union
  - _Acceptance: `QuestActivateEffect(type="quest_activate", quest_ref="x")` validates_
- [x] **4.4** Update `oscilla/engine/steps/effects.py`:
  - Import `QuestActivateEffect`
  - Add `quest_activate` case to match block in `run_effect`
  - Modify `MilestoneGrantEffect` case to call `await evaluate_quest_advancements(...)` after granting
  - _Acceptance: `quest_activate` on unknown ref logs error + TUI message; on valid ref adds to active_quests_
- [x] **4.5** Update `oscilla/engine/session.py`: call `_advance_quests_silent(player=state, registry=registry)` after `CharacterState` is restored from the database
- [x] **4.6** Write tests in `tests/engine/test_quest_engine.py` (see design.md for complete test functions):
  - `_advance_quests_silent` advances stage when milestone present
  - `_advance_quests_silent` does not advance when milestone absent
  - `evaluate_quest_advancements` fires completion effects and marks quest complete
  - Chained multi-stage advancement in single pass
  - Active quest with missing registry entry logs warning, does not crash
- [x] **4.7** Write tests in `tests/engine/test_effects_quest.py` (see design.md for complete test functions):
  - `quest_activate` with unknown ref shows error
  - `quest_activate` when already active is no-op
  - `quest_activate` when already completed is no-op
  - `quest_activate` valid ref sets active_quests entry and calls TUI
- [x] **4.8** Create `docs/authors/quests.md` covering:
  - Quest manifest structure (stages, `advance_on`, `next_stage`, `terminal`, `completion_effects`)
  - `quest_activate` effect with YAML example
  - Stage graph rules (no `advance_on` on terminal, no `completion_effects` on non-terminal)
  - Worked example: two-stage quest from activation through completion
  - Note on load-time re-evaluation behavior
- [x] **4.9** Update `docs/authors/README.md`: add `quests.md` entry to the table of contents
- [x] **4.10** Update `docs/authors/adventures.md`: add `quest_activate` to the effects reference section
- [x] **4.11** Update `docs/dev/game-engine.md`: add section on quest progression architecture, `quest_engine.py` module roles, call sites
- [x] **4.12** Run `make tests` — confirm all checks pass

---

## 5. Testlandia Content (all items)

- [x] **5.1** Create `content/testlandia/loot-tables/test-loot.yaml` — standalone LootTable with two entries (see design.md Testlandia Integration for YAML)
- [x] **5.2** Create `content/testlandia/quests/test-quest.yaml` — three-stage quest with `advance_on` and `completion_effects` (see design.md)
- [x] **5.3** Create `content/testlandia/adventures/test-quest-start.yaml` — applies `quest_activate` and `milestone_grant` for stage-one (see design.md)
- [x] **5.4** Create `content/testlandia/adventures/test-quest-finish.yaml` — grants milestone for stage-two completion (see design.md)
- [x] **5.5** Wire `test-quest-start` and `test-quest-finish` adventures into an appropriate testlandia location so they appear in the adventure menu
- [ ] **5.6** Run `docker compose up` and manually play through the quest chain: start quest, verify TUI messages, complete quest, verify completion item received and milestone set
- [x] **5.7** Run `make tests` — confirm all checks pass

---

## 6. Documentation audit and cleanup

- [x] **6.1** Verify `docs/dev/README.md` table of contents is accurate and complete after all changes
- [x] **6.2** Check `docs/authors/README.md` for completeness (quests.md added, all existing entries still accurate)
- [x] **6.3** Search all `docs/` for any remaining references to `base_adventure_count` and remove them
- [x] **6.4** Run `make tests` — confirm final clean pass across all checks (pytest, ruff, black, mypy, dapperdata, tomlsort)
