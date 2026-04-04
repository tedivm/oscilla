## Why

Four high-priority tech debt items are silently misleading content authors and engine developers: quests can be modeled but never progress, the condition shorthand creates inconsistent authoring syntax, enemy loot tables are declared but never actually used by the engine, and `base_adventure_count` is a dead field that implies behavior that does not exist. Addressing these together removes the gap between what the engine promises authors and what it delivers.

## What Changes

- **Quest activation engine**: Add a `quest_activate` effect type so adventures can start quests explicitly. Wire `grant_milestone()` to check active quests and advance stages whose `advance_on` list includes the granted milestone. Add a terminal-stage effect list so completing a quest can trigger item drops, stat changes, or milestones. Re-evaluate quest advancement on character/game load so state is consistent even if milestones were granted before the quest was active.

- **Condition shorthand removal** **BREAKING**: Remove `normalise_condition()`, `_LEAF_MAPPINGS`, and `_DICT_LEAVES` from `oscilla/engine/models/base.py`. The loader will hard-error if a bare-key condition (e.g. `{level: 3}`) is encountered — the explicit `{type: level, value: 3}` form is required. Migrate the one remaining shorthand usage in `content/` and update all author documentation to use only the explicit form.

- **Shared loot tables and enemy loot reference**: Introduce a named `LootTable` manifest kind so loot definitions can be declared once and referenced from multiple sources. Reconcile the `LootEntry` / `ItemDropEntry` schema split — a single `LootEntry` type with `item`, `weight`, and optional `quantity` fields will be used everywhere. Add a `loot_ref` field on `ItemDropEffect` that points to a named loot table (enemy or standalone). The enemy `loot` field continues to work and implicitly defines an anonymous loot table addressed by the enemy name.

- **Remove `base_adventure_count`** **BREAKING**: Delete the `base_adventure_count` field from `GameSpec` and from both content packages. The field was never read by the engine and its intent is not being carried forward.

## Capabilities

### New Capabilities

- `quest-engine`: Quest activation via explicit effect, milestone-triggered stage advancement, terminal-stage completion effects, and quest state re-evaluation on load.
- `loot-tables`: Named standalone loot tables as a manifest kind, reconciled loot entry schema, and `loot_ref` referencing from `ItemDropEffect`.

### Modified Capabilities

- `condition-evaluator`: Remove shorthand syntax support entirely — only the explicit `type:`-tagged form is valid. **BREAKING** for any content using bare-key conditions.
- `manifest-system`: Remove `base_adventure_count` from `GameSpec`. **BREAKING** for any content package declaring this field.

## Impact

- `oscilla/engine/models/base.py`: Remove `normalise_condition()`, `_LEAF_MAPPINGS`, `_DICT_LEAVES`.
- `oscilla/engine/models/quest.py`: Add completion effects to `QuestStage`.
- `oscilla/engine/models/adventure.py`: Add `quest_activate` effect type; add `loot_ref` field to `ItemDropEffect`; reconcile `ItemDropEntry` schema.
- `oscilla/engine/models/enemy.py`: Update `LootEntry` to match unified schema.
- `oscilla/engine/models/game.py`: Remove `base_adventure_count` from `GameSpec`.
- `oscilla/engine/character.py`: `grant_milestone()` triggers quest stage evaluation.
- `oscilla/engine/steps/effects.py`: Implement `quest_activate` effect handler and `loot_ref` resolution.
- `oscilla/engine/loader.py`: Register `LootTable` manifest kind; hard-error on bare-key conditions; validate `loot_ref` cross-references at load time.
- `oscilla/engine/registry.py`: Add loot table registry lookup.
- `content/the-example-kingdom/regions/wilderness/wilderness.yaml`: Migrate shorthand condition to explicit form.
- `content/` both packages: Remove `base_adventure_count` field.
- `docs/authors/conditions.md`, `docs/authors/world-building.md`, `docs/authors/adventures.md`, and all other author docs: Full audit for shorthand usage and consistency.
- `docs/authors/`: New or updated docs for quests and loot tables.
- `tests/`: New tests covering quest advancement, loot table resolution, condition hard errors.

### Testlandia QA Content

The following testlandia additions enable manual QA of all four items:

**Quest Engine:**

- A new `LootTable` manifest (`testlandia/loot-tables/test-loot.yaml`) with two weighted entries.
- A new `Quest` manifest (`testlandia/quests/test-quest.yaml`) with three stages: `stage-one` → `stage-two` → `complete` (terminal). `stage-one` advances on milestone `test-quest-stage-one-done`. `stage-two` advances on `test-quest-stage-two-done`. The terminal stage grants a unique item via completion effects.
- A new adventure (`testlandia/adventures/test-quest-start.yaml`) that applies `quest_activate: test-quest` and then grants `test-quest-stage-one-done`, immediately advancing the quest to `stage-two`. Used to verify activation and first advancement in a single run.
- A second adventure (`testlandia/adventures/test-quest-finish.yaml`) that grants `test-quest-stage-two-done`, advancing to terminal and triggering completion effects.

**Loot Tables:**

- The `test-loot` standalone loot table referenced by `test-quest-finish.yaml` via `loot_ref: test-loot` so the completion drop can be verified.

**Condition Hard Error (validated at load, not runtime):**

- A note in the testlandia dev guide confirming that introducing a shorthand condition in any manifest will produce a load error, not a warning.

**`base_adventure_count` removal:**

- Already covered by removing the field from `testlandia/game.yaml`.
