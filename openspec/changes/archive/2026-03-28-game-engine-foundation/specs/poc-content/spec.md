## ADDED Requirements

### Requirement: POC content exercises all engine capabilities

The default POC content package SHALL include enough content to exercise every engine capability: manifest inheritance, condition evaluation (milestone, level, item, stat), every adventure step type and effect type, crafting (recipes), and quest stage progression.

#### Scenario: All step and effect types are present in POC content

- **WHEN** the POC content is loaded
- **THEN** at least one adventure exists exercising each event step type (narrative, combat, choice, stat_check) and each effect type (xp_grant, item_drop, milestone_grant, end_adventure)

#### Scenario: POC content passes validation

- **WHEN** `oscilla validate` is run against the default POC content directory
- **THEN** the command exits successfully with no errors

---

### Requirement: POC content structure — regions

The POC content SHALL define at least three regions arranged in a hierarchy: a starting region (always accessible), an intermediate wilderness region (requires progression), and a dungeon region (requires significant progression). At least one region SHALL have a parent region to exercise inheritance.

#### Scenario: Starting region is accessible at game start

- **WHEN** a new player is created
- **THEN** the starting region is accessible (its effective unlock condition is satisfied)

#### Scenario: Dungeon region requires progression

- **WHEN** a new player is evaluated against the dungeon region's effective unlock condition
- **THEN** the condition is not satisfied

---

### Requirement: POC content structure — locations

The POC content SHALL define at least ten locations distributed across the three regions. At least two locations SHALL have their own `unlock` conditions (in addition to inherited region conditions) to exercise the inheritance chain.

#### Scenario: Locations are distributed across regions

- **WHEN** the content registry is loaded
- **THEN** each region contains at least two locations

---

### Requirement: POC content structure — adventures

The POC content SHALL define at least fifteen adventures. At least half SHALL be combat adventures. At least three SHALL be non-combat (narrative or choice). At least two SHALL have `requires` conditions so that the pool-filtering logic is exercised.

#### Scenario: Combat adventures use enemy references

- **WHEN** a combat adventure is loaded
- **THEN** its combat step references an enemy that exists in the registry

#### Scenario: Conditional adventures are excluded when unmet

- **WHEN** the adventure pool for a location is computed for a new player
- **THEN** adventures with unmet conditions are absent from the pool

---

### Requirement: POC content structure — enemies

The POC content SHALL define at least ten enemies with varying stat levels. Enemies SHALL have at minimum: `name`, `displayName`, `hp`, `attack`, `defense`, and optionally a `loot_table`. At least three enemies SHALL have a loot table with multiple weighted entries.

#### Scenario: Enemy loads with expected fields

- **WHEN** an Enemy manifest is loaded
- **THEN** the registry entry contains hp, attack, and defense values

---

### Requirement: POC content structure — items

The POC content SHALL define at least twenty-five items covering: consumables (e.g., health potion), weapons, armor, quest items, crafting materials, and at least one prestige-tagged item.

#### Scenario: Item kinds are represented

- **WHEN** the item registry is inspected
- **THEN** items with kinds consumable, weapon, armor, quest, and material are all present

---

### Requirement: POC content structure — recipes

The POC content SHALL define at least five recipes. Each recipe SHALL specify one or more required input items with quantities and one output item. The crafting system is not fully implemented in this phase, but recipes must validate and load correctly.

#### Scenario: Recipe cross-references resolve

- **WHEN** a Recipe manifest is loaded
- **THEN** all referenced input and output item names exist in the item registry

---

### Requirement: POC content structure — quests

The POC content SHALL define at least two quests. Each quest SHALL have at least two stages. Stage advancement SHALL be tied to milestones so that the milestone system is exercised in a quest context.

#### Scenario: Quest stages are ordered

- **WHEN** a Quest manifest is loaded
- **THEN** stages are stored in declared order and the first stage is the entry point
