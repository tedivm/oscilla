## Why

The item system has slots, stat modifiers, and skill grants but lacks the expressive authoring primitives needed for richer gear-driven gameplay: items cannot require prerequisites to equip, items cannot carry display tags the TUI can style, charged items cannot self-deplete, and there is no way to declare passive effects that activate or deactivate automatically as character state changes. Implementing these four roadmap features together is significantly cheaper than separately because they all share the same new condition predicates and loader infrastructure.

## What Changes

- Introduce a `LoadWarning` tier to the content loader: non-fatal issues that let the game run but surface clearly in `oscilla validate` and are structured enough for AI tooling to suggest fixes automatically.
- Add `--strict` flag to `oscilla validate` that promotes warnings to errors (CI-friendly).
- Add three new condition predicates — `item_equipped`, `item_held_label`, `any_item_equipped` — usable everywhere conditions appear.
- Fix a latent bug: `ItemCondition` (type: `item`) currently only checks stacks; it must also check non-stackable instances.
- Add `labels: List[str]` to `ItemSpec` and `item_labels` to `GameSpec` (author-defined display vocabulary). Undeclared label references produce a `LoadWarning`.
- Add `requires: Condition | None` to `EquipSpec` so items can declare equip prerequisites evaluated against base stats.
- Add `passive_effects` to `GameSpec`: each entry declares a condition + stat_modifiers + skill_grants that are applied dynamically whenever the condition is true. Passive effects drive `effective_stats()` and `available_skills()`.
- Add `charges: int | None` to `ItemSpec` and `charges_remaining: int | None` to `ItemInstance`. Each use decrements `charges_remaining`; the instance is removed when charges reach 0. **Validation error** if `charges` is combined with `consumed_on_use: true` or `stackable: true`.
- Update the `design-philosophy.md` to document the validation warning tier and its intent as an author-support tool.

## Capabilities

### New Capabilities

- `item-labels`: Author-defined label vocabulary for items, with display rules in `game.yaml` and three-surface access (conditions, templates, TUI).
- `item-requirements`: `requires` field on `EquipSpec` using the standard condition evaluator; enforced in TUI equip action.
- `item-charges`: `charges` on `ItemSpec` with per-instance `charges_remaining` tracking in `ItemInstance`.
- `passive-effects`: `passive_effects` declaration in `GameSpec`; evaluated continuously in `effective_stats()` and `available_skills()`.
- `load-warnings`: `LoadWarning` dataclass, warning collection in `load()` / `load_games()`, display in `validate` CLI, `--strict` flag.

### Modified Capabilities

- `condition-evaluator`: Three new predicate types added to the `Condition` union (`item_equipped`, `item_held_label`, `any_item_equipped`); fix `ItemCondition` instance-checking bug.
- `item-system`: `ItemSpec` gains `labels` and the `EquipSpec` gains `requires`; `ItemInstance` gains `charges_remaining`; new cross-reference validations for labels, prerequisites, and charges constraints.
- `item-skill-grants`: `available_skills()` must also loop `passive_effects` from the game manifest; no new fields on `ItemSpec` but the computation expands.

## Impact

- `oscilla/engine/models/base.py` — three new condition models + Condition union update + YAML normaliser entries
- `oscilla/engine/models/item.py` — `ItemSpec`, `EquipSpec`, `ItemInstance` field additions + validators
- `oscilla/engine/models/game.py` — `GameSpec` gains `item_labels` and `passive_effects`
- `oscilla/engine/conditions.py` — three new `case` branches in `evaluate()`
- `oscilla/engine/character.py` — `effective_stats()` and `available_skills()` loop passive effects
- `oscilla/engine/loader.py` — `LoadWarning` class, warning collection pipeline, label cross-reference check
- `oscilla/engine/steps/effects.py` — `UseItemEffect` charges decrement logic
- `oscilla/cli.py` — `validate` command warning display + `--strict` flag
- `docs/dev/design-philosophy.md` — new section on validation as author support
- `docs/authors/content-authoring.md` — document labels, requirements, charges, passive effects
- `content/testlandia/` — new items, adventures, and `game.yaml` entries to demonstrate and QA all new features
