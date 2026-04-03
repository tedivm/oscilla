# Item Requirements

## Purpose

Allow equippable items to declare prerequisites using the standard condition evaluator. A player who does not meet the requirement cannot equip the item via the TUI. The condition is evaluated against the player's full effective stats — including bonuses from currently equipped items and active passive effects — so that gear dependencies and synergies work as authors and players expect.

---

## Requirements

### Requirement: EquipSpec accepts an optional requires condition

`EquipSpec` SHALL accept a `requires: Condition | None` field (default `None`). Any condition type from the standard `Condition` union is valid. When `requires` is `None`, the item can be equipped by anyone.

#### Scenario: Item with no requires can be equipped freely

- **WHEN** an item's `equip` spec has no `requires` field
- **THEN** any player can equip the item regardless of stats or milestones

#### Scenario: Item with requires condition loads correctly

- **WHEN** an item declares `equip: {slots: [main_hand], requires: {character_stat: {name: strength, gte: 15}}, stat_modifiers: []}`
- **THEN** the manifest parses into an `EquipSpec` with a non-None `requires` condition

---

### Requirement: TUI equip action enforces requires condition using the full condition system

When a player attempts to equip an item via the TUI inventory screen, the engine SHALL evaluate `EquipSpec.requires` using `evaluate(condition, player, registry=registry, exclude_item=item_ref)`. Any condition type from the `Condition` union is valid in `requires`.

- `stat_source: "effective"` (the default on `CharacterStatCondition`) computes `player.effective_stats(registry, exclude_item=item_ref)`, which includes all currently-equipped gear and active passive bonuses but excludes the item being tested. This prevents circular self-justification.
- `stat_source: "base"` enforces a raw stat floor that gear cannot satisfy; `player.stats` is used directly.

If the condition evaluates false, the equip action SHALL be blocked. The TUI SHALL display a message explaining the requirement was not met; it SHOULD include the specific condition that failed where possible.

**Why exclude_item is needed:** Without it, an item that provides `+5 strength` and requires `strength >= 15` would appear satisfiable for a player with base strength 12 if the item somehow ended up equipped already (e.g., after a save migration), but would fail for a new equip attempt — producing inconsistent behavior.

#### Scenario: Player meets requirement via base stats — equip succeeds

- **WHEN** an item requires `strength >= 15` (`stat_source: effective`) and the player's base strength is 17
- **THEN** the equip action proceeds normally

#### Scenario: Player does not meet requirement — equip blocked

- **WHEN** an item requires `strength >= 15` and the player's effective strength (after accounting for all equipped gear) is 10
- **THEN** the equip action is blocked and the TUI shows a message indicating the requirement

#### Scenario: Player meets requirement via an equipped item's bonus — equip succeeds

- **WHEN** an item requires `strength >= 15` (`stat_source: effective`), the player's base strength is 12, and an already-equipped ring provides `+5 strength`
- **THEN** effective strength is 17 (excluding the item being equipped, which is not yet in the slot) and the equip action proceeds normally

#### Scenario: The item's own stat bonus is excluded from its own check

- **WHEN** an item requires `strength >= 15` and provides `+5 strength`, and the player's base strength is 12
- **THEN** the equip action is blocked because effective stats during the check exclude the item's own `+5` contribution (effective strength = 12)

#### Scenario: stat_source base enforces a raw stat floor

- **WHEN** an item requires `character_stat: {name: constitution, gte: 8, stat_source: base}` and the player has base constitution 7 but an equipped item provides `+3 constitution`
- **THEN** the equip action is blocked — base constitution is 7, and `stat_source: base` ignores gear

#### Scenario: Passive effect providing the boost does not apply if gated on the item under consideration

- **WHEN** a passive effect activates only when item X is equipped, the player does not have item X equipped, and item X requires `strength >= 15` that would only be met via that passive effect
- **THEN** the equip action is blocked because the passive effect is not active during the check

---

### Requirement: Unequipping an enabling item cascades to dependent items

After the player unequips item B, the engine SHALL re-evaluate `requires` for all remaining equipped items using `evaluate(c.equip.requires, player, registry=registry, exclude_item=c.name)` for each remaining item C. Passing `exclude_item=c.name` ensures each item's own stat bonuses do not mask a legitimate requirement failure. Any item C whose condition evaluates false SHALL be automatically unequipped. The TUI SHALL display a notification listing each cascade-unequipped item and the condition that was no longer satisfied. The cascade repeats until no further items fail (fixed-point), handling chains of stat dependencies.

#### Scenario: Unequipping Ring of Strength cascades to Vorpal Blade

- **GIVEN** a Ring of Strength is equipped providing `+5 strength`, and a Vorpal Blade is equipped requiring `strength >= 15`
- **AND** the player's base strength is 12 (effective 17 with ring)
- **WHEN** the player unequips the Ring of Strength
- **THEN** the engine re-validates, finds Vorpal Blade's requirement is no longer met (effective strength now 12), and auto-unequips the Vorpal Blade
- **AND** the TUI shows a notification: "Vorpal Blade was unequipped because its requirement is no longer met"

#### Scenario: Unequipping item with no dependent requirements has no cascade

- **WHEN** the player unequips an item and no remaining equipped items' `requires` conditions are affected
- **THEN** no cascade occurs and no additional notification is shown

---

### Requirement: Stat-changing effects re-validate equipped items

After any engine effect that modifies `player.stats` directly (e.g., `stat_set`, `stat_modify`), the engine SHALL re-evaluate `requires` for all equipped items. Any item whose `requires` condition now evaluates false SHALL be automatically unequipped with a TUI notification, using the same fixed-point cascade as the unequip path.

#### Scenario: Level-down effect that reduces a stat triggers cascade

- **WHEN** a level-down effect reduces the player's strength below a sword's requirement threshold
- **THEN** the sword is automatically unequipped with a notification

#### Scenario: Stat increase does not trigger unequip

- **WHEN** a stat-boosting effect increases a stat
- **THEN** no equipped items are unequipped (conditions can only become more likely to pass, not fail, from a stat increase)

---

### Requirement: requires condition is validated at load time

All stat names, milestone names, skill names, and other references in `EquipSpec.requires` SHALL be validated by the content loader in the same pass as other cross-references. Unknown references SHALL produce a `LoadError`.

#### Scenario: Unknown stat in requires is a load error

- **WHEN** an item's `equip.requires` references `character_stat: {name: nonexistent-stat, gte: 5}`
- **THEN** the content loader raises a `LoadError` identifying the item and the unknown stat

---

### Requirement: Slot reconciliation on load does not enforce requires

When player state is loaded from persistence, the engine SHALL NOT force-unequip items whose `requires` conditions are not satisfied. A `WARNING` SHALL be logged per invalid item. The TUI status panel SHALL surface each inconsistency with a visible indicator so the player can resolve it manually. No state mutation occurs on load.

This policy differs from active-session behavior (cascade unequip) because load time is not a player-initiated action — silently mutating the saved character state would be data loss from the player's perspective.

#### Scenario: Equipped item with unmet requirement on load

- **WHEN** a character is loaded with an item equipped and that item's `requires` condition is now false (e.g., a stat was reduced by a level-down effect between sessions)
- **THEN** the item remains equipped, a logger WARNING is emitted, and the TUI status panel shows a notification about the slot inconsistency
- **AND** the player may manually unequip the item if they choose
