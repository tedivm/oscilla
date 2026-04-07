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

| Item                                                          | Effort | Group                   |
| ------------------------------------------------------------- | ------ | ----------------------- |
| [Tick-Anchored State Refactor](#tick-anchored-state-refactor) | L      | Engine Architecture     |
| [Character Archetypes](#character-archetypes)                 | M      | Character Progression   |

### All Items

| Item                                                                                        | Effort | Group                   |
| ------------------------------------------------------------------------------------------- | ------ | ----------------------- |
| [Full TUI Upgrade](#full-tui-upgrade)                                                       | L      | —                       |
| [Cross-Iteration Conditions/Templates/Effects](#cross-iteration-conditionstemplateseffects) | M      | Character Progression   |
| [Tick-Anchored State Refactor](#tick-anchored-state-refactor)                               | L      | Engine Architecture     |
| [Adventure-Scoped Variables](#adventure-scoped-variables)                                   | M      | Adventure Authoring     |
| [Combat System Refactor](#combat-system-revisit--refactor-for-custom-combat-systems)        | XL     | Combat Overhaul         |
| [Buff Blocking and Priority](#buff-blocking-and-priority)                                   | S      | Combat Refinement       |
| [Buff Persistence Between Adventures](#buff-persistence-between-adventures)                 | S      | Combat Refinement       |
| [Character Archetypes](#character-archetypes)                                               | M      | Character Progression   |
| [Talent Trees / Passive Upgrades](#talent-trees--passive-upgrades)                          | L      | Character Progression   |
| [Stat Formula Templates](#stat-formula-templates)                                           | M      | Character Progression   |
| [Player-Defined Pronouns](#player-defined-pronouns)                                         | S      | Character Configuration |
| [Shop and Vendor System](#shop-and-vendor-system)                                           | L      | Economy & NPCs          |
| [Persistent NPCs and Dialogue](#persistent-npcs-and-dialogue)                               | L      | Economy & NPCs          |
| [Enhanced Loot Tables](#enhanced-loot-tables)                                               | S      | Item System             |
| [Inventory Storage](#inventory-storage)                                                     | L      | Item System             |
| [Quest Branching](#quest-branching)                                                         | M      | Quest Depth & Factions  |
| [Quest Progress Panel](#quest-progress-panel)                                               | M      | Quest Depth             |
| [Faction and Reputation System](#faction-and-reputation-system)                             | M      | Quest Depth & Factions  |
| [Content Inheritance / Prototypes](#content-inheritance--prototypes)                        | M      | Content Reuse           |
| [Plugin and Extension System](#plugin-and-extension-system)                                 | L      | Engine Architecture     |
| [HTTP API for Multi-User Support](#http-api-for-multi-user-support)                         | XL     | Multi-User Platform     |
| [Front End Website](#front-end-website)                                                     | XL     | Multi-User Platform     |
| [Picture Selection and ASCII Art](#picture-selection-and-ascii-art)                         | M      | —                       |
| [Region Maps](#region-maps)                                                                 | M      | —                       |

---

## Condition System

### Tick-Anchored State Refactor

**Effort: L** · **Group: Engine Architecture**

The internal game clock (`internal_ticks`) is a monotone, tamper-proof counter that already advances on every adventure. It is currently used for adventure cooldowns (`cooldown_ticks`) and era boundary calculations, but most state timestamps — milestones, quest completions, adventure completion history — are stored as opaque sets or string dates decoupled from the tick system. This change refactors those stores to record the `internal_ticks` value at the moment each event occurred.

Key changes this enables:

- **Milestone timestamps**: `milestones` changes from `Set[str]` to `Dict[str, int]` (milestone ref → tick when granted). Querying `has_milestone()` stays unchanged; conditions gain `milestone_at_ticks` and `milestone_before_ticks` predicates so authors can write time-relative checks (e.g., "granted the gate-key milestone within the last 10 ticks").
- **Cooldown unification**: Skill cooldowns currently count down in adventure-units. With tick timestamps, all cooldowns — adventure repeats, skill reuse, and buff durations — can be expressed as `cooldown_ticks` offsets from the granting tick. This removes the `tick_skill_cooldowns()` adventure-start ceremony and the separate `cooldown_days` date-string path.
- **Effect and trigger timestamps**: `emit_trigger` events and quest stage transitions gain a `granted_at_ticks` field, enabling elapsed-time conditions across the whole authoring surface.
- **`adventure_last_completed_at_ticks` unification**: The current parallel tracking (`adventure_last_completed_on` for calendar dates, `adventure_last_completed_at_ticks` for ticks) collapses into the single tick-based record; calendar-day comparisons are derived from the tick-to-game-date conversion where a `time:` block is declared.

Design considerations:

- Backward-compatible migration: existing saves have `milestones` as a set — `from_dict()` must detect the old format and migrate it by assigning `tick = 0` (or `None`) to pre-migration milestones
- The `has_milestone()` API must not change — only new tick-aware predicates are added; old content remains valid
- Without a `time:` block in `game.yaml`, the calendar-day cooldown path is already gated — tick-only is the baseline; date conversion is additive
- Skill cooldown duration would need to be expressed in ticks rather than adventure counts in manifests; a deprecation path for `cooldown_adventures` is required

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

### Buff Blocking and Priority

**Effort: S** · **Group: Combat Refinement**

Currently, the same buff can be applied multiple times simultaneously regardless of whether a weaker version is already active. For example, if a `thorns-60pct` buff is applied and then `thorns-30pct` is also applied, both fire independently — leading to unintended stacking and counter-intuitive results.

Add a priority or exclusion mechanism to buff manifests. Buffs in the same exclusion group should block lower-priority applications:

```yaml
spec:
  name: thorns
  exclusion_group: thorns # only the highest-priority instance in this group applies
  priority: 60 # numeric priority; higher wins
```

When a buff is applied, the engine checks for existing active effects in the same `exclusion_group` and skips the new application if a higher-priority instance is already running.

### Buff Persistence Between Adventures

**Effort: S** · **Group: Combat Refinement**

Buffs are currently ephemeral — they apply at the start of a combat encounter and are discarded when the encounter ends. This prevents authors from creating persistent status effects that carry between fights (e.g. a curse from losing a boss encounter, a blessing that lasts for three adventures, or a "well-rested" bonus that expires after the next combat).

Add an optional `duration` scope to buff manifests:

- `scope: encounter` (default) — current behavior, cleared after combat
- `scope: adventure` — persists until the adventure ends
- `scope: persistent` — stored on the player and persists until explicitly dispelled or a duration expires

Persistent buffs require a small addition to the player state serialization.

---

## Player Progression

### Character Archetypes

**Effort: M** · **Group: Character Progression**

Rather than a single hard-wired class system, the engine provides a generic **archetypes** collection on each character — a set of string keys whose legal values and meaning are fully defined by the author in `game.yaml`. Characters can hold any number of archetypes simultaneously, enabling multi-classing, dual guilds, overlapping faction memberships, or any other multi-category scheme a content package needs.

Authors define their archetype vocabulary in `game.yaml`:

```yaml
archetypes:
  warrior:
    label: "Warrior"
    stat_growth: # per-level stat bonuses stack across all held archetypes
      hp: 3
      strength: 1
    skill_categories: # union of all held archetypes' lists determines what can be learned
      - melee
      - defense
  mage:
    label: "Mage"
    stat_growth:
      hp: 1
      intelligence: 2
    skill_categories:
      - arcane
      - support
  guild_member: # a social archetype with no mechanical stat growth
    label: "Guild Member"
  wanderer: # open archetype — no restrictions added or removed
    label: "Wanderer"
```

A character who holds both `warrior` and `mage` gets the combined `stat_growth` bonuses each level and can learn from both `melee`/`defense` and `arcane`/`support` categories.

Archetypes are first-class across all three authoring systems:

- **Selection**: archetypes are granted or revoked via `archetype_add` and `archetype_remove` effects, available at character creation, in adventure steps, or via triggered adventures (enabling in-world multi-classing quests)
- **Condition system**: predicates operate on the set — `has_archetype: warrior` (holds at least one), `has_all_archetypes: [warrior, mage]` (holds all), `has_any_archetype: [warrior, paladin]` (holds at least one of the list), `archetype_count_gte: 2` (holds N or more)
- **Template system**: the character's full archetype set and each archetype's definition from `game.yaml` are exposed, so templates can list classes, display combined bonuses, or branch on membership
- **Skill gating**: the union of `skill_categories` across all held archetypes determines what the character may learn; a character with no archetypes falls back to package-level defaults

Content packages that don't want a class system simply omit the `archetypes` key and the feature is invisible.

### Talent Trees / Passive Upgrades

**Effort: L** · **Group: Character Progression**

A system for spending an author-defined resource to permanently unlock nodes that each apply a set of effects once on acquisition. The graph structure — tree, diamond, flat list, or web — is implicit in the manifests: each node's prerequisites are expressed as standard conditions, so authors build whatever topology their content needs without any engine-enforced shape.

The spending currency is any stat the author declares in `character_config.yaml`. A game using talent points names the stat `talent_points`; a game using favor calls it `favor`; a game with no distinct talent resource can gate nodes purely on level, milestones, or archetypes with no currency cost at all.

```yaml
apiVersion: oscilla/v1
kind: TalentNode
metadata:
  name: iron-constitution
spec:
  displayName: "Iron Constitution"
  cost:
    stat: talent_points # any author-defined stat; omit entirely for free nodes
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
- A node can also require a milestone, archetype, or stat threshold — not just another node
- Any effect type (stat change, skill grant, archetype add, item grant) is available at zero extra design cost
- Packages that have no talent system simply omit `TalentNode` manifests entirely

### Stat Formula Templates

**Effort: M** · **Group: Character Progression**

Level-up stat gains, HP maximums, and other derived values are currently hard-coded in the engine or declared as fixed integers in `character_config.yaml`. This prevents authors from expressing formulas like "max HP = base_hp + (constitution × 3)" or "XP to next level = 100 × level²".

Allow `character_config.yaml` stat definitions and level-up tables to declare template strings instead of fixed numbers:

```yaml
stats:
  - name: max_hp
    type: int
    formula: "{{ base_hp + player.stats.constitution * 3 }}" # recalculated on level-up

level_xp_formula: "{{ 100 * player.level ** 2 }}"
```

Formulas are evaluated using the standard template engine with the player's current stats as context. This is consistent with how `xp_grant.amount` and `stat_change.amount` already support template strings.

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

### Enhanced Loot Tables

**Effort: S** · **Group: Item System**

The current `item_drop` loot table is a flat weighted list — each entry has an `item` and a `weight`, and the engine picks one. Authors have no way to express richer drop semantics such as:

- **Guaranteed drops**: always drop item A, then roll for one of B/C/D
- **Multiple rolls**: roll the table N times independently, potentially giving duplicates
- **Conditional entries**: include an item only if a condition is met (player has a specific skill, milestone, etc.)
- **Tiered tables**: a rare tier with its own weight that activates separately from a common tier

The loot table schema should be extended to support these patterns without requiring authors to write workarounds using item charges or multi-step adventures.

### Inventory Storage

**Effort: L** · **Group: Item System**

Players currently have a single flat inventory. Some games need a way to move items into separate storage — a home chest, a guild vault, a ship's hold — that is distinct from the active carrying inventory and may have conditional access.

Key design points:

- A new `Storage` manifest kind declares named containers with an optional access condition and an optional attachment scope (`iteration` for per-character, `global` for shared across characters)
- The TUI gains a storage panel accessible from the inventory screen when the player is at a location that has a linked storage container
- Items in storage are not available for use or equipping until moved to the active inventory
- Storage access uses the standard condition system, so a vault can be gated behind a milestone, a key item, or a minimum level
- **Item carry-over on prestige**: the prestige system deliberately deferred item and equipment carry-forward across iterations. Once storage containers with `global` scope exist, the carry-over mechanism can be expressed as items moved into a globally scoped container before prestige and retrieved afterward, without any new engine primitives. The `prestige:` block in `game.yaml` can be extended with a `carry_items` list once this feature ships.

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

### Front End Website

**Effort: XL** · **Group: Multi-User Platform**

A browser-based client for the HTTP API. Players interact with the game through a web interface instead of (or in addition to) the terminal TUI.

Considerations:

- The API design should be driven by front-end needs first; avoid building an API that only the TUI could consume
- Rich text rendering: narrative text supports Jinja2 templates and pronoun placeholders; the front end should render formatted output rather than raw template strings
- Accessibility: keyboard navigation, screen reader support, sufficient color contrast
- The existing static file serving in `oscilla/static/` and template system in `oscilla/templates/` are starting points but likely need significant expansion

---

## Media and Presentation

### Full TUI Upgrade

**Effort: L** · **Group: —**

A comprehensive pass over the terminal TUI to surface all engine features that have been added since the original TUI was written but are not yet represented with dedicated UI — inventory management, the skill system, quests, faction reputations, NPC interactions, and prestige state among them. The current TUI shows the player's location and adventure choices but leaves most character depth invisible.

Scope of the upgrade:

- **Character sheet panel** — stats, archetypes, prestige count, and iteration number in a browsable panel; pulls from fields already tracked in character state
- **Inventory panel** — full item list with equip/unequip actions, item descriptions, and (if Inventory Storage is implemented) a link to open storage containers at supported locations
- **Skills panel** — active and passive skills with descriptions, slot names, and cooldown/charge state where applicable
- **Quests panel** — active and completed quests with current stage descriptions (depends on Quest Progress Panel being designed; this item covers the TUI surface, not the underlying engine wiring)
- **Factions panel** — reputation values for all declared factions, displayed once Faction and Reputation System is implemented
- **Prestige and iteration display** — after a prestige reset, the character sheet should clearly show current iteration and historical best stats where useful
- **NPC encounter framing** — when an adventure is associated with an NPC, display speaker context (name, portrait if available) in a dedicated region rather than inline in the narrative text
- **Keyboard navigation improvements** — consistent bindings across all panels, discoverable help overlay (press `?` to see keys)

This item is deliberately scoped as a TUI-only deliverable. It does not add new engine features; it exposes and presents data already computed by the engine. Each panel can be implemented and shipped independently — the item tracks the full set as a cohesive upgrade goal.

Dependencies:

- Quest Progress Panel (engine wiring) should land before the Quests panel surface is built
- Faction and Reputation System should land before the Factions panel surface is built
- All other panels depend only on existing character state fields

### Region Maps

**Effort: M** · **Group: —**

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

**Effort: M** · **Group: —**

Allow content manifests to associate images with locations, characters, enemies, items, and adventures. In the terminal TUI, images are rendered as ASCII art; in the web front end, they are displayed as standard images.

Implementation notes:

- The [`ascii-magic`](https://pypi.org/project/ascii-magic/) library converts images (local paths or URLs) to ASCII art suitable for terminal display — zero custom rasterization code required
- Manifests declare an optional `image:` field pointing to a bundled asset path within the content package
- The TUI rendering layer checks terminal width and scales ASCII output accordingly
- The web front end ignores the ASCII conversion and serves the original image
- Content authors are not required to provide images; the field is always optional and the engine renders gracefully without one
