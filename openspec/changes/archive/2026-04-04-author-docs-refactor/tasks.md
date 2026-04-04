## 1. Preparation

- [x] 1.1 Delete `docs/authors/content-authoring.md`
- [x] 1.2 Delete `docs/authors/pronouns.md`
- [x] 1.3 Create `docs/authors/cookbook/` directory

## 2. The Authoring Model

- [x] 2.1 Write `docs/authors/conditions.md` — intent, worked examples for each condition type, logical operators, `## Reference` section with complete lookup table
- [x] 2.2 Write `docs/authors/effects.md` — intent, worked examples for each effect type organized by authoring goal, `## Reference` section with complete lookup table
- [x] 2.3 Write `docs/authors/templates.md` — Jinja2 in Oscilla, player context object, functions, calendar functions, filters, Jinja2 conditionals, pronoun placeholder syntax and verb agreement, `## Reference` section with tables for all functions/filters/pronouns

## 3. Building Your Game

- [x] 3.1 Write `docs/authors/game-configuration.md` — `game.yaml` fields (XP thresholds, HP formula, item labels, passive effects overview), `character_config.yaml` fields (stats, bounds, equipment slots, custom pronoun sets), reference tables
- [x] 3.2 Write `docs/authors/world-building.md` — regions, region hierarchy, locations, adventure pools, unlock conditions, reference tables
- [x] 3.3 Write `docs/authors/adventures.md` — manifest overview, all step types (narrative, combat, choice, stat_check), step labels and goto, effects on steps, on_win/on_defeat/on_flee, narrative structuring guidance, reference tables
- [x] 3.4 Write `docs/authors/items.md` — consumables, equippable gear, multi-slot items, item labels, item requirements with `stat_source: base`, item charges, skill/buff grants from items, reference tables
- [x] 3.5 Write `docs/authors/enemies.md` — manifest structure, stats, loot tables, weighted drops, reference tables
- [x] 3.6 Rewrite `docs/authors/skills.md` — restructure to lead with intent and worked examples; retain and update the complete reference section; cover skills, buffs, costs, cooldowns, item skill/buff grants
- [x] 3.7 Rewrite `docs/authors/passive-effects.md` — restructure to lead with intent and how-to; add rationale for condition restrictions; retain and update complete reference section
- [x] 3.8 Write `docs/authors/quests.md` — manifest structure, stages, milestone advancement, player-facing display, reference tables
- [x] 3.9 Write `docs/authors/recipes.md` — manifest structure, ingredients, result item, crafting in play, reference tables

## 4. Getting Started Tutorial

- [x] 4.1 Write `docs/authors/getting-started.md` — step-by-step tutorial: create package directory, `game.yaml`, `character_config.yaml`, one region, one location with adventure pool, one adventure with narrative + choice steps; run `oscilla validate`; run the game

## 5. Cookbook

- [x] 5.1 Write `docs/authors/cookbook/reputation-system.md` — cross-system pattern using int stat for reputation, conditions gating content by tier, template display of current standing; complete end-to-end worked example
- [x] 5.2 Write `docs/authors/cookbook/locked-doors.md` — cross-system pattern using item as key, item condition on a choice option, milestone to prevent re-triggering; complete worked example
- [x] 5.3 Write `docs/authors/cookbook/day-night-narrative.md` — cross-system pattern using `today()` and `season()` in Jinja2 conditional blocks to vary narrative text; complete worked example
- [x] 5.4 Write `docs/authors/cookbook/README.md` — browsable index table: recipe name, systems used, one-line description

## 6. Navigation and README

- [x] 6.1 Rewrite `docs/authors/README.md` — orientation paragraph, quick-path "I want to…" table, grouped index matching the section structure, anchor deep-links to `## Reference` sections in each document, link to `docs/dev/README.md`

## 7. Verification

- [x] 7.1 Confirm `docs/authors/content-authoring.md` no longer exists
- [x] 7.2 Confirm `docs/authors/pronouns.md` no longer exists
- [x] 7.3 Verify all pronoun placeholder syntax from the old `pronouns.md` appears in `templates.md`
- [x] 7.4 Verify all custom pronoun set configuration from the old `pronouns.md` appears in `game-configuration.md`
- [x] 7.5 Cross-check all YAML examples in new documents against current engine models for accuracy
- [x] 7.6 Verify all inter-document links and anchor deep-links in `README.md` resolve correctly
- [x] 7.7 Run `uv run pytest` and confirm all tests still pass (no engine changes, should be clean)
