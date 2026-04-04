# Author Documentation

## Purpose

A complete, structured documentation suite for content authors. Each major authoring concern (conditions, effects, templates, world-building, adventures, items, enemies, skills, passive effects, quests, recipes) has its own standalone how-to guide, supplemented by a navigation hub, a getting-started tutorial, and a cookbook of cross-system composition recipes.

---

## Requirements

### Requirement: Author documentation has a navigation hub

The `docs/authors/README.md` file SHALL serve as the primary entry point for all content authors, providing a quick-path navigation table and anchor deep-links to the reference sections embedded within each document.

#### Scenario: New author finds where to start

- **WHEN** a new author opens `docs/authors/README.md`
- **THEN** they find a "I want to…" quick-path table directing them to the appropriate starting document

#### Scenario: Experienced author finds a reference section quickly

- **WHEN** an experienced author wants to look up a specific condition type
- **THEN** `README.md` contains an anchor deep-link that jumps directly to the reference section of `conditions.md`

---

### Requirement: A getting-started tutorial exists

The `docs/authors/getting-started.md` file SHALL provide a step-by-step tutorial that takes a first-time author from an empty directory to a working minimal game they can play.

#### Scenario: Author completes the tutorial

- **WHEN** an author follows all steps in `getting-started.md`
- **THEN** they have created a valid content package with at least one region, one location, and one adventure containing a narrative step and a choice step

#### Scenario: Tutorial validates successfully

- **WHEN** an author runs `oscilla validate` after completing the tutorial
- **THEN** the validator reports no errors

---

### Requirement: Conditions are documented as a standalone how-to guide

The `docs/authors/conditions.md` file SHALL explain what conditions are, where they appear across manifests, how all condition types work, and how to compose them with logical operators.

#### Scenario: Author learns how to gate an adventure by level

- **WHEN** an author reads `conditions.md`
- **THEN** they find a worked example showing a `level` condition on an adventure's `requires` field

#### Scenario: Author finds the complete condition reference

- **WHEN** an author scrolls to the end of `conditions.md`
- **THEN** they find a `## Reference` section with a table of all condition types, their fields, and valid values

#### Scenario: Author learns how to combine conditions

- **WHEN** an author reads `conditions.md`
- **THEN** they find examples of `all`, `any`, and `not` operators with working YAML

---

### Requirement: Effects are documented as a standalone how-to guide

The `docs/authors/effects.md` file SHALL explain what effects are, where they can be placed, how all effect types modify game state, and how to compose multiple effects on a single step.

#### Scenario: Author learns how to grant XP after a combat win

- **WHEN** an author reads `effects.md`
- **THEN** they find a worked example of `xp_grant` in a combat step's `on_win` block

#### Scenario: Author finds the complete effect reference

- **WHEN** an author scrolls to the end of `effects.md`
- **THEN** they find a `## Reference` section with a table of all effect types, their fields, and valid values

---

### Requirement: Templates are documented as a standalone how-to guide

The `docs/authors/templates.md` file SHALL explain Jinja2 template usage in Oscilla narrative text and numeric fields, covering the player context object, all built-in functions, all filters, and pronoun placeholder syntax.

#### Scenario: Author learns how to reference a player stat in narrative text

- **WHEN** an author reads `templates.md`
- **THEN** they find an example using `{{ player.stats.<name> }}` in a narrative step's `text` field

#### Scenario: Author learns pronoun placeholder syntax

- **WHEN** an author reads `templates.md`
- **THEN** they find the complete pronoun placeholder table (`{they}`, `{them}`, `{their}`, `{is}`, `{are}`, etc.) with example output for multiple pronoun sets

#### Scenario: Author finds the complete template reference

- **WHEN** an author scrolls to the end of `templates.md`
- **THEN** they find a `## Reference` section with tables for all functions, filters, and pronoun placeholders

---

### Requirement: Game configuration is documented as a standalone how-to guide

The `docs/authors/game-configuration.md` file SHALL cover `game.yaml` and `character_config.yaml` structure and all their fields, including stats, item labels, XP thresholds, HP formula, equipment slots, and custom pronoun sets.

#### Scenario: Author learns how to define a custom stat

- **WHEN** an author reads `game-configuration.md`
- **THEN** they find a worked example of a stat definition in `character_config.yaml` with `name`, `type`, `default`, and optional `bounds`

#### Scenario: Author learns how to configure item labels

- **WHEN** an author reads `game-configuration.md`
- **THEN** they find an example declaring `item_labels` in `game.yaml` with `name`, `color`, and `sort_priority`

#### Scenario: Author learns how to define custom pronoun sets

- **WHEN** an author reads `game-configuration.md`
- **THEN** they find the `CharacterConfig` pronoun set configuration fields with a worked example

---

### Requirement: World-building is documented as a standalone how-to guide

The `docs/authors/world-building.md` file SHALL explain regions, locations, region hierarchy, unlock conditions, and adventure pools.

#### Scenario: Author creates a locked region unlocked by milestone

- **WHEN** an author reads `world-building.md`
- **THEN** they find a worked example of a region with a `milestone` unlock condition

#### Scenario: Author learns how to set adventure pool weights

- **WHEN** an author reads `world-building.md`
- **THEN** they find an example location with multiple adventure pool entries and weights explained

---

### Requirement: Adventures are documented as a standalone how-to guide

The `docs/authors/adventures.md` file SHALL cover all adventure step types, branching with choice steps, stat check branching, combat steps with outcome branches, goto and labels, and how to structure a multi-branch adventure.

#### Scenario: Author creates a branching choice adventure

- **WHEN** an author reads `adventures.md`
- **THEN** they find a complete worked example of a choice step with conditional options using `requires`

#### Scenario: Author learns how to use goto for loops

- **WHEN** an author reads `adventures.md`
- **THEN** they find an example using `label` on a step and a `goto` effect targeting that label

---

### Requirement: Items are documented as a standalone how-to guide

The `docs/authors/items.md` file SHALL cover consumable items, equippable gear, equipment slots, item labels, item requirements, item charges, and item skill/buff grants.

#### Scenario: Author creates a healing potion

- **WHEN** an author reads `items.md`
- **THEN** they find a complete stackable consumable example with `use_effects` and `consumed_on_use`

#### Scenario: Author creates gear with an equipment requirement

- **WHEN** an author reads `items.md`
- **THEN** they find an example of `equip.requires` with `stat_source: base` and an explanation of why `base` is recommended

---

### Requirement: Enemies are documented as a standalone how-to guide

The `docs/authors/enemies.md` file SHALL cover enemy manifest structure, stats, and loot tables with weighted drops.

#### Scenario: Author creates an enemy with a loot table

- **WHEN** an author reads `enemies.md`
- **THEN** they find a complete enemy example with `loot_table` entries and weights explained

---

### Requirement: Skills and buffs are rewritten to follow the how-to + reference format

The `docs/authors/skills.md` file SHALL be rewritten so that it leads with intent and authoring goals rather than field tables, while retaining its complete reference section at the end. It SHALL cover skills, buffs, costs, cooldowns, skill item grants, and buff item grants.

#### Scenario: Author creates a skill with a mana cost

- **WHEN** an author reads `skills.md`
- **THEN** they find a worked example of a skill with `cost.stat` and `cost.amount` before encountering the reference table

---

### Requirement: Passive effects are rewritten to follow the how-to + reference format

The `docs/authors/passive-effects.md` file SHALL be rewritten so that it leads with intent and authoring goals, explains condition restrictions with rationale, and retains a complete reference section at the end.

#### Scenario: Author understands why certain conditions cannot be used in passive effects

- **WHEN** an author reads `passive-effects.md`
- **THEN** they find an explanation of why `item_held_label` and `any_item_equipped` produce load warnings, not just a warning that they do

---

### Requirement: Quests are documented as a standalone how-to guide

The `docs/authors/quests.md` file SHALL cover quest manifest structure, stages, milestone advancement, and how quests surface to players.

#### Scenario: Author creates a multi-stage quest

- **WHEN** an author reads `quests.md`
- **THEN** they find a complete quest example with three stages and `advance_milestone` fields

---

### Requirement: Recipes are documented as a standalone how-to guide

The `docs/authors/recipes.md` file SHALL cover recipe manifest structure, ingredients, quantities, and result items.

#### Scenario: Author creates a crafting recipe

- **WHEN** an author reads `recipes.md`
- **THEN** they find a complete recipe example with multiple ingredients and a result item

---

### Requirement: A cookbook directory exists with an index and initial recipes

The `docs/authors/cookbook/` directory SHALL contain a `README.md` index and at least three initial recipe files demonstrating cross-system composition patterns.

#### Scenario: Author browses the cookbook for inspiration

- **WHEN** an author opens `docs/authors/cookbook/README.md`
- **THEN** they find a table listing each recipe with the systems it uses and a one-line description

#### Scenario: Author follows the reputation system recipe

- **WHEN** an author reads `cookbook/reputation-system.md`
- **THEN** they find a complete worked example using an int stat, conditions gating content by reputation tier, and a template displaying current standing — with all three systems woven together in one narrative scenario

#### Scenario: Author follows the locked doors recipe

- **WHEN** an author reads `cookbook/locked-doors.md`
- **THEN** they find a complete worked example using an item condition on a choice option and a milestone to prevent re-triggering

#### Scenario: Author follows the day/night narrative recipe

- **WHEN** an author reads `cookbook/day-night-narrative.md`
- **THEN** they find a complete worked example using `today()` and `season()` inside a Jinja2 conditional block to vary narrative text

---

### Requirement: Old monolith documents are removed

The files `docs/authors/content-authoring.md` and `docs/authors/pronouns.md` SHALL be deleted. No content from these files SHALL be lost — all information must be present in the new documents.

#### Scenario: All content from content-authoring.md is accounted for

- **WHEN** the refactor is complete
- **THEN** every topic previously covered in `content-authoring.md` is documented in one of the new files

#### Scenario: Pronoun syntax reference is findable

- **WHEN** an author needs the pronoun placeholder table that was previously in `pronouns.md`
- **THEN** they find it in the `## Reference` section of `templates.md`

#### Scenario: Custom pronoun set configuration is findable

- **WHEN** an author needs to configure custom pronoun sets
- **THEN** they find it in `game-configuration.md` under the `CharacterConfig` section
