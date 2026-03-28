## Why

This project is a brand-new codebase started from a template with no game logic. We need to build the foundational game engine — the manifest system, content loader, condition evaluator, and adventure pipeline — along with a playable CLI experience, so that the system is runnable end-to-end before adding persistence or a web interface.

## What Changes

- Introduce a YAML manifest system for defining all game content (regions, locations, adventures, enemies, items, recipes, quests, classes)
- Build a content loader that scans a configurable content directory, parses manifests, validates schemas, and resolves cross-references
- Build a condition evaluator that determines visibility and availability based on player state (level, milestones, inventory, stats)
- Build an adventure pipeline runner that executes ordered, typed steps (narrative, combat, choice, item_drop, milestone_grant, xp_grant, stat_check)
- Build an in-memory player state model covering stats, inventory, equipment, milestones, quests, and active adventure
- Build a menu-driven TUI CLI game loop: select region → select location → run adventure → repeat
- Add a `validate` CLI command for content creators to catch manifest errors without running the game
- Ship a POC game as the default content package (generic fantasy kingdom, ~3 regions, ~10 locations, ~20 adventures, ~15 enemies, ~30 items)

## Capabilities

### New Capabilities

- `manifest-system`: YAML-based content manifest format with typed schemas for all entity kinds (Region, Location, Adventure, Enemy, Item, Recipe, Quest, Class), including the `apiVersion`/`kind`/`metadata`/`spec` structure, cross-reference validation, and region/location inheritance of unlock conditions
- `condition-evaluator`: Rules engine that evaluates logical condition trees (`all`, `any`, `not`) against player state; conditions include level thresholds, milestone flags, inventory checks, stat comparisons, and class membership
- `adventure-pipeline`: Composable, ordered step execution engine for adventures; step types: `narrative`, `combat` (turn-based), `choice` (branching), `item_drop` (weighted loot), `milestone_grant`, `xp_grant`, `stat_check`
- `player-state`: In-memory player state model covering level, XP, HP, stats (strength/dexterity/wisdom), gold, inventory, equipment, milestones, statistics (enemy kills/location visits/adventure completions), active quest stages, and active adventure position
- `cli-game-loop`: Menu-driven TUI game experience using Typer; flows: character creation → world map → region → location → adventure → outcome → repeat; includes a `validate` command for content creators
- `poc-content`: Default POC game content package — a generic fantasy kingdom with regions, locations, adventures, enemies, items, recipes, and quests sufficient to exercise all engine capabilities

### Modified Capabilities

<!-- None — this is a greenfield build on top of the template scaffold -->

## Impact

- New top-level package directories: `oscilla/engine/`, `oscilla/content/`
- New content directory (configurable path, default: `content/` at project root)
- New dependencies: `rich` (TUI rendering), `ruamel.yaml` (manifest parsing)
- Existing `oscilla/cli.py` extended with new game and validate commands
- Existing `oscilla/models/` will gain player state models in a future phase (persistence); this phase is intentionally stateless
- Tests must cover the condition evaluator, content loader validation, and adventure pipeline execution
