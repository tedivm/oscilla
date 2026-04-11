# Buff Blocking

## Purpose

Specifies how `exclusion_group` and `priority` fields on `BuffSpec` prevent lower-priority instances of the same buff family from being applied when a stronger version is already active.

## Requirements

### Requirement: BuffSpec declares exclusion group, priority, and exclusion mode

`BuffSpec` SHALL accept three optional fields:

- `exclusion_group: str | None = None` — an author-defined identifier grouping buffs that are mutually exclusive. May be any non-empty string. Two buffs are in the same group if and only if their `exclusion_group` values are equal (case-sensitive).
- `priority: int | str = 0` — numeric priority within the exclusion group. Higher values represent stronger buffs. When a string, treated as a variable name that MUST be declared in `BuffSpec.variables` (validated at load time by an extension of `validate_variable_refs`) and resolved against the merged variables dict at apply time, yielding an `int`. Defaults to 0 when not specified.
- `exclusion_mode: Literal["block", "replace"] = "block"` — controls what happens when an incoming buff has higher priority than all existing same-group effects. `"block"` leaves existing effects intact; `"replace"` evicts all same-group same-target effects before applying the new one.

A load-time warning SHALL be emitted when `priority != 0` and `exclusion_group is None` — priority has no effect without a group.

`ActiveCombatEffect` SHALL carry mirrored fields: `exclusion_group: str = ""`, `priority: int = 0` (always resolved), and `exclusion_mode: str = "block"`, populated from the buff spec at apply time.

#### Scenario: BuffSpec with exclusion_group loads successfully

- **WHEN** a buff manifest declares `exclusion_group: thorns` and `priority: 60`
- **THEN** the manifest loads without error and those values are accessible on `BuffSpec`

#### Scenario: Priority without exclusion_group emits a load warning

- **WHEN** a buff manifest declares `priority: 60` but no `exclusion_group`
- **THEN** a load warning is emitted and the manifest is still loaded successfully

#### Scenario: Variable name priority resolves against variables

- **WHEN** a buff manifest declares `priority: "strength"` and `variables: {strength: 0}` and is applied with `variables: {strength: 50}`
- **THEN** `ActiveCombatEffect.priority` equals `50`

#### Scenario: String priority referencing undeclared variable is rejected at load time

- **WHEN** a buff manifest declares `priority: "undeclared_var"` but does not list `undeclared_var` in `variables`
- **THEN** a load-time validation error is raised

---

### Requirement: apply_buff enforces exclusion group gating and replacement

When dispatching `ApplyBuffEffect`, after the buff manifest is resolved and variables are merged, the engine SHALL:

1. **Resolve priority** — if `spec.priority` is a template string, evaluate it against the merged variables dict and cast to `int`.
2. **Scan** `CombatContext.active_effects` for existing entries where `ae.exclusion_group == incoming_exclusion_group` (non-empty) and `ae.target == incoming_target`.
3. If **any** such entry has `ae.priority >= incoming_priority`, skip the application with a DEBUG log. No `ActiveCombatEffect` is added. (This applies in both `"block"` and `"replace"` modes.)
4. If **all** such entries have `ae.priority < incoming_priority`:
   - In `"replace"` mode, remove all same-group same-target entries from `CombatContext.active_effects` before applying the new one.
   - In `"block"` mode (default), apply the new effect without touching existing lower-priority entries.
5. When `incoming_exclusion_group` is empty (buff has no group), no exclusion check is performed and the application always proceeds.

#### Scenario: Weaker buff blocked by stronger same-group buff

- **WHEN** `thorns-60pct` (exclusion_group=thorns, priority=60) is already active
- **AND** `apply_buff` fires for `thorns-30pct` (exclusion_group=thorns, priority=30, target=player)
- **THEN** the `thorns-30pct` application is skipped
- **THEN** `CombatContext.active_effects` still has exactly one entry for the thorns group

#### Scenario: Stronger buff in block mode does not evict weaker same-group buff

- **WHEN** `thorns-30pct` (exclusion_group=thorns, priority=30, exclusion_mode=block) is already active
- **AND** `apply_buff` fires for `thorns-60pct` (exclusion_group=thorns, priority=60, exclusion_mode=block, target=player)
- **THEN** `thorns-60pct` is applied successfully
- **THEN** `CombatContext.active_effects` contains both entries (lower-priority entry expires naturally)

#### Scenario: Stronger buff in replace mode evicts weaker same-group buff

- **WHEN** `thorns-30pct` (exclusion_group=thorns, priority=30, exclusion_mode=replace) is already active
- **AND** `apply_buff` fires for `thorns-60pct` (exclusion_group=thorns, priority=60, exclusion_mode=replace, target=player)
- **THEN** `thorns-30pct` is removed from `CombatContext.active_effects`
- **THEN** `thorns-60pct` is applied
- **THEN** `CombatContext.active_effects` contains exactly one thorns-group entry

#### Scenario: Variable-driven priority enables same manifest to replace weaker application

- **WHEN** a `thorns` buff with `priority: "strength"` and `variables: {strength: 0}` is active with `variables: {strength: 30}`
- **AND** `apply_buff` fires for `thorns` with `variables: {strength: 50}` and `exclusion_mode=replace`
- **THEN** the weaker (strength=30) entry is evicted
- **THEN** the stronger (strength=50) entry is applied
- **THEN** `CombatContext.active_effects` contains exactly one thorns-group entry with priority=50

#### Scenario: Equal priority blocks application

- **WHEN** an effect (exclusion_group=shield, priority=50) is already active
- **AND** `apply_buff` fires for a second buff (exclusion_group=shield, priority=50, target=player)
- **THEN** the second application is skipped

#### Scenario: Buffs in different groups do not block each other

- **WHEN** an effect with `exclusion_group=thorns` is already active
- **AND** `apply_buff` fires for a buff with `exclusion_group=shield` (different group)
- **THEN** both effects are active simultaneously

#### Scenario: Buff without exclusion group is never blocked

- **WHEN** a buff with no `exclusion_group` is applied multiple times
- **THEN** each application succeeds, adding a new `ActiveCombatEffect` each time

#### Scenario: Same-group check is per-target

- **WHEN** an effect with `exclusion_group=poison`, `priority=50`, `target=player` is active
- **AND** `apply_buff` fires for `exclusion_group=poison`, `priority=30`, `target=enemy`
- **THEN** the enemy-targeted application proceeds (different target, no blocking)
