# POC Content (delta)

## MODIFIED Requirements

### Requirement: POC content structure — items

> **Changed by this change**: The `kind` field is replaced by the required `category` field. Consumable items now declare `use_effects` using the adventure effect grammar. Equippable items now declare an `equip` spec with `StatModifier` entries. Items with an `equip` spec must set `stackable: false`.

The POC content SHALL define at least twenty-five items covering: consumables (e.g., health potion), weapons, armor, quest items, crafting materials, and at least one prestige-tagged item.

Each item manifest SHALL use the `category` field (not the deprecated `kind` field) as a required display-only string for inventory grouping. Consumable items SHALL declare `use_effects` using the adventure effect grammar. Equippable items SHALL declare an `equip` spec with at least one `StatModifier`. Items that are equippable SHALL set `stackable: false`.

#### Scenario: Item categories are represented

- **WHEN** the item registry is inspected
- **THEN** items with categories `consumable`, `weapon`, `armor`, `quest`, and `material` are all present

#### Scenario: Consumable items carry use effects

- **WHEN** an item with `use_effects` is loaded
- **THEN** each entry in `use_effects` is a valid typed Effect (e.g., `heal`, `xp_grant`)

#### Scenario: Equippable items declare slots and modifiers

- **WHEN** an item with an `equip` spec is loaded
- **THEN** `equip.slots` is non-empty and all slot names match entries in the game's `CharacterConfig.equipment_slots`
