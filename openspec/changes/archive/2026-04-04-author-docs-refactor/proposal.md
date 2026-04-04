## Why

The current `docs/authors/` section has grown incrementally and is no longer a coherent learning resource. A single 1,500-line monolith (`content-authoring.md`) mixes reference tables with shallow examples, has no tutorial for newcomers, and does not reflect the engine's authoring model (conditions, effects, templates as three interconnected surfaces). Content authors — who may not be programmers — deserve documentation that teaches by example, builds understanding progressively, and makes it easy to find answers quickly.

## What Changes

- **DELETE** `docs/authors/content-authoring.md` — replaced entirely by the new structure
- **DELETE** `docs/authors/pronouns.md` — content folded into `templates.md` and `game-configuration.md`
- **REWRITE** `docs/authors/skills.md` — restructured to match new how-to + reference format
- **REWRITE** `docs/authors/passive-effects.md` — restructured to match new how-to + reference format
- **REWRITE** `docs/authors/README.md` — becomes a navigation hub with quick-path table and deep-links to reference sections within each file
- **NEW** `docs/authors/getting-started.md` — end-to-end tutorial building a minimal complete game
- **NEW** `docs/authors/conditions.md` — how conditions work + full predicate reference
- **NEW** `docs/authors/effects.md` — how effects work + full effect type reference
- **NEW** `docs/authors/templates.md` — Jinja2 in Oscilla: player context, functions, filters, pronoun placeholders + reference
- **NEW** `docs/authors/game-configuration.md` — `game.yaml`, `character_config.yaml`, stats, labels, XP/HP, pronoun sets
- **NEW** `docs/authors/world-building.md` — regions, locations, unlock conditions, adventure pools
- **NEW** `docs/authors/adventures.md` — steps, branching, choices, goto, narrative structure
- **NEW** `docs/authors/items.md` — consumables, equippable gear, labels, charges, requirements
- **NEW** `docs/authors/enemies.md` — enemy stats, loot tables
- **NEW** `docs/authors/quests.md` — multi-stage storylines and milestone tracking
- **NEW** `docs/authors/recipes.md` — crafting and ingredient transformation
- **NEW** `docs/authors/cookbook/README.md` — browsable index of cross-system pattern examples
- **NEW** `docs/authors/cookbook/reputation-system.md` — tracking faction standing with stats + conditions
- **NEW** `docs/authors/cookbook/locked-doors.md` — item-gated paths and key/lock patterns
- **NEW** `docs/authors/cookbook/day-night-narrative.md` — seasonal and time-based text variants

## Capabilities

### New Capabilities

- `author-docs`: The complete `docs/authors/` documentation section — structured as a coherent set of how-to guides with embedded reference sections, a getting-started tutorial, and an extensible cookbook directory.

### Modified Capabilities

<!-- No existing engine specs change — this is a pure documentation change. -->

## Impact

- No engine code changes.
- No test changes.
- `docs/authors/README.md` gains a quick-path navigation table with anchor deep-links into the reference sections of each file.
- The `docs/dev/README.md` link to author docs remains valid (points to `docs/authors/README.md`).
- Testlandia content is unaffected; this is documentation only.
