# Derived Stats

## Purpose

Defines the derived stat system where stat values are computed from Jinja2 formula expressions rather than stored directly. Covers the `derived` field on `StatDefinition`, circular dependency detection, topological evaluation order, shadow change detection, and template access.

## Requirements

### Requirement: StatDefinition supports a derived formula field

`StatDefinition` in `character_config.yaml` SHALL support an optional `derived` field containing a Jinja2 template string. When `derived` is set, the stat is a **derived stat** — its value is always computed from other stats and never written to `CharacterState.stats`. Derived stats:

- SHALL NOT appear in `CharacterState.stats` (they are never stored)
- SHALL be computed at read time using the `_derived_shadows` mechanism
- SHALL accept `bounds` for clamping the computed value
- SHALL NOT accept a `default` value (derived stats have no initial stored value; declaring one is a load error)
- SHALL NOT be of type `bool` (derived formulas always produce `int`; declaring a bool derived stat is a load error)
- SHALL support an optional `stat_context: "stored" | "effective"` field (default `"stored"`)

`stat_context` controls which stat dict the derived formula sees:

- `stat_context: stored` (default) — the formula sees `player.stats` (raw stored values, no equipment bonuses or passive effects)
- `stat_context: effective` — the formula sees `effective_stats(registry)` (stored stats + equipped item modifiers + passive effects)

Regardless of `stat_context`, the formula also sees previously-computed derived stat values in topological order (derived-from-derived chains work in both modes).

Derived formulas receive the same `ExpressionContext` as adventure templates. The stat dict visible as `player.stats` in the formula depends on `stat_context`:

- `stored` — `player.stats` contains raw stored stats plus already-computed derived stats that precede the current one in topological order
- `effective` — `player.stats` contains `effective_stats(registry)` (equipment bonuses and passive effects included) plus already-computed derived stats that precede the current one in topological order

Derived formulas MAY reference other derived stats by name as long as no circular dependency exists. A circular dependency (including self-reference) is a load-time error. The loader builds a dependency graph, performs a topological sort, and evaluates derived stats in safe order so each formula sees its dependencies already resolved.

#### Scenario: Derived stat declared in character_config.yaml

- **WHEN** a stat definition contains `derived: '{{ floor((player.stats["constitution"] - 10) / 2) }}'`
- **THEN** `load()` accepts it without error and the stat is recognized as a derived stat

#### Scenario: Derived stat is absent from CharacterState.stats

- **WHEN** a character has a derived stat `constitution_bonus` declared
- **THEN** `player.stats` does NOT contain a key `"constitution_bonus"`

#### Scenario: `stat_context: effective` derived stat sees equipment bonus

- **WHEN** derived stat `hp` is declared with `stat_context: effective` and formula `'{{ player.stats["constitution"] * 5 }}'`, and the player has an equipped item that adds `constitution: +2`
- **THEN** `player._derived_shadows["hp"]` reflects the boosted value (as if constitution were 2 higher)

#### Scenario: `stat_context: stored` derived stat does not see equipment bonus

- **WHEN** derived stat `constitution_label` is declared with the default `stat_context: stored` and the player has a Helm of Hardening equipped adding `constitution: +2`
- **THEN** the formula sees the unmodified stored `constitution` value

#### Scenario: Derived stat with default value is a load error

- **WHEN** a stat declares both `derived` and `default`
- **THEN** `load()` raises a `ContentLoadError` with a message identifying the stat name

#### Scenario: Bool derived stat is a load error

- **WHEN** a stat declares `type: bool` AND `derived: <formula>`
- **THEN** `load()` raises a `ContentLoadError` with a message identifying the stat name

#### Scenario: Derived formula referencing another derived stat is valid when no cycle exists

- **WHEN** derived stat `constitution_bonus` references `player.stats["constitution"]` (a stored stat) and derived stat `attack_bonus` references `player.stats["constitution_bonus"]` (a derived stat)
- **THEN** `load()` accepts both, sorts them in dependency order (`constitution_bonus` before `attack_bonus`), and evaluates correctly

---

### Requirement: Circular derived stat dependencies are a load error

The content loader SHALL build a directed dependency graph over all derived stat formulas by detecting references to other derived stat names in each formula. It SHALL perform a topological sort (DFS-based cycle detection) on this graph. If a cycle is found (including a stat referencing itself), `load()` SHALL raise a `ContentLoadError` identifying the stat names involved in the cycle. Non-circular chains (A derives from B, B derives from C) are fully supported.

---

### Requirement: Derived stat formulas are precompiled and mock-rendered at load time

Derived stat formulas SHALL be compiled and mock-rendered at `load()` using the same mock `ExpressionContext` used for adventure templates. The mock context SHALL include all stored (non-derived) stats with representative values, plus mock values for all derived stats that precede the current one in topological order (so derived-from-derived references do not produce false load errors). A formula that fails compilation or mock render SHALL be a load error.

#### Scenario: Valid derived formula compiles at load time

- **WHEN** `derived: '{{ player.stats["xp"] // 100 }}'` references a known stored stat
- **THEN** `load()` compiles and mock-renders it without error

#### Scenario: Derived formula with syntax error is a load error

- **WHEN** `derived: '{{ player.stats["xp" '` contains an unterminated expression
- **THEN** `load()` raises a `ContentLoadError` identifying the stat and the template syntax error

#### Scenario: Derived formula referencing unknown stat is a load error

- **WHEN** `derived: '{{ player.stats["nonexistent"] }}'` and `nonexistent` is not in `CharacterConfig`
- **THEN** `load()` raises a `ContentLoadError` during mock render

---

### Requirement: Engine maintains shadow values for derived stat change detection

`CharacterState` SHALL include a `_derived_shadows: Dict[str, int | None]` field (never serialized). After every `stat_change` or `stat_set` effect, the engine SHALL call `_recompute_derived_stats()`, which:

1. Evaluates every derived stat formula
2. Compares the new value to the stored shadow value
3. Writes the new value to `_derived_shadows`
4. For each stat whose value changed, calls `_fire_threshold_triggers()` for that stat

`_recompute_derived_stats()` SHALL evaluate derived stats **in topological dependency order** (computed once at load time and stored in the registry as `ContentRegistry.derived_eval_order`), using a working stats dict that tracks computed derived values as evaluation proceeds. For each derived stat, the base stat dict is selected by `stat_context`: `stored` reads from `player.stats`; `effective` reads from `effective_stats(registry)`. Previously computed derived stat values are merged into the formula context for both modes to support derived-from-derived chains.

**Equipment change triggers:** When one or more derived stats declare `stat_context: effective`, the engine SHALL also call `_recompute_derived_stats()` after any equipment change (equip or unequip) in the TUI and engine item-use paths, in addition to the post-stat-mutation call.

#### Scenario: Shadow updated after stat mutation

- **WHEN** a `stat_change` effect increases `constitution` from 10 to 14 and `constitution_bonus` is `derived: '{{ (player.stats["constitution"] - 10) // 2 }}'`
- **THEN** `player._derived_shadows["constitution_bonus"]` equals `2` after the effect

#### Scenario: No threshold trigger fires on first shadow initialization

- **WHEN** `_recompute_derived_stats()` is called for the first time after character creation
- **THEN** no `on_stat_threshold` triggers are enqueued regardless of the initial computed values

#### Scenario: Derived shadow is not serialized to the database

- **WHEN** `player.to_dict()` is called
- **THEN** the returned dict does not contain a `_derived_shadows` key

---

### Requirement: Derived stats are accessible via player.stats in templates

After `_recompute_derived_stats()` runs, derived stat values SHALL be accessible in `PlayerContext.stats` alongside stored stats, using the derived stat's name as the key. This merging happens inside `PlayerContext.from_character()` — the context is built from the union of `CharacterState.stats` (stored) and `CharacterState._derived_shadows` (derived).

#### Scenario: Template can read derived stat value

- **WHEN** `{{ player.stats["constitution_bonus"] }}` is rendered for a character where `constitution_bonus` is a derived stat with shadow value `2`
- **THEN** the rendered output is `"2"`

#### Scenario: Derived stat mock value available at load time for template validation

- **WHEN** an adventure template references `player.stats["constitution_bonus"]` and `constitution_bonus` is a defined derived stat
- **THEN** `load()` mock-renders the template without error

---

### Requirement: on_stat_threshold fires for derived stat changes

`_fire_threshold_triggers()` SHALL be called for derived stats whenever their shadow value changes, using the same upward-crossing logic as stored stats. All threshold entries registered for the derived stat name SHALL be evaluated. Multi-cross behavior applies: if the derived value crosses multiple thresholds in one recomputation, each threshold fires as a separate enqueue, in ascending threshold order.

#### Scenario: Derived stat crossing threshold enqueues trigger

- **WHEN** `constitution_bonus` (derived) changes from `1` to `2` and a threshold at `2` is registered for `constitution_bonus`
- **THEN** the threshold's trigger name is appended to `pending_triggers`

#### Scenario: Multi-cross enqueues one entry per threshold crossed

- **WHEN** `level` (derived from `xp`) jumps from `1` to `4` in a single XP grant and thresholds for `level` are declared at `2`, `3`, and `4`
- **THEN** three trigger entries are appended to `pending_triggers` in ascending threshold order

#### Scenario: Downward change on derived stat does not fire threshold

- **WHEN** a derived stat's value decreases (e.g., `constitution_bonus` falls from `3` to `1`)
- **THEN** no `on_stat_threshold` trigger is enqueued

#### Scenario: No threshold registered for derived stat means no trigger

- **WHEN** a derived stat's shadow value changes and no `on_stat_threshold` entry lists that stat
- **THEN** `pending_triggers` is unchanged

---

### Requirement: stat_change and stat_set targeting a derived stat are load errors

If a `stat_change` or `stat_set` effect targets a stat name declared as `derived`, the content loader SHALL raise a `ContentLoadError` at load time. The error message SHALL identify the adventure, the step, and the derived stat name.

#### Scenario: stat_change targeting derived stat is a load error

- **WHEN** a manifest declares `stat_change { stat: level, amount: 1 }` and `level` is a derived stat
- **THEN** `load()` raises a `ContentLoadError` identifying the adventure and stat

#### Scenario: stat_set targeting derived stat is a load error

- **WHEN** a manifest declares `stat_set { stat: constitution_bonus, value: 5 }` and `constitution_bonus` is a derived stat
- **THEN** `load()` raises a `ContentLoadError` identifying the adventure and stat
