## ADDED Requirements

### Requirement: LootGroup model

A `LootGroup` model SHALL exist with the following fields:

- `count: int | str` (default `1`) — how many entries to draw from this group's pool. When a string, it is a Jinja2 template that resolves to a non-negative integer via `render_int`. A resolved count of `0` causes the group to produce no items.
- `method: Literal["weighted", "unique"]` (default `"weighted"`) — selects the sampling strategy. `weighted` draws entries with replacement using `random.choices` with per-entry weights; `unique` draws without replacement using `random.sample`, with `count` silently clamped to pool size and weights ignored.
- `requires: Condition | None` (default `None`) — when set, the entire group is skipped if `evaluate(requires, player, registry)` returns `False`.
- `entries: List[LootEntry]` (required, minimum one entry) — the pool to draw from.

#### Scenario: LootGroup with integer count draws N entries with replacement

- **WHEN** a `LootGroup` with `count: 3` and three entries is resolved against a player
- **THEN** exactly 3 entries are drawn from the weighted pool (with replacement; duplicates are possible)

#### Scenario: LootGroup with template count resolves via render_int at runtime

- **WHEN** a `LootGroup` has `count: "{{ player.stats.luck // 5 }}"` and the player's luck is 15
- **THEN** the resolved count is 3 and 3 entries are drawn

#### Scenario: LootGroup with count 0 produces no items

- **WHEN** a `LootGroup` has `count: 0` (or a template resolving to 0)
- **THEN** no entries are drawn and no items are added to inventory

#### Scenario: LootGroup requires condition — passes

- **WHEN** a `LootGroup` has `requires: {type: milestone, name: dragon-defeated}` and the player holds that milestone
- **THEN** the group is processed and entries are drawn normally

#### Scenario: LootGroup requires condition — fails

- **WHEN** a `LootGroup` has `requires: {type: milestone, name: dragon-defeated}` and the player does not hold that milestone
- **THEN** the entire group is skipped; no entries from that group are drawn

#### Scenario: LootGroup empty pool after entry filtering is skipped gracefully

- **WHEN** every entry in a `LootGroup` has a `requires` condition that evaluates to `False` for the current player
- **THEN** the group is skipped silently; no error is logged

#### Scenario: LootGroup with count greater than pool draws with replacement (method weighted)

- **WHEN** a `LootGroup` has `method: weighted` (or omits `method`), `count: 5`, and only 2 entries in the pool after filtering
- **THEN** 5 entries are drawn with replacement (duplicates are possible)

---

#### Scenario: LootGroup with method unique draws without replacement

- **WHEN** a `LootGroup` has `method: unique`, `count: 3`, and 5 entries in the pool
- **THEN** exactly 3 distinct entries are drawn (no duplicates); each entry is equally likely regardless of its `weight`

#### Scenario: LootGroup unique count clamped when count exceeds pool

- **WHEN** a `LootGroup` has `method: unique`, `count: 10`, and only 3 entries in the pool after filtering
- **THEN** all 3 entries are drawn (count silently clamped to pool size); no error is raised

#### Scenario: LootGroup unique mode ignores entry weights

- **WHEN** a `LootGroup` has `method: unique` and entries with varying `weight` values
- **THEN** all qualifying entries have equal probability of selection; weights are not applied

---

### Requirement: LootEntry extended fields

`LootEntry` SHALL have the following fields:

- `item: str` — manifest name of the item (unchanged)
- `weight: int` (default `1`, minimum `1`) — relative probability weight; optional (omitting equals weight 1)
- `amount: int | str` (default `1`) — how many of the item are added when this entry is selected. When a string, it is a Jinja2 template that resolves to a non-negative integer via `render_int`. A resolved amount of `0` adds nothing.
- `requires: Condition | None` (default `None`) — when set, this entry is excluded from the pool if `evaluate(requires, player, registry)` returns `False`.

#### Scenario: LootEntry with default amount grants one item

- **WHEN** a `LootEntry` omits `amount`
- **THEN** the player receives exactly 1 of the item when the entry is selected

#### Scenario: LootEntry with integer amount grants that many items

- **WHEN** a `LootEntry` has `amount: 5` and is selected
- **THEN** the player receives 5 of the item

#### Scenario: LootEntry with template amount resolves at runtime

- **WHEN** a `LootEntry` has `amount: "{{ randint(50, 200) }}"` and is selected
- **THEN** a random integer between 50 and 200 (inclusive) is resolved and that many items are added

#### Scenario: LootEntry with default weight participates in uniform draw

- **WHEN** multiple entries omit `weight` (all defaulting to 1)
- **THEN** each entry has equal probability of being selected

#### Scenario: LootEntry requires condition — entry included when true

- **WHEN** an entry has `requires: {type: milestone, name: joined-guild}` and the player holds that milestone
- **THEN** the entry is included in the candidate pool

#### Scenario: LootEntry requires condition — entry excluded when false

- **WHEN** an entry has `requires: {type: milestone, name: joined-guild}` and the player does not hold that milestone
- **THEN** the entry is excluded from the candidate pool before the weighted draw

---

### Requirement: Multi-group resolution

When an `item_drop` effect is executed, ALL groups in the resolved group list SHALL be processed independently in order. Results from all groups are merged before items are added to inventory and before the "You found:" announcement.

#### Scenario: Multiple groups each produce their own drops

- **WHEN** an `item_drop` effect has two groups (group A with `count: 2`, group B with `count: 1`)
- **THEN** 2 draws occur from group A's pool and 1 draw occurs from group B's pool; all selected items are added to inventory

#### Scenario: A skipped group does not affect other groups

- **WHEN** group A has a `requires` condition that fails and group B has no condition
- **THEN** group B is still processed normally; the combined result contains only group B's items

#### Scenario: Results are announced as a combined "You found:" message

- **WHEN** multiple groups each produce items
- **THEN** all items are shown in a single "You found: X, Y, Z" message, not one message per group

---

### Requirement: Template string precompilation for LootGroup and LootEntry

All `count` strings on `LootGroup` and all `amount` strings on `LootEntry` SHALL be precompiled at content load time via `precompile_and_validate`. A template syntax error or failed mock render SHALL produce a `LoadError`.

#### Scenario: Valid count template precompiles successfully

- **WHEN** a `LootGroup` has `count: "{{ d(1, 6) }}"` and the content is loaded
- **THEN** the template is precompiled without error

#### Scenario: Invalid count template produces a load error

- **WHEN** a `LootGroup` has `count: "{{ unclosed_brace"` and the content is loaded
- **THEN** a `LoadError` is produced identifying the template and its location

#### Scenario: Amount template with undefined variable produces a load error

- **WHEN** a `LootEntry` has `amount: "{{ nonexistent_var }}"` and the content is loaded
- **THEN** a `LoadError` is produced at load time (mock render fails)

---

### Requirement: Load-time validation of condition refs in loot entry trees

The content loader SHALL validate all condition nodes inside `LootGroup.requires` and `LootEntry.requires` across all loot sources (LootTable manifests, enemy loot fields, adventure inline groups). Unknown milestone names, stat names, item names, and archetype names SHALL produce a `LoadError`.

#### Scenario: Unknown milestone in LootGroup requires produces a load error

- **WHEN** a `LootGroup` declares `requires: {type: milestone, name: nonexistent-milestone}` and no milestone with that name exists
- **THEN** a `LoadError` is produced at load time

#### Scenario: Unknown item in LootEntry requires produces a load error

- **WHEN** a `LootEntry` declares `requires: {type: item, name: ghost-item}` and no item manifest named `ghost-item` exists
- **THEN** a `LoadError` is produced at load time

#### Scenario: Valid condition refs pass validation

- **WHEN** all condition refs in loot groups and entries resolve to known manifest names
- **THEN** no errors are produced and the content loads successfully
