# Design: Enhanced Loot Tables

## Context

The current loot system is built around a flat `List[LootEntry]` on both `LootTableSpec` and `ItemDropEffect`. The `ItemDropEffect.count` field rolls the entire flat list `count` times with replacement. `LootEntry` carries `item`, `weight`, and `quantity` — nothing more.

This model works for simple one-of-N drops but forces authors to chain multiple `item_drop` effects or build multi-step adventures when they need independent pools, conditional entries, or template-driven quantities. `LootTable` manifests already exist and are loaded into `registry.loot_tables`, but `creatable=False` in `kinds.py` means they are invisible to `oscilla content create`.

The template infrastructure used by `StatChangeEffect.amount` and `ItemDropEffect.count` (precompile at load time, `render_int` at runtime) is already in place and can be reused directly for `LootGroup.count` and `LootEntry.amount`.

The condition evaluator (`conditions.evaluate()`) already accepts `CharacterState` and `ContentRegistry`. Threading player state into the loot resolution path is purely a call-site change.

**Current state before this change:**

| Element                   | Current state                                                    |
| ------------------------- | ---------------------------------------------------------------- |
| `LootEntry.quantity`      | Fixed `int`; no template support                                 |
| `LootEntry.weight`        | Required `int ge=1`                                              |
| `LootEntry.requires`      | Not present                                                      |
| `LootTableSpec.loot`      | Flat `List[LootEntry]`; no groups, no conditions                 |
| `LootTable` creatable     | `creatable=False` — invisible to `oscilla content create`        |
| `ItemDropEffect.loot`     | Inline flat list                                                 |
| `ItemDropEffect.loot_ref` | Resolves against LootTable manifests _and_ enemies               |
| `ItemDropEffect.count`    | Template-capable `int \| str`; rolls the whole flat list N times |
| `EnemySpec.loot`          | `List[LootEntry]` — flat, no groups, no conditions               |
| Multi-pool drops          | Not possible without multiple `item_drop` effects                |
| Conditional drops         | Not possible                                                     |

---

## Goals / Non-Goals

**Goals:**

- Replace the flat `loot: List[LootEntry]` with `groups: List[LootGroup]` everywhere loot is declared (LootTable manifest, ItemDropEffect inline).
- `LootGroup`: independent resolution unit with its own `count: int | str`, `method: Literal["weighted", "unique"] = "weighted"` (sampling strategy), optional `requires: Condition`, and `entries: List[LootEntry]`.
- `LootEntry`: gain `requires: Condition | None` (per-entry filter) and rename `quantity` → `amount: int | str` (template-capable).
- Existing `weight: int = 1` behaviour is unchanged; weight is now optional (default 1).
- All `count` and `amount` template strings in loot manifests are precompiled at load time and resolved at runtime.
- Condition refs in `LootGroup.requires` and `LootEntry.requires` are validated at load time (hard errors for unknown milestones, stats, items, archetypes).
- `ItemDropEffect` retains `loot_ref` (now pointing at a LootTable with groups); inline `loot` and `count` fields are removed.
- `LootTable` kind becomes `creatable=True`; scaffold template added.
- Enemy `EnemySpec.loot` migrates from `List[LootEntry]` to `List[LootGroup]`, giving enemies the same expressive power as all other loot sites.
- `LootTable`, `LootGroup`, and `LootEntry` are fully reflected in the `oscilla content schema` export (automatic via Pydantic model introspection, no separate schema code needed).
- `docs/authors/loot-tables.md` written as the canonical author reference for the entire feature.
- Testlandia content updated: all inline `loot:` lists migrated; all enemy `loot:` lists migrated; new dedicated loot-table QA region added.

**Non-Goals:**

- Nested or recursive group references (a group whose entries are themselves groups).

---

## Decisions

### D1: Groups replace the flat list entirely — no backward-compatible `loot:` alias

**Decision:** Both `LootTableSpec.loot` and `ItemDropEffect.loot` are removed. Authors use `groups:` everywhere. No migration alias or deprecation warning.

**Alternatives considered:**

- Keep `loot:` as a shorthand that wraps silently into a single group with `count: 1` — rejected. Two schemas for the same thing creates documentation debt, ambiguous error messages, and a migration surface that outlasts its usefulness. Since no v1 release has shipped and there is only one testlandia `LootTable` manifest plus ~12 inline adventure `loot:` lists, the migration cost is low.
- Deprecation warning for one release cycle — no release cycle exists to deprecate across. Hard removal is cleanest.

**Rationale:** Design philosophy: features are invisible when unused, not partially present. The migration is a one-time content touch.

---

### D2: `LootGroup.count` mirrors `ItemDropEffect.count` exactly — `int | str`, resolved via `render_int`

**Decision:** `LootGroup.count: int | str = 1`. When a string, it is a Jinja2 template string evaluated via `GameTemplateEngine.render_int()`. Precompiled at load time by `_collect_all_template_strings`. At runtime, resolved before the weighted draw.

**Alternatives considered:**

- A dedicated `count` resolver that clamps to pool size — rejected as premature. Authors who pass `count > len(entries)` get duplicate draws (with-replacement), which is the documented behavior and matches the existing `ItemDropEffect.count` semantics.
- Separate `count_min` / `count_max` fields for range draws — rejected. Template strings subsume this use case (`{{ randint(1, 3) }}`) with far more flexibility (level scaling, stat-based scaling, dice expressions).

---

### D3: `LootEntry.amount` mirrors `StatChangeEffect.amount` — `int | str`

**Decision:** `LootEntry.amount: int | str = 1`. When a string, precompiled and resolved via `render_int`. The old field name `quantity` is removed.

**Rationale:** `amount` is the established name for template-capable integer fields on effects (`StatChangeEffect.amount`). Using `quantity` for loot and `amount` elsewhere is inconsistent. The rename is a clean break with no migration cost beyond the content files already being updated.

---

### D4: `LootEntry.requires` and `LootGroup.requires` both use the standard `Condition` union

**Decision:** Both fields are `Condition | None = None`, evaluated via `conditions.evaluate(condition, player, registry)` at runtime. A `None` condition always passes. Load-time validation traverses these condition trees with the same validators used elsewhere (milestone refs, stat refs, item refs, archetype refs).

**Alternatives considered:**

- Only `LootGroup.requires`, not per-entry — rejected. Per-entry conditions enable "this item only drops if the player has a specific skill/milestone" without requiring authors to split entries across separate groups. Both levels are useful.
- A simpler `milestone_required: str | None` shorthand — rejected. Violates the design principle that the condition evaluator is the universal gate. Authors already know the condition syntax; a one-off shorthand creates a second way to express the same constraint.

**Consequence:** `_resolve_loot_groups()` at runtime requires `CharacterState`. The call site in `run_effect` already has `player`; passing it through is a signature change to one helper function.

---

### D5: All groups on a LootTable or inline `groups:` are processed independently; results are announced together

**Decision:** The resolution algorithm is:

```
results = []
for group in groups:
    if group.requires and not evaluate(group.requires, player, registry):
        continue                      # skip entire group
    pool = [e for e in group.entries
            if e.requires is None or evaluate(e.requires, player, registry)]
    if not pool:
        continue                      # no entries pass — skip gracefully
    count = resolve_count(group.count)
    if group.method == "unique":
        chosen = random.sample(pool, k=min(count, len(pool)))  # no weights
    else:
        weights = [e.weight for e in pool]
        chosen = random.choices(pool, weights=weights, k=count)
    results.extend(chosen)

# Add all results to inventory, announce combined "You found: X, Y, Z"
```

**Key behavior:**

- `method: weighted` (default): `random.choices(pool, weights, k=count)` — with replacement, duplicates possible when `count > len(pool)`.
- `method: unique`: `random.sample(pool, k=min(count, len(pool)))` — without replacement; `count` is silently clamped to pool size rather than erroring. Weights are ignored (`random.sample` does not support them; all qualifying entries are equally likely).
- If the pool is empty after filtering, the group is skipped silently regardless of method.

**Rationale:** With-replacement is consistent with the existing `count` semantics. Silent empty-pool skip is safer than a runtime error and correct for conditional groups that might have all entries filtered.

---

### D6: Load-time validation of condition refs in loot entry trees

**Decision:** Extend the semantic validator to collect and validate condition nodes inside `LootGroup.requires` and `LootEntry.requires` across all three loot sources:

1. `LootTable` manifests (via `registry.loot_tables`)
2. Enemy `spec.loot` groups (same `List[LootGroup]` structure — group-level and entry-level `requires` both validated)
3. Adventure `item_drop` inline `groups` fields

The validator reuses the existing `_collect_archetype_refs_in_condition`, `_collect_quest_stage_conditions_in_condition`, and similar traversal helpers. No new traversal framework is needed — just additional call sites.

**Hard errors:** Unknown milestone names, stat names, item names, archetype names referenced in loot conditions are `LoadError`s (not warnings). This matches the policy for all other condition ref validation in the codebase.

---

### D7: Enemy `spec.loot` migrates from `List[LootEntry]` to `List[LootGroup]`

**Decision:** `EnemySpec.loot` changes type from `List[LootEntry]` to `List[LootGroup]`. The field name `loot` is kept on the enemy model because it semantically describes what the enemy drops, but its structure becomes identical to every other loot site. Enemies with simple single-pool drops use a single group with no `requires`.

**Alternatives considered:**

- Keep enemy loot as a flat `List[LootEntry]` and let complex cases delegate entirely to a named `LootTable` via `loot_ref` in an adventure effect — rejected. Enemies are the _primary_ site of loot drops in most content; demoting them to a restricted subset defeats the purpose of a unified system and forces authors to create a separate `LootTable` manifest for every enemy that needs multiple pools or conditional drops. That is needless indirection.
- Rename `EnemySpec.loot` to `EnemySpec.groups` for strict naming consistency — rejected. `loot` on an enemy manifest clearly describes its purpose (what the enemy drops). The `groups` name applies at the structural level _within_ a loot declaration. `Enemy.loot` is the declaration; each element of that list is a `LootGroup`. Both names are correct at their level.

**Rationale:** One loot system everywhere. Enemies that previously had a flat `loot: [item: sword, weight: 1]` entry become `loot: [{entries: [{item: sword}]}]`. The migration is purely mechanical and covered in the tasks. The schema export (`oscilla content schema enemy`) will reflect the updated model automatically.

**Migration scope:** Testlandia has a small number of enemy YAML files with `loot:` lists. All are migrated as part of the content migration tasks.

---

### D8: `LootGroup.method` selects the sampling strategy

**Decision:** `LootGroup` gains a `method: Literal["weighted", "unique"] = "weighted"` field. `weighted` (the default) preserves existing `random.choices` with-replacement behavior. `unique` switches to `random.sample` without replacement, with `count` silently clamped to pool size.

**Weight behavior in unique mode:** Python's `random.sample` does not support per-item weights. When `method: unique`, weights on `LootEntry` are ignored and all qualifying entries are equally likely. Authors should be aware of this trade-off; it is documented in the author reference.

**Alternatives considered:**

- A boolean `unique: bool = False` — rejected. A boolean cannot express a third method when one is added later (e.g. `weighted_unique` — weighted sampling without replacement via iterative draw). An enum-like `Literal` field pays no implementation cost now and avoids a breaking field rename later.
- Weighted sampling without replacement as an immediate third value (`weighted_unique`) — deferred, not rejected. The implementation (iterative `random.choices` removing chosen items) is straightforward but introduces complexity not needed today. Adding `method: weighted_unique` is a non-breaking extension to this field.
- Raising an error when `count > len(pool)` in unique mode — rejected. Silent clamping is consistent with the empty-pool skip behavior (graceful degradation over runtime errors). Authors who set `count: 5` on a pool of 3 in unique mode get all 3; this is the most useful behavior.

**Rationale:** A `Literal` field scales to future methods without a breaking schema change. With-replacement is the correct default for most loot scenarios; `method: unique` adds the "pick N distinct items" capability as an explicit, legible opt-in.

---

## Architecture

### Loot Data Flow

```mermaid
graph TD
    IE[ItemDropEffect<br/>groups: List[LootGroup] | None<br/>loot_ref: str | None]
    LT[LootTable manifest<br/>spec.groups: List[LootGroup]]
    ES[EnemySpec<br/>loot: List[LootGroup]]

    IE -- loot_ref --> LT
    IE -- inline groups --> R
    LT -- resolved groups --> R
    ES -- loot groups --> R

    R[_resolve_loot_groups<br/>groups, player, registry]

    R --> G1[Group 1<br/>count, method, requires]
    R --> G2[Group 2<br/>count, method, requires]
    R --> GN[Group N ...]

    G1 --> C1{group.requires?}
    C1 -- false → skip --> DONE
    C1 -- true / None --> F1[filter entries<br/>by entry.requires]
    F1 --> D1{method?}
    D1 -- weighted --> W1[random.choices<br/>pool, weights, k=count]
    D1 -- unique --> U1[random.sample<br/>pool, k=min count len pool]

    W1 --> MERGE[merge all chosen entries]
    U1 --> MERGE
    MERGE --> INV[add_item × amount<br/>announce You found:]
```

### Template String Resolution

```
load time:  _collect_all_template_strings()
              └─▶ _walk_loot_groups(groups, path)
                    └─▶ per group: group.count if str
                    └─▶ per entry: entry.amount if str
            precompile_and_validate(template_id, template_str, context_type)

run time:   count  = render_int(template_id, ctx) if str(group.count)  else group.count
            amount = render_int(template_id, ctx) if str(entry.amount) else entry.amount
            Both results clamped to max(0, value) before use.
```

---

## Implementation

### Modified File: `oscilla/engine/models/loot_table.py`

**Before:**

```python
class LootEntry(BaseModel):
    item: str
    weight: int = Field(ge=1)
    quantity: int = Field(default=1, ge=1)


class LootTableSpec(BaseModel):
    displayName: str
    description: str = ""
    loot: List[LootEntry] = Field(min_length=1)


class LootTableManifest(ManifestEnvelope):
    kind: Literal["LootTable"]
    spec: LootTableSpec
```

**After:**

```python
from typing import List, Literal
from pydantic import BaseModel, Field
from oscilla.engine.models.base import Condition, ManifestEnvelope


class LootEntry(BaseModel):
    """A single weighted entry within a LootGroup.

    weight: relative draw probability in weighted mode; ignored in unique mode.
    amount: how many of the item to grant per selection. Template-capable.
    requires: optional condition evaluated at runtime; entry is excluded from the
              pool when it evaluates False. A None condition always passes.
    """

    item: str
    weight: int = Field(default=1, ge=1)
    amount: int | str = Field(default=1)
    requires: Condition | None = None


class LootGroup(BaseModel):
    """An independent draw pool within a loot table.

    count: how many entries to draw from this group. Template-capable.
    method: "weighted" (default) draws with replacement using entry weights;
            "unique" draws without replacement via random.sample (weights ignored,
            count clamped to pool size).
    requires: optional condition evaluated at runtime; the entire group is skipped
              when it evaluates False.
    entries: at least one LootEntry required.
    """

    count: int | str = Field(default=1)
    method: Literal["weighted", "unique"] = "weighted"
    requires: Condition | None = None
    entries: List[LootEntry] = Field(min_length=1)


class LootTableSpec(BaseModel):
    displayName: str
    description: str = ""
    groups: List[LootGroup] = Field(min_length=1)


class LootTableManifest(ManifestEnvelope):
    kind: Literal["LootTable"]
    spec: LootTableSpec
```

---

### Modified File: `oscilla/engine/models/adventure.py`

**Before (ItemDropEffect only):**

```python
class ItemDropEffect(BaseModel):
    type: Literal["item_drop"]
    count: int | str = Field(default=1, description="Roll count or template string resolving to int.")
    loot: List[LootEntry] | None = None
    loot_ref: str | None = Field(
        default=None,
        description=(
            "Reference to a named LootTable manifest or an Enemy manifest name. "
            "Mutually exclusive with loot."
        ),
    )

    @model_validator(mode="after")
    def exactly_one_loot_source(self) -> "ItemDropEffect":
        has_inline = self.loot is not None and len(self.loot) > 0
        has_ref = self.loot_ref is not None
        if has_inline and has_ref:
            raise ValueError("ItemDropEffect: specify either 'loot' or 'loot_ref', not both.")
        if not has_inline and not has_ref:
            raise ValueError("ItemDropEffect: must specify either 'loot' (inline list) or 'loot_ref'.")
        return self
```

**After:**

```python
from oscilla.engine.models.loot_table import LootGroup


class ItemDropEffect(BaseModel):
    """Drop items from one or more independent loot groups.

    Exactly one of groups (inline) or loot_ref (named LootTable manifest) must
    be provided. loot_ref is resolved exclusively against registry.loot_tables;
    the historical enemy fallback is removed.
    """

    type: Literal["item_drop"]
    groups: List[LootGroup] | None = Field(
        default=None,
        description="Inline loot group list. Mutually exclusive with loot_ref.",
    )
    loot_ref: str | None = Field(
        default=None,
        description="Reference to a named LootTable manifest. Mutually exclusive with groups.",
    )

    @model_validator(mode="after")
    def exactly_one_loot_source(self) -> "ItemDropEffect":
        has_inline = self.groups is not None and len(self.groups) > 0
        has_ref = self.loot_ref is not None
        if has_inline and has_ref:
            raise ValueError("ItemDropEffect: specify either 'groups' or 'loot_ref', not both.")
        if not has_inline and not has_ref:
            raise ValueError("ItemDropEffect: must specify either 'groups' (inline) or 'loot_ref'.")
        return self
```

---

### Modified File: `oscilla/engine/models/enemy.py`

**Before (EnemySpec.loot only):**

```python
from oscilla.engine.models.loot_table import LootEntry  # noqa: F401 — re-exported for callers

class EnemySpec(BaseModel):
    ...
    loot: List[LootEntry] = []
```

**After:**

```python
from oscilla.engine.models.loot_table import LootGroup  # noqa: F401 — re-exported for callers

class EnemySpec(BaseModel):
    ...
    # Each element is an independent draw pool. Simple single-pool drops use a
    # single group with no requires and method: weighted (the defaults).
    loot: List[LootGroup] = []
```

---

### Modified File: `oscilla/engine/kinds.py`

**Before:**

```python
ManifestKind("loot-table", "loot-tables", "loot_tables", "LootTable", LootTableManifest, creatable=False),
```

**After:**

```python
ManifestKind("loot-table", "loot-tables", "loot_tables", "LootTable", LootTableManifest, creatable=True),
```

---

### Modified File: `oscilla/engine/steps/effects.py`

**Before (`_resolve_loot_list`):**

```python
def _resolve_loot_list(
    effect: ItemDropEffect,
    registry: "ContentRegistry",
) -> "List[LootEntry]":
    if effect.loot is not None:
        return effect.loot
    assert effect.loot_ref is not None
    entries = registry.resolve_loot_entries(effect.loot_ref)
    assert entries is not None, (...)
    return entries
```

The `run_effect` dispatch then called `random.choices(population=loot_entries, weights=weights, k=count)` directly on the flat list.

**After (`_resolve_loot_groups`):**

```python
def _resolve_loot_groups(
    groups: "List[LootGroup]",
    player: "CharacterState",
    registry: "ContentRegistry",
    ctx: "ExpressionContext",
) -> "List[tuple[str, int]]":
    """Resolve a list of LootGroups into (item_ref, amount) pairs.

    Each group is processed independently:
    - group.requires is evaluated; the group is skipped if it returns False.
    - Each entry's requires is evaluated; entries not passing are excluded from the pool.
    - If the pool is empty after filtering, the group is silently skipped.
    - group.count (template-capable) is resolved and clamped to max(0, value).
    - Entries are drawn via group.method: "weighted" uses random.choices with entry
      weights; "unique" uses random.sample without replacement, count clamped to
      min(count, len(pool)).
    - entry.amount (template-capable) is resolved per chosen entry.

    Returns a flat list of (item_ref, amount) tuples, one per drawn entry instance.
    All groups contribute to the same result list.
    """
    results: list[tuple[str, int]] = []
    for group in groups:
        if group.requires is not None and not evaluate(group.requires, player, registry):
            continue
        pool = [
            e for e in group.entries
            if e.requires is None or evaluate(e.requires, player, registry)
        ]
        if not pool:
            continue
        count = _resolve_int_field(group.count, ctx, registry)
        count = max(0, count)
        if count == 0:
            continue
        if group.method == "unique":
            chosen = random.sample(pool, k=min(count, len(pool)))
        else:
            weights = [e.weight for e in pool]
            chosen = random.choices(pool, weights=weights, k=count)
        for entry in chosen:
            amount = _resolve_int_field(entry.amount, ctx, registry)
            results.append((entry.item, max(0, amount)))
    return results
```

---

## Documentation Plan

- **`docs/authors/loot-tables.md`** (new): Canonical author reference. Audience: content authors. Covers: `LootTable` manifest anatomy, `groups` + `entries` schema, `count` / `amount` template expressions, `requires` on groups and entries, inline `groups:` in adventures, referencing a named LootTable via `loot_ref`, enemy `loot:` with groups, migration from old `loot:` syntax. Includes a full worked example with multiple independent pools and conditional entries.
- **`docs/authors/README.md`**: Add entry for loot-tables.
- **`docs/authors/enemies.md`**: Update enemy `loot:` field documentation to reflect `List[LootGroup]` and link to loot-tables.
- **`docs/dev/game-engine.md`**: Update `item_drop` effect documentation and enemy loot documentation to reflect the unified group model.

---

## Testing Philosophy

- **Unit tests**: `LootGroup` and `LootEntry` model validation (Pydantic) — required fields, defaults, `model_validator` for `groups`/`loot_ref` mutual exclusivity on `ItemDropEffect`.
- **Unit tests**: `EnemySpec.loot` accepts `List[LootGroup]` and rejects flat `List[LootEntry]`.
- **Unit tests**: `_resolve_loot_groups()` logic — group-level condition skip, entry-level condition filter, empty-pool graceful skip, `method: weighted` with-replacement draw, `method: unique` without-replacement draw with count clamping, template `count` and `amount` resolution.
- **Integration tests**: Load a fixture `LootTable` manifest with groups and verify registry registration; load an adventure with inline `groups:` and verify it runs end-to-end; load a fixture enemy with `loot: [{entries: [...]}]` and verify the groups resolve correctly at runtime.
- **Schema tests**: Verify `oscilla content schema loot-table` and `oscilla content schema enemy` outputs reflect `LootGroup` and `LootEntry` — confirm the schema export includes the full group structure.
- **Load-error tests**: Fixture with an unknown item ref in a `LootEntry.requires` condition triggers `LoadError`; same for `LootGroup.requires`. Covers all three loot sites (LootTable, adventure inline, enemy).
- **Fixture constraints**: All test fixtures live in `tests/fixtures/content/` with `test-` prefixed manifest names. No reference to `content/` directory. Condition refs in fixture loot tables must use milestone/stat/item names declared in the same fixture set.
- **No mock TUI required for unit tests on `_resolve_loot_groups()`**: construct `CharacterState` and a minimal `ContentRegistry` directly.

---

## Risks / Trade-offs

- [With-replacement when `count > pool`] Authors expecting "pick N unique items" will get duplicates with the default `method: weighted`. → Document clearly; `method: unique` is the explicit opt-in for duplicate-free draws.
- [Template strings in `count`/`amount` can produce `≤ 0`] Negative or zero values would be nonsensical. → `render_int` result is clamped to `max(0, result)`; a count of 0 skips the group gracefully; an amount of 0 adds 0 items (effectively a no-op).
- [Load-time condition validation for loot entries increases validator complexity] More traversal code in `loader.py`. → The pattern is already established; this is additive, not structural.
- [Breaking change to adventure YAML format] All inline `loot:` lists need migration. → Scope is bounded: testlandia has ~12 such adventures plus a small number of enemy YAML files. The migration is mechanical and fully covered by the tasks.
