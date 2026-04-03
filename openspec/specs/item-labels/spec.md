# Item Labels

## Purpose

A generic, author-defined label system for items that allows content packages to attach named tags to items. Labels serve as display metadata and as first-class query targets in the condition and template systems. The engine stores and exposes labels but never interprets their meaning, preserving the design principle that all item taxonomies are author-defined.

---

## Requirements

### Requirement: Authors declare label vocabulary in game.yaml

`GameSpec` SHALL accept an `item_labels: List[ItemLabelDef]` field (default `[]`). Each `ItemLabelDef` SHALL have:

- `name: str` — unique label identifier within the package
- `color: str = ""` — Rich-compatible color string (e.g., `"gold"`, `"#FFD700"`); empty means no special rendering
- `sort_priority: int = 0` — lower value appears first; equal priority sorts alphabetically

`item_labels` is opt-in: packages that do not declare it have no label vocabulary and no validation warnings. Packages that declare it have the full label system available.

#### Scenario: item_labels declared in game.yaml loads correctly

- **WHEN** a `game.yaml` declares `item_labels: [{name: legendary, color: gold, sort_priority: 1}]`
- **THEN** `registry.game.spec.item_labels` contains one `ItemLabelDef` with `name="legendary"`

#### Scenario: Empty item_labels is valid

- **WHEN** a `game.yaml` omits `item_labels`
- **THEN** the manifest loads without error and `item_labels` defaults to `[]`

---

### Requirement: Items declare zero or more labels

`ItemSpec` SHALL accept a `labels: List[str]` field (default `[]`). Each string is a label name. Labels are purely metadata; their presence on an item has no automatic engine effect. Authors use them in conditions and templates to implement whatever behavior they want.

#### Scenario: Item with multiple labels loads correctly

- **WHEN** an Item manifest declares `labels: [legendary, cursed]`
- **THEN** `item.spec.labels` contains both strings

#### Scenario: Item with no labels is unaffected by label system

- **WHEN** an Item manifest omits `labels`
- **THEN** the item loads and behaves identically to pre-label-system behavior

---

### Requirement: Undeclared labels produce a LoadWarning

If an item references a label string not present in `GameSpec.item_labels`, the content loader SHALL emit a `LoadWarning` (not a `LoadError`). The game continues to load and run. The warning SHALL include a `suggestion` string that offers a likely fix, including a close-match label name when one exists in `item_labels`.

This warning enables the `oscilla validate` command and AI tooling to surface typos and help authors fix them. The label still works functionally (it is queryable in conditions and templates); it simply has no display treatment.

#### Scenario: Undeclared label emits warning with suggestion

- **WHEN** an item declares `labels: [legendery]` and only `legendary` is in `item_labels`
- **THEN** the loader emits a `LoadWarning` for that item with a message identifying the undeclared label and a suggestion mentioning `legendary`

#### Scenario: Undeclared label when no item_labels declared

- **WHEN** an item declares `labels: [rare]` and the game has no `item_labels`
- **THEN** the loader emits a `LoadWarning` indicating the label is undeclared, with a suggestion to add it to `item_labels` in `game.yaml`

#### Scenario: Declared label produces no warning

- **WHEN** an item declares `labels: [legendary]` and `legendary` is in `item_labels`
- **THEN** no warning is emitted for that label

---

### Requirement: Labels are accessible from all three authoring surfaces

Labels declared on items SHALL be accessible from:

1. **Condition system** — via `item_held_label` and `any_item_equipped` predicates (see condition-evaluator spec).
2. **Template system** — inventory template context SHALL expose `item.labels` as a list of strings so templates can branch or display based on labels.
3. **TUI display** — `InventoryScreen` SHALL render label badges next to each item's name, and SHALL sort items within each category tab by label `sort_priority`.

#### Scenario: Template system accesses item labels

- **WHEN** a template renders an item description and the item has `labels: [legendary]`
- **THEN** the template context exposes `item.labels` containing `"legendary"`, accessible via `{{ item.labels }}`

---

### Requirement: InventoryScreen renders label badges with label color

`InventoryScreen` in `oscilla/engine/tui.py` SHALL append an inline Rich-markup badge for each label on an item. The badge color SHALL come from the matching `ItemLabelDef.color` in `registry.game.spec.item_labels`. An item with a label that has no color (or is not in `item_labels`) SHALL receive a `[dim]` fallback badge so the label is still visible.

#### Scenario: Item with declared colored label shows colored badge

- **GIVEN** `item_labels` declares `{name: legendary, color: gold}`
- **AND** an item has `labels: [legendary]`
- **WHEN** the inventory screen is rendered
- **THEN** the item row shows a `[gold]legendary[/gold]` badge after the item name

#### Scenario: Item with undeclared label shows dim badge

- **GIVEN** an item has `labels: [cursed]` but `cursed` is not in `item_labels`
- **WHEN** the inventory screen is rendered
- **THEN** the item row shows a `[dim]cursed[/dim]` badge after the item name

#### Scenario: Item with no labels shows no badges

- **WHEN** an item has `labels: []`
- **THEN** the item row renders identically to pre-label behavior (no badge markup)

---

### Requirement: InventoryScreen sorts items by label sort_priority then alphabetically

Within each category tab, items SHALL be sorted first by the lowest `sort_priority` among all their labels (items with no labels or only unlabeled labels sort last), then alphabetically by `displayName` as a tiebreaker to produce a stable, deterministic order.

#### Scenario: Lower sort_priority item appears above higher priority item

- **GIVEN** item A has `labels: [legendary]` with `sort_priority: 1`
- **AND** item B has `labels: [common]` with `sort_priority: 10`
- **WHEN** both appear in the same inventory category tab
- **THEN** item A is listed above item B

#### Scenario: Unlabeled item sorts after labeled items

- **GIVEN** item A has `labels: [legendary]` with `sort_priority: 1`
- **AND** item B has no labels
- **WHEN** both appear in the same inventory category tab
- **THEN** item A is listed above item B
