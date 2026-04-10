## Why

The current loot resolution system is a flat weighted list with a single `count` roll — expressive enough for trivial cases but inadequate for authors who need guaranteed drops, independent pools (pick 2 from weapons _and_ 2 from consumables), per-entry conditions, or template-driven quantities. Authors currently work around these limitations with multiple chained adventures or item-charge tricks. The `LootTable` manifest kind also exists but is not treated as a first-class content object alongside adventures, items, and enemies.

## What Changes

- **BREAKING** `LootTableSpec.loot` (flat `List[LootEntry]`) is replaced by `spec.groups: List[LootGroup]`. The existing `testlandia` `test-loot.yaml` must be updated.
- **BREAKING** `ItemDropEffect.loot` (inline flat list) and `ItemDropEffect.loot_ref` are both replaced by `ItemDropEffect.groups` (inline `List[LootGroup]`) and `ItemDropEffect.loot_ref` (still valid, now resolves to a `LootTable` manifest with `groups`). Authors must port all inline `loot:` lists in adventures to the new `groups:` syntax.
- **BREAKING** `ItemDropEffect.count` is removed. Count is now expressed per-group via `LootGroup.count`.
- New `LootGroup` model: `count: int | str`, `requires: Condition | None`, `entries: List[LootEntry]`.
- `LootEntry` gains `requires: Condition | None` and `amount: int | str` (replaces `quantity`). `weight` becomes optional (default `1`).
- `LootGroup.count` and `LootEntry.amount` are template-capable (`int | str`), following the same pattern as `StatChangeEffect.amount` and the retired `ItemDropEffect.count`.
- Template strings in loot groups and entries are precompiled at load time and resolved at runtime with `CharacterState` context, using `render_int`.
- `LootTable` is promoted to a first-class content object: `creatable=True` in `kinds.py`, scaffold template added, `oscilla content create loot-table` supported.
- `docs/authors/loot-tables.md` is created as the canonical author reference.
- Semantic validator is extended to validate condition refs in `LootGroup.requires` and `LootEntry.requires` across all three loot sources (LootTable manifests, enemy loot fields, adventure inline groups).

## Capabilities

### New Capabilities

- `loot-groups`: The `LootGroup` model and multi-group resolution algorithm — independent groups each with their own `count`, optional `requires`, and weighted `entries`.

### Modified Capabilities

- `loot-tables`: `LootTableSpec` replaces `loot:` with `groups:`. `LootEntry` gains `requires` and renames `quantity` → `amount`. `ItemDropEffect` replaces `loot`/`count` with `groups`/`loot_ref`. `LootTable` becomes creatable.

## Impact

- `oscilla/engine/models/loot_table.py` — new `LootGroup` model, revised `LootEntry`, revised `LootTableSpec`
- `oscilla/engine/models/adventure.py` — `ItemDropEffect` revised (remove `loot`, rename to `groups`)
- `oscilla/engine/steps/effects.py` — loot resolution logic rewritten for group-based model
- `oscilla/engine/loader.py` — `_collect_all_template_strings` extended; `_validate_loot_refs` updated; new condition ref validator for loot entries
- `oscilla/engine/conditions.py` — no changes to evaluator; `evaluate()` already accepts `CharacterState`
- `oscilla/engine/kinds.py` — `LootTable` set `creatable=True`
- `oscilla/cli_content.py` — scaffold template for `loot-table` kind
- `docs/authors/loot-tables.md` — new author documentation
- `docs/authors/README.md` — add loot-tables entry to table of contents
- `content/testlandia/` — update `test-loot.yaml`; update all inline `loot:` drops across testlandia adventures; add a dedicated loot-table QA location with fixtures exercising every new feature
- No database migrations required
- No new Python dependencies required
