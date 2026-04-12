# Roadmap

Ideas and future directions that are explicitly out of scope for current work but should not be forgotten.

---

## Effort Scale

| Label  | Meaning                                                                                   |
| ------ | ----------------------------------------------------------------------------------------- |
| **XS** | Trivial addition — touches one file or a narrow code path, no design required             |
| **S**  | Small, well-scoped feature — limited to a single subsystem with minimal interface changes |
| **M**  | Moderate feature — requires design work and touches a few interconnected components       |
| **L**  | Significant feature — spans multiple engine subsystems and requires coordinated changes   |
| **XL** | Major system — requires full architectural design and changes across the entire stack     |

## Summary

Items sharing a **Group** label can be scoped and worked on together as a single change.

### High Priority

These items fix existing bugs, remove technical debt that actively misleads authors or degrades engine correctness, or introduce breaking changes to existing content or saves. They should be addressed before other roadmap work to ensure authors and players are not left with incompatible data or content.

Since this project has not had a v1 release yet it is acceptable to break backwards compatibility, but we want to prioritize those features before the v1 release.

| Item | Effort | Group |
| ---- | ------ | ----- |

> All pre-v1 items have been implemented.

### All Items

| Item                                                                                            | Effort | Group                   |
| ----------------------------------------------------------------------------------------------- | ------ | ----------------------- |
| [Decision Tree AI for Enemies](#decision-tree-ai-for-enemies)                                   | L      | Combat Overhaul         |
| [Combat System Refactor](#combat-system-revisit--refactor-for-custom-combat-systems)            | XL     | Combat Overhaul         |
| [Talent Trees / Passive Upgrades](#talent-trees--passive-upgrades)                              | M      | Character Progression   |
| [Extended Template Primitives](#extended-template-primitives)                                   | S      | Engine Architecture     |
| [Adventure Pipeline State-Machine Refactor](#adventure-pipeline-state-machine-refactor)         | XL     | Engine Architecture     |
| [Player-Defined Pronouns](#player-defined-pronouns)                                             | S      | Character Configuration |
| [Cross-Iteration Conditions/Templates/Effects](#cross-iteration-conditionstemplateseffects)     | M      | Character Progression   |
| [Adventure-Scoped Variables](#adventure-scoped-variables)                                       | M      | Adventure Authoring     |
| [Inventory Storage](#inventory-storage)                                                         | L      | Item System             |
| [Shop and Vendor System](#shop-and-vendor-system)                                               | L      | Economy & NPCs          |
| [Persistent NPCs and Dialogue](#persistent-npcs-and-dialogue)                                   | L      | Economy & NPCs          |
| [Quest Branching](#quest-branching)                                                             | M      | Quest Depth & Factions  |
| [Quest Progress Panel](#quest-progress-panel)                                                   | M      | Quest Depth             |
| [Faction and Reputation System](#faction-and-reputation-system)                                 | M      | Quest Depth & Factions  |
| [Content Inheritance / Prototypes](#content-inheritance--prototypes)                            | M      | Content Reuse           |
| [Plugin and Extension System](#plugin-and-extension-system)                                     | L      | Engine Architecture     |
| [HTTP API for Multi-User Support](#http-api-for-multi-user-support)                             | XL     | Multi-User Platform     |
| [Front End Website](#front-end-website)                                                         | XL     | Multi-User Platform     |
| [API-Level Active Adventure Enforcement](#api-level-active-adventure-enforcement)               | S      | Multi-User Platform     |
| [Skill Cooldown State in API](#skill-cooldown-state-in-api)                                     | S      | Multi-User Platform     |
| [Display Metadata in CharacterState Sub-models](#display-metadata-in-characterstate-sub-models) | S      | Multi-User Platform     |
| [CharacterSummaryRead Enrichment](#charactersummaryread-enrichment)                             | XS     | Multi-User Platform     |
| [Remove `character_class` Dead Field](#remove-character_class-dead-field)                       | S      | Multi-User Platform     |
| [Full TUI Upgrade](#full-tui-upgrade)                                                           | L      | Media and Presentation  |
| [Region Maps](#region-maps)                                                                     | M      | Media and Presentation  |
| [Picture Selection and ASCII Art](#picture-selection-and-ascii-art)                             | M      | Media and Presentation  |
| [Content Documentation Generator](#content-documentation-generator)                             | M      | Author Tooling          |

---

## Adventure System

## Combat System

### Decision Tree AI for Enemies

**Effort: L** · **Group: Combat Overhaul**

Add a decision-tree-based AI system that allows content authors to define enemy behavior as a manifest-driven branching structure rather than a flat action list. Enemies could select attacks, switch stances, or flee based on conditions like current HP threshold, player buffs, round number, or status effects.

Example use cases:

- A boss switches to a berserker attack pattern below 25% HP
- An enemy heals if a healing item is available and HP is below 50%
- A cowardly enemy attempts to flee if outmatched

This builds naturally on top of the condition evaluator — each decision node is a condition that the engine already knows how to evaluate. The AI system is purely a structured way to sequence those decisions at combat step resolution time.

### Combat System Revisit / Refactor for Custom Combat Systems

**Effort: XL** · **Group: Combat Overhaul**

The current combat system is tightly coupled to a single resolution model. Refactor it to expose a well-defined interface that allows content packages to specify custom combat systems — for example, a tactical positioning system, a card-draw-based system, or a stamina/cooldown model — without changes to core engine code.

Goals:

- Define a `CombatSystem` protocol or base class that the engine dispatches to
- Ship the existing combat logic as the default `StandardCombatSystem` implementation
- Allow `game.yaml` to declare an alternate combat system by name
- Ensure the TUI and pipeline layers are agnostic to the specific combat system in use

This is a prerequisite for games that want combat to feel meaningfully different from the default turn-based model.

---

## Player Progression

### Talent Trees / Passive Upgrades

**Effort: M** · **Group: Character Progression**

A system for spending an author-defined resource to permanently unlock nodes that each apply a set of effects once on acquisition. The graph structure — tree, diamond, flat list, or web — is implicit in the manifests: each node's prerequisites are expressed as standard conditions, so authors build whatever topology their content needs without any engine-enforced shape.

The spending currency is any stat the author declares in `character_config.yaml`. A game using talent points names the stat `talent_points`; a game using favor calls it `favor`; a game with no distinct talent resource can gate nodes purely on level, milestones, archetypes, or derived stats with no currency cost at all. Because stats are now fully author-defined (with support for derived formulas), the cost and prerequisite model is highly flexible without any new engine primitives.

```yaml
apiVersion: oscilla/v1
kind: TalentNode
metadata:
  name: iron-constitution
spec:
  displayName: "Iron Constitution"
  cost:
    stat: talent_points # any author-declared stat; omit entirely for free nodes
    amount: 1
  requires: # standard condition — prerequisite nodes, stats, milestones, archetypes
    type: talent_unlocked
    name: basic-endurance
  effects: # standard effect list — the same as used everywhere else
    - type: stat_change
      stat: max_hp
      amount: 10
```

Because prerequisites are conditions and rewards are standard effects:

- A node can require multiple unlocked predecessors (AND condition), creating branching paths
- A node can also require a milestone, archetype, stat threshold, or a `milestone_ticks_elapsed` time-based check — not just another node
- Triggered adventures (`on_character_create`, `emit_trigger`) integrate naturally — talent point allocation can happen at character creation or as a triggered post-adventure scene
- Any effect type (stat change, skill grant, archetype add, item grant) is available at zero extra design cost
- Packages that have no talent system simply omit `TalentNode` manifests entirely

The effort for this item has been revised downward from L to M because the stat, condition, effects, and trigger infrastructure it depends on is now fully in place.

### Extended Template Primitives

**Effort: S** · **Group: Engine Architecture**

Adds a second tier of numeric and interpolation utilities to `SAFE_GLOBALS` for authors who need continuous value scaling, percentage math, or list statistics — going beyond the dice-pool and display functions already in the engine (shipped in the stat-formula-templates change).

Functions deferred from the stat-formula-templates change:

- `lerp(a, b, t)` — linear interpolation: `a + (b - a) * t`
- `average(values)` — arithmetic mean of a list (alias for `mean`, more discoverable name)
- `percent(value, total)` — `(value / total) * 100`, safe for zero-total
- `scale(value, in_min, in_max, out_min, out_max)` — map a value from one range to another
- Additional pool manipulation: `drop_highest(pool, n)`, `drop_lowest(pool, n)`, `reroll_below(pool, sides, threshold)`

All functions follow the existing SAFE_GLOBALS conventions: pure Python, sandboxed, `ValueError` on invalid input, precompile-and-mock-render at load time.

### Player-Defined Pronouns

**Effort: S** · **Group: Character Configuration**

The engine currently supports three built-in pronoun sets (`they/them`, `she/her`, `he/him`) and game-defined custom sets declared in `CharacterConfig`. Neither allows a player to enter their own pronoun forms at character creation without the author pre-registering them.

Add a pronoun input mode at character creation where players can type in their own subject, object, possessive, possessive standalone, and reflexive forms. The resulting pronoun set behaves identically to author-defined sets — all placeholder shorthand and `player.pronouns.*` template expressions work unchanged.

This feature is already noted as coming in the author documentation for `game-configuration.md`.

### Cross-Iteration Conditions/Templates/Effects

**Effort: M** · **Group: Character Progression**

A query surface over a character's full `character_iterations` history, enabling conditions, template expressions, and effects that reference data from past prestige runs — not just the current one. This is the natural follow-on to the prestige system, which deliberately scoped itself to current-iteration state.

Examples of what this enables:

- Condition: "player reached milestone X in any past iteration" (milestone-ever-reached)
- Template: `{{ player.past_run_count }}` — how many completed iterations exist
- Effect: grant a cumulative legacy bonus based on the sum of a stat across all past runs
- Content: an NPC who remembers your best stat from a previous life

Key design points:

- Requires a new query surface (`load_all_iterations()` already exists in services) — the gap is exposing that data through `CharacterState`, `PlayerContext`, and the condition evaluator
- Milestone carry-forward ("always have milestone X once earned in any run") is a special case of this — it can be implemented as a condition check at iteration creation time without changing the iteration model
- Milestones now record the `internal_ticks` value at grant time; cross-iteration queries gain a richer "when was this milestone first earned" dimension, including which iteration it was earned in and the tick offset within that run
- Per-run comparison displays in the TUI (e.g., best run, current vs. previous) also fall here
- Cross-iteration effects could be limited in scope at first (read-only history for conditions and templates; write effects like carry-forward happen only at prestige time)
- Since data in past iterations never changes it is an ideal candidate for caching.

---

## Adventure Authoring

### Adventure-Scoped Variables

**Effort: M** · **Group: Adventure Authoring**

Adventures currently have no way to set a value once and refer to it consistently throughout their steps. This forces authors to either repeat the same template expression in multiple places (introducing inconsistency if the roll resolves differently each time) or work around the limitation with complex item-drop mechanics.

Add a `variables:` block to adventure manifests and a `set_variable` step type that evaluates a template expression and stores the result for the rest of that adventure's execution:

```yaml
steps:
  - type: set_variable
    name: reward
    value: "{{ choice(['sword', 'shield', 'amulet']) }}"

  - type: narrative
    text: |
      The chest contains a gleaming {{ reward }}!
    effects:
      - type: item_drop
        loot:
          - item: "{{ reward }}"
            weight: 1
```

Variables live only for the duration of the adventure run. They are accessible in all subsequent step `text` and effect fields via the normal template context.

---

## Item System

### Inventory Storage

**Effort: L** · **Group: Item System**

Players currently have a single flat inventory. Some games need a way to move items into separate storage — a home chest, a guild vault, a ship's hold — that is distinct from the active carrying inventory and may have conditional access.

Key design points:

- A new `Storage` manifest kind declares named containers with an optional access condition and an optional attachment scope (`iteration` for per-character, `global` for shared across characters)
- The TUI gains a storage panel accessible from the inventory screen when the player is at a location that has a linked storage container
- Items in storage are not available for use or equipping until moved to the active inventory
- Storage access uses the standard condition system, so a vault can be gated behind a milestone, a key item, or a minimum level
- **Item carry-over on prestige**: the prestige system (`prestige:` block in `game.yaml`) is now implemented. Once storage containers with `global` scope exist, the carry-over mechanism can be expressed as items moved into a globally scoped container before prestige and retrieved afterward, without any new engine primitives. The `prestige:` block can be extended with a `carry_items` list once this feature ships.

### Shop and Vendor System

**Effort: L** · **Group: Economy & NPCs**

There is currently no mechanism for authors to define item exchanges — trading one resource for another. A vendor system gives content authors a manifest kind for declaring merchants with stock, prices, and availability, without the engine ever knowing what currency or items mean.

The economic model is entirely author-defined: prices are costs expressed as stat deltas (whatever stat the author uses as currency), and item value for resale is any field the author declares on their items. A fantasy game uses `gold`; a sci-fi game uses `credits`; a barter economy uses any combination of item grants and removals.

Key design points:

- Vendors are a manifest kind (`kind: Vendor`) where each stock entry declares an availability condition and a transaction effect list (deduct currency stat, grant item)
- Buying and selling are both just choice steps whose effects are the transaction — no special engine logic for commerce
- Vendor-exclusive items are simply items whose only `item_grant` source is a vendor manifest entry
- Stock availability uses the standard condition system; a vendor can have items that appear only after a milestone, only while the player holds a certain archetype, or only during a specific season

---

## NPC System

### Persistent NPCs and Dialogue

**Effort: L** · **Group: Economy & NPCs**

A manifest kind `NPC` representing a named, persistent character that appears in locations. NPC interactions are regular adventures — the same step types, the same effects, the same condition system. There is no separate adventure kind or special dialogue mode; the author writes a normal adventure and associates it with an NPC.

Speaker context — NPC name, portrait path, and the visual framing of who is talking — is declared as display metadata in the NPC manifest and passed through to the TUI. How the TUI renders that metadata (side panel, header, speech bubble) is a presentation concern; the engine delivers the data without interpreting it.

NPC memory is expressed through milestones, which already exist: the adventures available to an NPC are condition-gated, so a merchant who was cheated simply has a different adventure available once the relevant milestone is set.

Example use cases:

- A merchant whose adventure presents a choice step with buy/sell options (pairs with the Vendor system)
- A stranger whose available adventure changes as the player progresses through milestones
- A lore-keeper whose text step uses templates to reveal what the player has already discovered

---

## Quest System

### Quest Branching

**Effort: M** · **Group: Quest Depth & Factions**

Allow a quest to fork based on a player choice or condition, directing the player into mutually exclusive paths. Each path can have different objectives, rewards, and narrative consequences. The branch condition uses the standard condition evaluator, so any character state — milestone, archetype, stat, faction reputation — can drive the fork. Faction allegiance is one natural use case, not the only one.

```yaml
stages:
  - name: "Choose a Side"
    branches:
      - requires:
          type: milestone
          name: joined-rebels
        advance_milestone: quest-rebel-path
      - requires:
          type: milestone
          name: joined-empire
        advance_milestone: quest-empire-path
```

### Quest Progress Panel

**Effort: M** · **Group: Quest Depth**

The TUI currently has no dedicated surface for displaying quest state. Players can only infer quest progress from narrative text and the effects of milestone grants. A quest progress panel would give players visibility into what quests they have active, what stage each is on, and which quests they have completed.

Scope:

- A new TUI panel (similar to the inventory or skills panels) showing `active_quests` and `completed_quests` from character state
- Each active quest entry shows the quest `displayName` and current stage `description`
- Completed quests shown in a collapsed or greyed section
- The panel is read-only — no actions, just status display

This depends on the Quest Activation Engine being functional first. It is explicitly not part of the engine wiring change — it is a pure TUI/presentation deliverable.

---

## Faction and Reputation System

**Effort: M** · **Group: Quest Depth & Factions**

A named faction system layered on top of the existing stat and milestone infrastructure. Factions are declared in `game.yaml`; reputation with each faction is tracked as a hidden stat with bounds.

This is largely syntactic sugar over what already exists — authors could manually track faction reputation as `int` stats today — but first-class faction support allows:

- The TUI to display a dedicated "Factions" panel
- The condition evaluator to gain a `faction_reputation` predicate with readable syntax
- Faction reward/penalty effects without authors knowing which underlying stat to modify
- Content to reference factions by name rather than by raw stat name, making manifests more readable

When this system ships, `GameFeatureFlags` in the API must also gain a `has_factions: bool` field so that clients can conditionally show the Factions panel. This flag was intentionally omitted from the MU2 `GameFeatureFlags` model until the faction system is implemented.

---

## Content Organization

### Content Inheritance / Prototypes

**Effort: M** · **Group: Content Reuse**

Allow manifests to declare a `base:` reference and inherit all unspecified fields from it. Particularly useful for enemy variants (goblin-scout, goblin-chief, goblin-king all sharing the same loot table and description prefix) and item families (five sword tiers that differ only in damage and value).

```yaml
# base manifest
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin-base
spec:
  description: "A small, aggressive humanoid with yellowed fangs."
  loot_table:
    - item: goblin-ear
      weight: 80

# variant inherits and overrides
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin-chief
spec:
  base: goblin-base       # Inherit description and loot_table
  displayName: "Goblin Chief"
  level: 8
  hp: 80
  damage: 22
```

---

## Engine Architecture

### Plugin and Extension System

**Effort: L** · **Group: Engine Architecture**

Allow third-party Python packages to extend the engine with new conditions, effects, and template filters without patching the core codebase — following the pytest plugin model where installing a package makes its contributions automatically discoverable.

Entry points declared in the contributing package's `pyproject.toml`:

```toml
[project.entry-points."oscilla.conditions"]
my_condition = "mypkg.conditions:MyConditionEvaluator"

[project.entry-points."oscilla.effects"]
my_effect = "mypkg.effects:MyEffectHandler"

[project.entry-points."oscilla.template_filters"]
my_filter = "mypkg.filters:my_filter_fn"
```

The engine discovers these at startup using `importlib.metadata.entry_points()` and registers them alongside built-in implementations. No configuration file changes are needed by the game author — installing the package is sufficient.

This also cleanly separates the engine core from content-specific extensions, and enables community-contributed condition packs (e.g., a date/time condition library, a dice-rolling filter pack) to be distributed independently.

### Adventure Pipeline State-Machine Refactor

**Effort: XL** · **Group: Engine Architecture**

Replace the current coroutine-based adventure pipeline with an explicit step-function / saga model where each step handler returns a typed result — `Decision(event)`, `Continue`, or `Complete(outcome)` — rather than calling into a blocking callback. The pipeline runner becomes a simple loop: call the current step, if it returns `Decision` stop and persist state, if it returns `Continue` advance the step index and loop.

The motivation is MU3's `DecisionPauseException` mechanism, which is a deliberate workaround for a fundamental mismatch between the coroutine model and the stateless HTTP request model. It works, but it uses exceptions as control flow and requires careful management of `asyncio.create_task` lifetimes. A step-function model eliminates both.

Benefits of the refactor:

- No exception-as-control-flow at decision points
- No coroutine lifetime or `create_task` complexity in the web path
- Step handlers become ordinary functions, trivially unit-testable without async machinery
- State is fully serializable by definition — it is just a step index and a typed return value
- Both TUI and web runners share identical step logic; they differ only in how they handle a `Decision` result (block on terminal input vs. emit SSE and return HTTP response)
- Horizontal scaling becomes straightforward — any server can resume any adventure from DB state

This is the same pattern used by workflow engines (AWS Step Functions, Temporal, Prefect) for processes that must survive across process boundaries. It is the architecturally correct model for this use case.

The refactor does not change the content authoring model — manifests, effects, conditions, and step types are unchanged. It is a rewrite of the execution scaffolding only. The TUI must be rebuilt around the new runner interface, but its behavior is functionally identical.

Prerequisite: MU3 must be complete and stable before this refactor begins, as MU3 establishes and validates the full SSE event contract that the new runner must preserve.

---

## Multi-User Platform

### HTTP API for Multi-User Support

**Effort: XL** · **Group: Multi-User Platform**

Extend the existing FastAPI layer into a full multi-user API so that many players can each run their own independent single-player game sessions on a shared server instance. This is explicitly not multiplayer — players do not interact with each other — but they share the same deployed server and game content library.

Goals:

- Authenticated user accounts with persistent character state stored in the database (player persistence already partially exists)
- Session management: a player can close the browser, return later, and resume exactly where they left off
- Per-user game selection: each user can be playing a different game from the content library
- REST endpoints for all game actions currently driven by the TUI (begin adventure, make choice, view inventory, etc.)
- The TUI remains a valid client; the API is an additional interface layer, not a replacement

This is the prerequisite for a web front end and mobile clients.

### API-Level Active Adventure Enforcement

**Effort: S** · **Group: Multi-User Platform**

When a character has an active adventure, the API should reject state-mutating requests made from outside the adventure flow. Currently the frontend enforces this by redirecting to the play screen and blocking navigation away from it, but a determined client (or a bug) can still call endpoints like inventory management, character updates, or location navigation directly while a session lock is held.

Goals:

- Add an `active_adventure_guard` dependency or middleware that checks whether the character has a live session lock before processing requests to endpoints that mutate character state outside the play flow (e.g., `POST /characters/{id}/inventory`, `POST /characters/{id}/navigate`)
- Play-flow endpoints (`/play/begin`, `/play/advance`, `/play/takeover`, `/play/current`) are exempt
- Return `409 Conflict` with a clear error body when the guard fires, consistent with the existing session conflict response
- Document which endpoint groups are covered by the guard in the API reference

This is a defense-in-depth measure alongside the frontend redirect behavior introduced in the MU5 web frontend. It prevents state corruption if a client bypasses the frontend guard or if the frontend has a bug.

---

### Display Metadata in CharacterState Sub-models

**Effort: S** · **Group: Multi-User Platform**

Several sub-models returned inside `CharacterStateRead` expose only a `ref` identifier — `display_name` and `description` fields were not included when these models were initially implemented. The frontend is therefore forced to display raw manifest reference keys to the player instead of human-readable names.

Affected models:

| Model              | Missing fields                |
| ------------------ | ----------------------------- |
| `StackedItemRead`  | `display_name`, `description` |
| `ItemInstanceRead` | `display_name`, `description` |
| `BuffRead`         | `display_name`, `description` |
| `ActiveQuestRead`  | `display_name`, `description` |
| `MilestoneRead`    | `display_name`, `description` |
| `ArchetypeRead`    | `display_name`, `description` |

Goals:

- Add `display_name: str | None` and `description: str | None` to each model above; default both to `None` to keep the change backward-compatible
- Populate them from the content registry in the `CharacterStateRead.from_state()` factory method — resolve the manifest for each `ref` and extract metadata at serialization time
- Update `types.ts` in the web frontend to add the fields to the corresponding TypeScript interfaces
- Once shipped, update all panels in the character sheet that currently fall back to `ref` for display to prefer `display_name` instead
- Add tests confirming the fields are populated when the game registry contains the referenced manifests and are `None` when the ref is not found (defensive — registry should always be consistent, but defensive null is safer than a hard error)

Note: `SkillRead` is handled separately by the [Skill Cooldown State in API](#skill-cooldown-state-in-api) item, which also adds `description` alongside the cooldown fields.

### Remove `character_class` Dead Field

**Effort: S** · **Group: Multi-User Platform**

`character_class` is a scaffolded field that was never wired up. It exists throughout the stack but is always `None` — no effect, condition, content manifest, or endpoint ever sets it. It is not part of the archetypes system, which is the correct mechanism for character classification. Its presence is misleading to developers and content authors.

Locations to remove:

- `oscilla/engine/character.py` — `CharacterState.character_class` field, initialization, serialization, and deserialization
- `oscilla/engine/session.py` — two scalar-field diff blocks that track `character_class` changes
- `oscilla/engine/steps/effects.py` — `player.character_class = None` in the prestige reset
- `oscilla/models/character_iteration.py` — `CharacterIterationRecord.character_class` ORM column
- `oscilla/models/api/characters.py` — `CharacterStateRead.character_class` field
- `oscilla/services/character.py` — two `character_class=state.character_class` assignments
- `tests/engine/test_character_persistence.py` — four fixture dicts that include `"character_class": None`
- DB migration — new Alembic migration dropping the `character_class` column from `character_iterations`
- `docs/dev/database.md` and `docs/dev/api.md` — remove all references

When removed, run `make document_schema` to regenerate the database schema documentation and `make tests` to confirm all checks pass.

### CharacterSummaryRead Enrichment

**Effort: XS** · **Group: Multi-User Platform**

The `CharacterSummaryRead` model returned by `GET /characters` is missing `updated_at: datetime` — the timestamp of the last write to the character record. This is useful for sorting the character list by "most recently played" and for informational display in the character card.

Goals:

- Add `updated_at: datetime` to `CharacterSummaryRead` in `oscilla/models/api/characters.py`
- Ensure `updated_at` is populated from `CharacterRecord.updated_at` (add this column if it does not already exist via a migration)
- Update the `CharacterSummaryRead` TypeScript interface in `types.ts` and the `CharacterCard` component to display the last-played date once available

### Skill Cooldown State in API

**Effort: S** · **Group: Multi-User Platform**

The current `SkillRead` Pydantic model returned by `GET /characters/{id}` exposes only `ref` and `display_name`. It does not expose cooldown state, even though the engine tracks cooldowns as absolute tick and real-time timestamps on `CharacterIterationRecord`.

The web frontend (MU4) cannot display cooldown state for this reason. The Skills panel shows only the skill name — it cannot show whether a skill is on cooldown or how many ticks remain.

Goals:

- Add `description: str | None`, `on_cooldown: bool`, and `cooldown_remaining_ticks: int | None` to `SkillRead`
- `on_cooldown` is `True` when the current game tick is less than the skill's cooldown expiry tick stored in character state
- `cooldown_remaining_ticks` is the difference between the expiry tick and the current game tick when on cooldown, `None` otherwise
- Update `CharacterStateRead` and the character router to populate these fields
- Update the `types.ts` TypeScript interface in the web frontend to match
- Once shipped, update the Skills panel in the web frontend to display cooldown state

This is a prerequisite for the Skills panel showing meaningful cooldown information in the web UI.

### Front End Website

**Effort: XL** · **Group: Multi-User Platform**

A browser-based client for the HTTP API. Players interact with the game through a web interface instead of (or in addition to) the terminal TUI.

Considerations:

- The API design should be driven by front-end needs first; avoid building an API that only the TUI could consume
- Rich text rendering: narrative text supports Jinja2 templates and pronoun placeholders; the front end should render formatted output rather than raw template strings
- Accessibility: keyboard navigation, screen reader support, sufficient color contrast
- The existing static file serving in `oscilla/static/` and template system in `oscilla/templates/` are starting points but likely need significant expansion

## Media and Presentation

### Full TUI Upgrade

**Effort: L** · **Group: Media and Presentation**

A comprehensive pass over the terminal TUI to surface all engine features that have been added since the original TUI was written but are not yet represented with dedicated UI — inventory management, the skill system, quests, faction reputations, NPC interactions, and prestige state among them. The current TUI shows the player's location and adventure choices but leaves most character depth invisible.

Scope of the upgrade:

- **Character sheet panel** — stats (all author-declared, accessed via `player.stats`), derived stats, archetypes, prestige count (`player.prestige_count`), and iteration number in a browsable panel; pulls from fields already tracked in character state
- **In-game time display** — when a `time:` block is configured in `game.yaml`, show the current cycle positions (day, season, era, etc.) and game-tick count alongside the character sheet; uses the `ingame_time` context already computed by the engine
- **Inventory panel** — full item list with equip/unequip actions, item descriptions, and (if Inventory Storage is implemented) a link to open storage containers at supported locations
- **Skills panel** — active and passive skills with descriptions, slot names, and cooldown/charge state where applicable; cooldown expiry is now stored as absolute tick or real-time timestamps, so remaining time can be displayed precisely
- **Quests panel** — active and completed quests with current stage descriptions (depends on Quest Progress Panel being designed; this item covers the TUI surface, not the underlying engine wiring)
- **Factions panel** — reputation values for all declared factions, displayed once Faction and Reputation System is implemented
- **Prestige and iteration display** — after a prestige reset, the character sheet should clearly show current `prestige_count` and historical best stats where useful
- **NPC encounter framing** — when an adventure is associated with an NPC, display speaker context (name, portrait if available) in a dedicated region rather than inline in the narrative text
- **Keyboard navigation improvements** — consistent bindings across all panels, discoverable help overlay (press `?` to see keys)

This item is deliberately scoped as a TUI-only deliverable. It does not add new engine features; it exposes and presents data already computed by the engine. Each panel can be implemented and shipped independently — the item tracks the full set as a cohesive upgrade goal.

Dependencies:

- Quest Progress Panel (engine wiring) should land before the Quests panel surface is built
- Faction and Reputation System should land before the Factions panel surface is built
- All other panels depend only on existing character state fields

### Region Maps

**Effort: M** · **Group: Media and Presentation**

Automatically generated visual maps of a region and the locations within it, rendered in the terminal TUI and optionally as a static image asset for the web front end. Maps give players spatial orientation — they can see which locations are nearby, which they have visited, and how the world is structured — without requiring content authors to hand-draw any art.

Implementation approach:

- Region manifests already declare their child locations; the map generator reads this graph and derives a layout automatically using a force-directed or grid-based placement algorithm — no manual coordinate authoring required
- Visited locations are tracked in character state (milestone or explicit flag); the map renderer distinguishes visited from unvisited locations using character symbols or color
- The current location is highlighted with a distinct marker
- Location connections (edges in the graph) are drawn as lines between nodes; the connection graph is inferred from navigation options declared in location manifests
- Terminal rendering uses [Rich](https://rich.readthedocs.io/) or a lightweight box-drawing approach; no external image library is required for the TUI surface
- For the web front end, the same layout graph can be serialized and rendered as an SVG or canvas element

Design considerations:

- Map display is read-only — it shows state, it does not enable travel; navigation remains choice-driven through the standard step system
- Authors can optionally declare `x`/`y` coordinates on locations to override the automatic layout for regions where spatial precision matters
- Regions with very large numbers of locations (50+) may need a pan/zoom interaction in the TUI; the initial implementation can cap display at a reasonable node count and revisit scrolling later
- If [Picture Selection and ASCII Art](#picture-selection-and-ascii-art) is implemented, location icons or themed symbols can be layered onto map nodes

### Picture Selection and ASCII Art

**Effort: M** · **Group: Media and Presentation**

Allow content manifests to associate images with locations, characters, enemies, items, and adventures. In the terminal TUI, images are rendered as ASCII art; in the web front end, they are displayed as standard images.

Implementation notes:

- The [`ascii-magic`](https://pypi.org/project/ascii-magic/) library converts images (local paths or URLs) to ASCII art suitable for terminal display — zero custom rasterization code required
- Manifests declare an optional `image:` field pointing to a bundled asset path within the content package
- The TUI rendering layer checks terminal width and scales ASCII output accordingly
- The web front end ignores the ASCII conversion and serves the original image
- Content authors are not required to provide images; the field is always optional and the engine renders gracefully without one

---

## Author Tooling

### Content Documentation Generator

**Effort: M** · **Group: Author Tooling**

A CLI command (`oscilla content docs`) that reads a loaded content bundle and emits a self-contained set of interlinked Markdown files documenting every entity in the game — items, enemies, regions, locations, adventures, quests, archetypes, skills, and more. Authors control whether to ship the output alongside their content package, host it as a dedicated site, or keep it as a private reference.

The generator produces one Markdown file per entity plus index pages per kind (e.g. `items/index.md`, `enemies/index.md`). Every generated page cross-links to related entities: an item page links to the adventures where it can be found, an adventure page links to the items it can grant, an enemy page links to its loot table entries, a region page links to its locations and the adventures accessible there.

Key design points:

- Output is pure Markdown with relative links so it renders correctly in any Markdown viewer, static site generator (MkDocs, Docusaurus, Jekyll), or GitHub repository browser without additional tooling
- The command accepts an output directory argument and an optional `--game` flag to select the content package, consistent with other `oscilla content` subcommands
- Author-provided `description` and `displayName` fields from manifests are the primary narrative content; generated pages annotate them with structured data (stats, effects, conditions, loot weights) rendered as Markdown tables
- Cross-reference maps are built by walking all manifests once and resolving references before writing any output — item names appearing in loot tables, effect targets, adventure prerequisites, etc. are linked wherever they appear
- Effect and condition blocks are rendered in a human-readable summary format rather than raw YAML so pages are useful to players as well as authors
- An `index.md` at the output root provides a top-level table of contents with counts and links to each kind index
- The generator is entirely read-only and works against any valid content bundle, including third-party packages the author did not write
- Authors can suppress individual entities from documentation output with a `hidden: true` metadata flag, allowing spoiler content or internal test fixtures to be excluded

Example invocation:

```bash
oscilla content docs --game testlandia --output ./docs/game/
```

This pairs naturally with the `oscilla content graph` command (which already generates region graphs) and would reuse the same content-loading pipeline.
