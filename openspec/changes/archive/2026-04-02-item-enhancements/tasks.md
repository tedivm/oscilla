## 1. LoadWarning Infrastructure

- [x] 1.1 Add `LoadWarning` dataclass to `oscilla/engine/loader.py` with `file: Path`, `message: str`, and `suggestion: str = ""` fields; add `__str__` that appends the suggestion when non-empty
- [x] 1.2 Change `load()` return type from `ContentRegistry` to `Tuple[ContentRegistry, List[LoadWarning]]` and thread the warnings accumulator through all internal helpers
- [x] 1.3 Change `load_games()` return type to `Tuple[Dict[str, ContentRegistry], Dict[str, List[LoadWarning]]]` and aggregate per-game warnings
- [x] 1.4 Update the `validate` CLI command to unpack the new tuple, print each warning in yellow with a `⚠` prefix, and keep exit code 0
- [x] 1.5 Add `--strict` flag to `validate` command: when set, re-print warnings in red and exit 1 if any are present
- [x] 1.6 Update the `play` / `start` CLI path to unpack the tuple and log each warning via `logger.warning()`

## 2. Fix Existing ItemCondition Bug

- [x] 2.1 Fix the `item` condition evaluator in `oscilla/engine/conditions.py` to check both `player.stacks` (stackable items) and `player.instances` (non-stackable items), not just stacks

## 3. New Condition Predicates

- [x] 3.1 Add `ItemEquippedCondition` model to `oscilla/engine/models/base.py` with `type: Literal["item_equipped"]` and `item: str`; add `item_equipped` entry to `_LEAF_MAPPINGS`
- [x] 3.2 Add `ItemHeldLabelCondition` model to `oscilla/engine/models/base.py` with `type: Literal["item_held_label"]` and `label: str`; add `item_held_label` entry to `_LEAF_MAPPINGS`
- [x] 3.3 Add `AnyItemEquippedCondition` model to `oscilla/engine/models/base.py` with `type: Literal["any_item_equipped"]` and `label: str`; add `any_item_equipped` entry to `_LEAF_MAPPINGS`
- [x] 3.4 Add all three new types to the `Condition` discriminated union in `models/base.py`
- [x] 3.5 Add `case ItemEquippedCondition` branch in `conditions.py` `evaluate()` — true when the named item is in `player.instances` with `equipped=True`
- [x] 3.6 Add `case ItemHeldLabelCondition` branch in `conditions.py` `evaluate()` — true when any instance or stack matches the given label (requires registry lookup)
- [x] 3.7 Add `case AnyItemEquippedCondition` branch in `conditions.py` `evaluate()` — true when any equipped instance matches the given label (requires registry lookup)
- [x] 3.8 Add `stat_source: Literal["base", "effective"] = "effective"` field to `CharacterStatCondition` in `models/base.py`
- [x] 3.9 Update `evaluate()` in `conditions.py` to accept `exclude_item: str | None = None`; update the `CharacterStatCondition` case to use `player.stats` when `stat_source == "base"` or registry is `None`, otherwise call `player.effective_stats(registry=registry, exclude_item=exclude_item)`; forward `exclude_item` unchanged through `AllCondition`, `AnyCondition`, and `NotCondition` recursive calls
- [x] 3.10 Update `effective_stats()` in `oscilla/engine/character.py` to accept `exclude_item: str | None = None`; skip any `ItemInstance` whose `item_ref` matches `exclude_item` during the equipment bonus loop

## 4. Item Labels

- [x] 4.1 Add `ItemLabelDef` model to `oscilla/engine/models/game.py` with `name: str`, `color: str = ""`, `description: str = ""`, and `sort_priority: int = 0`
- [x] 4.2 Add `item_labels: List[ItemLabelDef]` field (default empty list) to `GameSpec`
- [x] 4.3 Add `labels: List[str]` field (default empty list) to `ItemSpec` in `oscilla/engine/models/item.py`
- [x] 4.4 Add `levenshtein(a, b) -> int` to `oscilla/engine/string_utils.py` (two-row DP, O(m×n) time O(n) space, no new dependency); implement `_validate_labels()` in `loader.py` importing `levenshtein` from `string_utils` — iterate all loaded items, compare each label against declared `game.item_labels`, emit a `LoadWarning` for each undeclared label; use `levenshtein` to find the closest declared label and suggest it when distance ≤ 2 (catches single-character typos and transpositions like `legendery` → `legendary`, distance 1); populate `suggestion` with a "Did you mean X?" message when a match is found, or a generic "Add to item_labels" message otherwise
- [x] 4.5 Call `_validate_labels()` from `load()` and append its warnings to the accumulator

## 4b. TUI Label Rendering

- [x] 4b.1 In `InventoryScreen.compose()`, build a `label_color_map: Dict[str, str]` from `registry.game.spec.item_labels` (mapping label name to color string); use `""` sentinel (renders as `[dim]`) for labels absent from the map
- [x] 4b.2 Update the stack item render path to append colored label badges using Rich markup: for each label in `item_mf.spec.labels`, emit `[{color}]{label}[/{color}]` if color is set or `[dim]{label}[/dim]` if not
- [x] 4b.3 Update the instance item render path identically (same badge logic as 4b.2)
- [x] 4b.4 Sort items within each category before rendering: sort key is `(min_sort_priority(item_mf), display_name)` where `min_sort_priority` returns the lowest `sort_priority` of the item's labels from `item_labels`, or `float("inf")` when no labeled labels are found

## 5. Item Requirements

- [x] 5.1 Add `requires: Condition | None` field (default `None`) to `EquipSpec` in `oscilla/engine/models/item.py`
- [x] 5.2 In the equip handler in `InventoryScreen`, evaluate `requires` using `evaluate(condition, player, registry=registry, exclude_item=item_ref)` so the item's own stat bonuses are excluded from its own check (self-justification guard); if the condition fails, show a blocking message in the TUI and do not equip
- [x] 5.3 Extract a `validate_equipped_requires(player, registry) -> List[str]` helper in `character.py` (or a free function in `tui.py`) that returns a list of `instance_id` strings for equipped items whose `requires` is no longer satisfied; each item's `requires` must be evaluated with `exclude_item=item.name` to strip the item's own bonuses from the check
- [x] 5.4 Implement `cascade_unequip_invalid(player, registry) -> List[str]` that calls the validator in a fixed-point loop, unequipping each failing item and repeating until no further items fail; returns display names of all unequipped items for notification
- [x] 5.5 Call `cascade_unequip_invalid` inside `InventoryScreen` after every unequip action; show a TUI notification listing any cascade-unequipped items
- [x] 5.6 Call `cascade_unequip_invalid` inside engine step handlers that mutate `player.stats` (e.g., `stat_set`, `stat_modify` effects) and emit each cascade event as a TUI-visible message
- [x] 5.7 At session load (character restore), log a `logger.WARNING` for each equipped item whose `requires` evaluates false; do NOT unequip; add a TUI status-panel indicator for invalid equipped items

## 6. Item Charges

- [x] 6.1 Add `charges: int | None` field (default `None`) to `ItemSpec`; add a Pydantic model validator that raises a `ValueError` when both `charges` and `consumed_on_use: true` are set on the same item
- [x] 6.2 Add `charges_remaining: int | None` field (default `None`) to `ItemInstance` in `oscilla/engine/character.py`
- [x] 6.3 Update `add_instance()` to accept an optional `charges_remaining` parameter and set it from the item's `charges` field when not explicitly provided
- [x] 6.4 In `UseItemEffect`, after confirming item is usable: if `charges_remaining` is set, decrement it; if it reaches 0, remove the instance from the player's inventory before returning the effect result
- [x] 6.5 Ensure `charges_remaining: None` round-trips cleanly through the existing persistence schema (backward-compatible with saved `ItemInstance` dicts that lack the field)

## 7. Passive Effects

- [x] 7.1 Add `StatModifier` import/reuse or equivalent inline spec and define `PassiveEffect` model in `oscilla/engine/models/game.py` with `condition: Condition | None`, `stat_modifiers: List[StatModifier]`, and `skill_grants: List[SkillGrant]` (reuse existing types from `item.py`)
- [x] 7.2 Add `passive_effects: List[PassiveEffect]` field (default empty list) to `GameSpec`
- [x] 7.3 Update `effective_stats()` in `oscilla/engine/character.py` to loop `registry.game.passive_effects` and apply each effect's `stat_modifiers` when its condition is satisfied (evaluated with `registry=None`)
- [x] 7.4 Update `available_skills()` in `oscilla/engine/character.py` to yield each passive effect's `skill_grants` when its condition is satisfied (evaluated with `registry=None`)
- [x] 7.5 In `_validate_labels()` (or a new `_validate_passive_effects()` helper), emit a `LoadWarning` when any passive effect condition uses `item_held_label` or `any_item_equipped` (require a registry; will never trigger in passive evaluation); also emit a `LoadWarning` when any passive effect condition contains a `character_stat` node with `stat_source: effective` (the stat_source cannot be honored when registry=None is passed)

## 8. Tests

- [x] 8.1 Add tests for `LoadWarning` dataclass: field defaults, `__str__` output with and without suggestion
- [x] 8.2 Add tests confirming `load()` returns `(registry, [])` for a clean fixture package and `(registry, [warning])` when an undeclared label is present
- [x] 8.3 Add tests for the fixed `ItemCondition` evaluator: item in stacks, item in instances, item absent from both
- [x] 8.4 Add tests for each new condition predicate (`item_equipped`, `item_held_label`, `any_item_equipped`) using constructed `CharacterState` and registry fixtures
- [x] 8.5 Add tests for label validation: undeclared label triggers warning, close-match produces non-empty suggestion, declared label produces no warning
- [x] 8.11 Add tests for `InventoryScreen` label rendering: colored badge appears for declared label, dim badge appears for undeclared label, no badge for unlabeled item, items sorted by sort_priority within category
- [x] 8.6 Add tests for `EquipSpec.requires` at equip time: `stat_source: base` condition met allows equip; `stat_source: base` condition not met blocks equip even with gear boost; `stat_source: effective` (default) met via an equipped item's bonus allows equip; item's own stat bonus is excluded from its own check (self-justification guard — `exclude_item` prevents circular pass); passive effect gated on the item itself does not contribute during the check
- [x] 8.15 Add tests for `CharacterStatCondition.stat_source`: `stat_source: effective` uses `effective_stats()`; `stat_source: base` uses `player.stats`; `exclude_item` parameter strips named item's bonuses from effective stats without affecting other items; `stat_source: base` is unaffected by `exclude_item`
- [x] 8.12 Add tests for cascade unequip: unequipping an enabling item auto-unequips a dependent item; chain cascades (A enables B enables C) resolve correctly; items with no dependents do not trigger notifications
- [x] 8.13 Add tests for stat-change cascade: a stat-reducing effect auto-unequips items whose `requires` threshold is crossed; a stat-increasing effect does not trigger unequip
- [x] 8.14 Add tests for session-load preservation: a character loaded with an invalid equipped item remains unchanged; a `logger.WARNING` is emitted; no cascade occurs
- [x] 8.7 Add tests for the `charges` / `consumed_on_use` mutual exclusion validator (raises on load)
- [x] 8.8 Add tests for item charges: usage decrements `charges_remaining`, item removed at zero, `charges_remaining=None` is unaffected by usage (consumed_on_use path unchanged)
- [x] 8.9 Add tests for passive effects: `effective_stats()` includes passive modifiers when condition met and excludes them when condition fails; `available_skills()` yields passive grants when condition met
- [x] 8.10 Add tests for `oscilla validate --strict`: exits 0 with no warnings, exits 1 with warnings; standard validate (no flag) exits 0 with warnings

## 9. Documentation

- [x] 9.1 Add a **Load Warnings** section to `docs/dev/design-philosophy.md` explaining the three-tier diagnostic philosophy (hard error, warning, silent success) and the `suggestion` field for human-readable fix hints
- [x] 9.2 Update `docs/dev/game-engine.md` with `LoadWarning`, the updated `load()` signature, the new condition predicates, and passive effects
- [x] 9.3 Update `docs/dev/cli.md` with the `--strict` flag for `validate`
- [x] 9.4 Update `docs/authors/content-authoring.md` with sections for item labels (declaring in `game.yaml`, tagging items, using in conditions), item requirements (`requires` on `equip`), item charges (`charges` field, interaction with `consumed_on_use`), and passive effects (`passive_effects` in `game.yaml`)
- [x] 9.5 Add `docs/authors/passive-effects.md` as a dedicated author guide covering passive effect YAML structure, supported condition types, stat modifiers, and skill grants; add to `docs/authors/README.md` table of contents
- [x] 9.6 Add `docs/dev/load-warnings.md` documenting the `LoadWarning` dataclass, when to emit warnings vs. errors, the `suggestion` field contract for AI tools, and how to add new warning conditions; add to `docs/dev/README.md` table of contents

## 10. Testlandia Content

- [x] 10.1 Add `item_labels` list to `content/testlandia/game.yaml` with at minimum three test labels: `test-consumable`, `test-equippable`, and `test-legendary`; each with a description
- [x] 10.2 Add a `passive_effects` list to `content/testlandia/game.yaml` with one entry that grants a small stat bonus (e.g., +1 to any existing stat) when the player holds `test-legendary` label using `item_held_label` condition — this intentionally triggers the "passive condition uses label predicate" warning to validate that code path
- [x] 10.3 Create or update a testlandia item manifest (e.g., add a new item in the appropriate region YAML) with `labels: [test-consumable]`, `charges: 3`, and verify the charges decrement correctly after three uses in a play session
- [x] 10.4 Create or update a testlandia equippable item with `labels: [test-equippable]` and a `requires` condition based on an existing stat threshold (e.g., a level or stat check); verify that a character below the threshold cannot equip it
- [x] 10.5 Create or update a testlandia item with `labels: [test-legendary]` to serve as the trigger item for the passive effect defined in 10.2; confirm the passive stat bonus appears in character stats when the item is held
- [x] 10.6 Run `oscilla validate testlandia` and confirm the expected `LoadWarning` (for `item_held_label` inside passive effects) appears in yellow output with exit code 0; run with `--strict` and confirm exit code 1
