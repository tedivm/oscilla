## Context

The `docs/authors/` directory is the primary resource for content authors building games with Oscilla. It currently contains four files: a 1,500-line monolith (`content-authoring.md`) that covers everything from package structure to Jinja2 templates, plus three spin-off files (`skills.md`, `passive-effects.md`, `pronouns.md`) that were extracted as afterthoughts but left the core document unrestructured.

The result fails on multiple fronts:

- **No learning path.** There is no tutorial. A new author opening `content-authoring.md` is immediately confronted with envelope format, every manifest kind, all condition types, all effect types, and Jinja2 — in one scroll.
- **Reference masquerading as instruction.** Sections list YAML fields and types without explaining intent, mental models, or authoring goals.
- **The engine's authoring model is invisible.** The design philosophy explicitly names conditions, effects, and templates as three interconnected surfaces for the same character state. The current docs never surface this insight; conditions appear in the middle of the file sandwiched between manifest kinds.
- **No cross-system patterns.** Authors cannot see how systems compose — how a reputation mechanic uses stats + conditions + templates together.
- **Pronouns are orphaned.** `pronouns.md` is a standalone syntax reference with no connection to the broader template system or writing context.

This change is a complete rewrite of `docs/authors/` — not an edit, not a reorganization. Every file is authored from scratch against the finalized structure.

## Goals / Non-Goals

**Goals:**

- Replace `content-authoring.md` and `pronouns.md` with a structured set of focused documents
- Rewrite `skills.md` and `passive-effects.md` to match the new how-to + reference format
- Produce a `getting-started.md` tutorial that takes a new author from zero to a working minimal game
- Surface the three-surface authoring model (conditions / effects / templates) as a first-class section
- Each document follows the pattern: intent → how-to → examples → reference section at end
- Create a `cookbook/` directory with an index and three initial recipes demonstrating cross-system composition
- Update `README.md` to serve as a navigation hub with quick paths and anchor deep-links to reference sections

**Non-Goals:**

- No engine code changes of any kind
- No changes to `docs/dev/` developer documentation
- No new engine features to document (all documented capabilities already exist in the engine)
- No changes to testlandia or the-example-kingdom content packages

## Decisions

### Decision 1: Embed references at the end of each how-to doc, not a separate reference directory

**Decision:** Each document (`conditions.md`, `effects.md`, etc.) closes with its own complete reference section — a lookup table for all types, fields, and options covered by that document.

**Rationale:** An author reading `conditions.md` to understand `item` conditions doesn't want to navigate to a separate `reference/conditions.md`. Co-locating reference with how-to reduces friction. Experienced authors who want quick lookup get anchor deep-links from `README.md` straight to the reference section.

**Alternative considered:** A dedicated `reference/` directory with pure lookup tables. Rejected because it creates two places to maintain the same information and forces navigation context-switches for the most common case (learning something and needing specifics at the same time).

### Decision 2: Pronoun syntax moves to `templates.md`; custom pronoun set configuration moves to `game-configuration.md`

**Decision:** The mechanical syntax (`{they}`, `{are}`, verb agreement, capitalization) lives in `templates.md` as a section. The `CharacterConfig` fields for defining custom pronoun sets live in `game-configuration.md`. `pronouns.md` is deleted.

**Rationale:** Pronoun placeholders are a template feature — their natural home is alongside Jinja2 expressions and filters. Custom pronoun set configuration is a game configuration concern — it belongs with the other `CharacterConfig` spec fields. Splitting them into a standalone file made both harder to find.

### Decision 3: Cookbook is a directory, not a single file

**Decision:** `docs/authors/cookbook/` is a directory with an index `README.md` and individual recipe files.

**Rationale:** A single file grows unwieldy as recipes accumulate. The directory structure lets authors navigate to a specific recipe without scrolling, and allows recipes to be linked individually. The `cookbook/README.md` index (a table of recipe name, systems used, and one-line description) keeps the collection browsable as it grows.

### Decision 4: Structure of each how-to document

**Decision:** Every document in "The Authoring Model" and "Building Your Game" sections follows this internal structure:

1. Opening paragraph explaining _what this system does for you as an author_ (intent)
2. A minimal worked example introduced early — build on it throughout
3. How-to sections organized by authoring goal, not by engine type name
4. A `## Reference` section at the end with complete lookup tables

**Rationale:** The design philosophy states the threshold for "expressive enough" is whether a non-programmer can build a complete game from manifests alone. Docs that lead with type catalogs work against that goal. Leading with intent and authoring goals, using the type catalog only as a reference at the end, serves the non-programmer author while still meeting the needs of experienced authors.

## Documentation Plan

This change _is_ the documentation. The following table specifies every file to be created or updated, its intended audience, and the topics it must cover.

| File                                           | Action  | Audience                           | Topics                                                                                                                                                                                                                                                                                                                                                                  |
| ---------------------------------------------- | ------- | ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/authors/README.md`                       | Rewrite | All authors — entry point          | Quick-path table ("I want to…"), grouped index matching section structure, anchor deep-links to reference sections in each file, link to `docs/dev/README.md`                                                                                                                                                                                                           |
| `docs/authors/getting-started.md`              | New     | First-time authors                 | Step-by-step: create package directory, `game.yaml`, `character_config.yaml`, one region, one location, one adventure with narrative + choice steps; run `oscilla validate`; run the game                                                                                                                                                                               |
| `docs/authors/conditions.md`                   | New     | All authors                        | What conditions are and where they appear; leaf condition types (level, milestone, item, character_stat, prestige_count, enemies_defeated, locations_visited, adventures_completed, skill, item_equipped, item_held_label, any_item_equipped); logical operators (all, any, not); reference table of all condition types with fields                                    |
| `docs/authors/effects.md`                      | New     | All authors                        | What effects are and where they appear; state change effects (xp_grant, stat_change, stat_set, item_drop, use_item, milestone_grant, skill_grant); combat effects (apply_buff, dispel); flow control (end_adventure, goto); reference table of all effect types with fields                                                                                             |
| `docs/authors/templates.md`                    | New     | All authors                        | When and where templates can be used; player context object; built-in functions; calendar/astronomical functions; filters; Jinja2 conditionals in text; pronoun placeholder syntax (`{they}`, `{are}`, etc.), verb agreement, capitalization; reference tables for functions, filters, pronouns                                                                         |
| `docs/authors/game-configuration.md`           | New     | All authors                        | `game.yaml` structure and fields; XP thresholds and leveling; HP formula; item labels; passive effects overview (link to passive-effects.md); `character_config.yaml` structure; stat types, default values, bounds; equipment slots; custom pronoun sets; reference tables for all fields                                                                              |
| `docs/authors/world-building.md`               | New     | All authors                        | Regions and region hierarchy; locations and adventure pools; unlock conditions; parent/child relationships; how the player navigates the world; reference tables                                                                                                                                                                                                        |
| `docs/authors/adventures.md`                   | New     | All authors                        | Adventure manifest overview; `requires` condition; step types (narrative, combat, choice, stat_check); step labels and goto; effects on steps; on_win/on_defeat/on_flee branches; how to structure branching narratives; reference tables for all step types and fields                                                                                                 |
| `docs/authors/items.md`                        | New     | All authors                        | What items are; stackable consumables; equippable gear; equipment slots and multi-slot items; item labels; item requirements (`equip.requires`, `stat_source: base`); item charges; use effects; `grants_skills_equipped`, `grants_skills_held`, `grants_buffs_equipped`; reference tables                                                                              |
| `docs/authors/enemies.md`                      | New     | All authors                        | Enemy manifest structure; level, HP, damage; loot tables and weighted drops; how enemies connect to combat steps; reference tables                                                                                                                                                                                                                                      |
| `docs/authors/skills.md`                       | Rewrite | Authors using combat/skill systems | What skills are; skill contexts (combat, overworld); activation costs and cooldowns; `use_effects`; `requires` condition on skills; buffs: what they are, duration, per-turn effects, passive modifiers (damage_reduction, damage_amplify, damage_reflect, damage_vulnerability); buff variables; `apply_buff` effect; `dispel` effect; reference tables for all fields |
| `docs/authors/passive-effects.md`              | Rewrite | Authors using passive systems      | What passive effects are; where they are declared (game.yaml); condition restrictions and why; stat modifiers; skill grants; interaction with effective stats; reference tables                                                                                                                                                                                         |
| `docs/authors/quests.md`                       | New     | All authors                        | Quest manifest; stages and milestone tracking; how quests surface to players; reference tables                                                                                                                                                                                                                                                                          |
| `docs/authors/recipes.md`                      | New     | Authors using crafting             | Recipe manifest; ingredients and quantities; result item; how crafting works in play; reference tables                                                                                                                                                                                                                                                                  |
| `docs/authors/cookbook/README.md`              | New     | Experienced authors                | Browsable index: recipe name, systems used, one-line description                                                                                                                                                                                                                                                                                                        |
| `docs/authors/cookbook/reputation-system.md`   | New     | Experienced authors                | Cross-system pattern: int stat for reputation, conditions to gate content by reputation tier, template display of current standing                                                                                                                                                                                                                                      |
| `docs/authors/cookbook/locked-doors.md`        | New     | Experienced authors                | Cross-system pattern: item as key, item condition gating a choice option, milestone to prevent re-triggering                                                                                                                                                                                                                                                            |
| `docs/authors/cookbook/day-night-narrative.md` | New     | Experienced authors                | Cross-system pattern: `today()` and `season()` in templates to vary narrative, calendar-based conditional text blocks                                                                                                                                                                                                                                                   |

**Files deleted:**

- `docs/authors/content-authoring.md`
- `docs/authors/pronouns.md`

## Testing Philosophy

This change is purely documentation — there is no engine code to test. Verification is editorial and structural.

**Completeness check (manual):** Each new file must cover all topics listed in the Documentation Plan table above. No topic listed should be absent.

**Accuracy check (manual):** All YAML examples in the new documents must be valid against the current engine. Each example should be cross-checked against the corresponding engine model (conditions in `oscilla/engine/`, manifest models, effect handlers).

**Cross-reference check (manual):** Every link between documents (e.g., `conditions.md` → `adventures.md`, `templates.md` → `game-configuration.md` for pronoun sets) must resolve correctly. No broken anchors.

**Navigation check (manual):** The anchor deep-links in `README.md` must target sections that exist in each file. The `## Reference` section in each doc must use a consistent heading so anchors are predictable.

**No regressions (automated):** The existing test suite must continue passing without modification. No engine files are changed.

## Risks / Trade-offs

**Risk: Content drift between docs and engine** → Documents are written against the current engine. As the engine evolves, examples may become stale. Mitigation: the `oscilla validate` command catches broken references in content packages; documentation examples should be simple enough that they are obviously correct and easy to update.

**Risk: Scope creep during authoring** → Writing 14 new documents risks expanding scope to document planned-but-unimplemented features. Mitigation: every example and reference table must reflect only currently-implemented behavior. Forward references to roadmap items are explicitly forbidden.

**Risk: Cookbook recipes become outdated faster than core docs** → Recipes demonstrate system composition at a higher level and may reference multiple features. If one underlying feature changes, the recipe may mislead. Mitigation: cookbook recipes should be simple enough (3–4 systems maximum) that ownership is clear, and they should link back to the canonical docs for each system.

## Testlandia Integration

This change makes no modifications to testlandia. All documented features are demonstrated through YAML examples in the documents themselves. Testlandia serves as the engine's QA environment for mechanics; it is not the vehicle for documentation examples.
