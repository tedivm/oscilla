# Content Author Documentation

Welcome to the Oscilla content author documentation. These guides explain how to craft game content using YAML manifests — regions, adventures, enemies, items, and everything else that makes up your game world.

If you're working on the engine itself, see the [Developer Documentation](../dev/README.md) instead.

---

## How Oscilla Is Built for Authors

### Narrative first

Oscilla is a narration engine. Every mechanic — combat, inventory, quests, skill checks — exists to serve the story you want to tell, not the other way around. Adventures are built from steps that print text, present choices, and react to what the player has done. The mechanics are the scaffolding; the words on the screen are the game.

### No genre lock-in

The engine ships with no opinions about what kind of game you are making. There is no hardcoded class system, no fixed rarity scale, no required faction structure, no assumed combat model (or at least there are plans to make that last one more flexible). Anything the engine needs to name — item qualities, character archetypes, factions, skill categories — you define in `game.yaml` using your own vocabulary. A game set in a trading company uses completely different labels than a dungeon-crawler, and neither one has to fight the engine to express that.

### Skip what you don't need

Every system is opt-in. A game without crafting simply has no recipe manifests. A game without skills skips that section of `character_config.yaml`. A game without quests has no quest manifests. Nothing in the engine requires boilerplate you aren't using, and ignoring a system entirely produces no errors or warnings.

### One vocabulary, everywhere

You will learn three core systems — **conditions**, **effects**, and **templates** — and they work identically in every manifest kind. The condition that checks a player's level on an adventure's `requires` field uses the exact same syntax as the condition that gates a passive effect, unlocks a region, or branches a stat check. Learn it once; use it everywhere.

### No programming needed

Everything is data. Your entire game is written in YAML manifest files that declare what exists, what it does, and what conditions govern it. There is no scripting language, no Python, no code. The engine evaluates your manifests at runtime and handles all the logic.

---

## New Authors: Start Here

1. **[Getting Started](./getting-started.md)** — Build your first complete game from scratch in a single tutorial. Create a region, location, enemy, and adventure, then play it immediately.

---

## The Authoring Model

These documents explain the three cross-cutting systems you'll use in almost everything you write.

| Guide                         | What it covers                                                                                                                                                                                       |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Conditions](./conditions.md) | All condition types — level, milestone, item, stat, skill, calendar/time predicates, and logical operators. Used in unlock gates, adventure requirements, stat checks, and choice option visibility. |
| [Effects](./effects.md)       | All effect types — XP, item drops, stat changes, milestones, skills, flow control, and combat buffs. Used anywhere something happens: adventure outcomes, skill use, item use.                       |
| [Templates](./templates.md)   | Jinja2 templates in narrative text — player context, mathematical functions, calendar functions, filters, and pronoun placeholders.                                                                  |

---

## Building Your Game

These documents cover each manifest kind in depth.

| Guide                                         | What it covers                                                                                                                     |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| [Game Configuration](./game-configuration.md) | `game.yaml` and `character_config.yaml` — XP thresholds, HP formula, item labels, stats, equipment slots, custom pronoun sets.     |
| [In-Game Time](./ingame-time.md)              | Calendar cycles, dual clocks, eras, tick-based cooldowns, and time conditions.                                                     |
| [World Building](./world-building.md)         | Regions, nested regions, locations, adventure pools, unlock conditions.                                                            |
| [Adventures](./adventures.md)                 | Narrative, combat, choice, and stat-check steps; goto/labels; outcome branches.                                                    |
| [Items](./items.md)                           | Consumables, gear, charges, equip requirements, labels, skill/buff grants.                                                         |
| [Enemies](./enemies.md)                       | Combat stats, loot tables, enemy skills and resources.                                                                             |
| [Skills](./skills.md)                         | Skill and Buff manifests, costs, cooldowns, buff modifiers, item skill/buff grants, enemy skills, CharacterConfig skill resources. |
| [Passive Effects](./passive-effects.md)       | Always-on and condition-gated stat bonuses and skill grants declared in `game.yaml`.                                               |
| [Quests](./quests.md)                         | Multi-stage storylines with milestone-driven stage advancement.                                                                    |
| [Recipes](./recipes.md)                       | Crafting formulas: input items + quantities → output item.                                                                         |

---

## Author CLI Tooling

| Guide                     | What it covers                                                                                                                                                                         |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [CLI Reference](./cli.md) | `oscilla content` commands — list, show, graph, schema, test, trace, create. Inspect content, generate graphs, export JSON schemas, trace adventure paths, and scaffold new manifests. |

---

## Quick Path by Goal

Not sure which guide to read? Find your goal:

| I want to…                                                 | Read                                                                                                                       |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Branch an adventure based on player level or a stat        | [Conditions §stat-check](./conditions.md) + [Adventures §stat-check](./adventures.md#stat-check)                           |
| Give the player XP, loot, or a stat change                 | [Effects](./effects.md)                                                                                                    |
| Make narrative text mention the player's stats or pronouns | [Templates](./templates.md)                                                                                                |
| Let players equip weapons and armor                        | [Game Configuration §equipment-slots](./game-configuration.md#equipment-slots) + [Items §gear](./items.md#equippable-gear) |
| Create a boss fight                                        | [Enemies](./enemies.md) + [Adventures §combat](./adventures.md#combat) + [Skills](./skills.md)                             |
| Track story progress across multiple adventures            | [Conditions §milestone](./conditions.md) + [Quests](./quests.md)                                                           |
| Let players craft items from materials                     | [Recipes](./recipes.md)                                                                                                    |
| Add skill abilities (heal, power attack, etc.)             | [Skills](./skills.md)                                                                                                      |
| Lock a region until the player is strong enough            | [World Building §unlocking-regions](./world-building.md#unlocking-regions)                                                 |
| Add pronoun options beyond the built-in three              | [Game Configuration §custom-pronoun-sets](./game-configuration.md#custom-pronoun-sets)                                     |

---

## Going Further: Cookbook

Ready-made patterns for common authoring challenges:

| Recipe                                                      | What it covers                                                                       |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| [Reputation System](./cookbook/reputation-system.md)        | Tracking player standing with a faction using a stat, conditions, and templates      |
| [Locked Doors](./cookbook/locked-doors.md)                  | Gating a choice behind a key item, one-time discovery, and item consumption          |
| [Day-Night Narrative](./cookbook/day-night-narrative.md)    | Writing text that changes based on the real system clock                             |
| [In-Game Time Patterns](./cookbook/ingame-time-patterns.md) | Seasonal events, era transitions, time skips, lunar gates, and time-reversal puzzles |

More recipes: [Cookbook README](./cookbook/README.md)
