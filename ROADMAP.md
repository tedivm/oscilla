# Roadmap

Ideas and future directions that are explicitly out of scope for current work but should not be forgotten.

---

## Effort Scale

| Label | Meaning |
|-------|---------|
| **XS** | A day or less — trivial addition, no new design required |
| **S** | 2–5 days — small, well-scoped feature |
| **M** | 1–2 weeks — moderate feature, some design work required |
| **L** | 3–6 weeks — significant feature spanning multiple engine components |
| **XL** | 2+ months — major system requiring full architectural design |

## Summary

Items sharing a **Group** label can be scoped and worked on together as a single change.

### High Priority

These items fix existing bugs or remove technical debt that actively misleads authors or degrades engine correctness. They should be addressed before other roadmap work.

| Item | Effort | Group |
|------|--------|-------|
| [Quest Activation Engine](#quest-activation-engine) | S | Quest Depth |
| [Remove Condition Shorthand Syntax](#remove-condition-shorthand-syntax) | S | Technical Debt |
| [Enemy Loot Table Reference in on_win](#enemy-loot-table-reference-in-on_win) | S | Item System |
| [Remove `base_adventure_count` Field](#remove-base_adventure_count-field) | XS | Technical Debt |

### All Items

| Item | Effort | Group |
|------|--------|-------|
| [Date and Time Conditions](#date-and-time-conditions) | S | Calendar Conditions |
| [Calendar Functions in Conditions](#calendar-and-astronomical-functions-in-conditions) | XS | Calendar Conditions |
| [In-Game Time System](#in-game-time-system) | M | Calendar Conditions |
| [Season Hemisphere Configuration](#season-hemisphere-configuration) | XS | Calendar Conditions |
| [Triggered Adventures](#triggered-adventures) | M | — |
| [Adventure-Scoped Variables](#adventure-scoped-variables) | M | Adventure Authoring |
| [Adventure Outcome Definitions](#adventure-outcome-definitions) | S | Adventure Authoring |
| [Passive Event Step](#passive-event-step) | S | Adventure Authoring |
| [Adventure Repeat Controls](#adventure-repeat-controls) | S | Adventure Authoring |
| [Decision Tree AI for Enemies](#decision-tree-ai-for-enemies) | L | Combat Overhaul |
| [Combat System Refactor](#combat-system-revisit--refactor-for-custom-combat-systems) | XL | Combat Overhaul |
| [Buff Blocking and Priority](#buff-blocking-and-priority) | S | Combat Refinement |
| [Buff Persistence Between Adventures](#buff-persistence-between-adventures) | S | Combat Refinement |
| [Character Archetypes](#character-archetypes) | M | Character Progression |
| [Talent Trees / Passive Upgrades](#talent-trees--passive-upgrades) | L | Character Progression |
| [Stat Formula Templates](#stat-formula-templates) | M | Character Progression |
| [Player-Defined Pronouns](#player-defined-pronouns) | S | Character Configuration |
| [Skill Slot Naming Revisit](#skill-slot-naming-revisit) | XS | Character Configuration |
| [Shop and Vendor System](#shop-and-vendor-system) | L | Economy & NPCs |
| [Persistent NPCs and Dialogue](#persistent-npcs-and-dialogue) | L | Economy & NPCs |
| [Enhanced Loot Tables](#enhanced-loot-tables) | S | Item System |
| [Enemy Loot Table Reference in on_win](#enemy-loot-table-reference-in-on_win) | S | Item System |
| [Inventory Storage](#inventory-storage) | L | Item System |
| [Quest Activation Engine](#quest-activation-engine) | S | Quest Depth |
| [Remove Condition Shorthand Syntax](#remove-condition-shorthand-syntax) | S | Technical Debt |
| [Quest Stage Condition](#quest-stage-condition) | S | Quest Depth |
| [Quest Failure States](#quest-failure-states) | S | Quest Depth |
| [Quest Branching](#quest-branching) | M | Quest Depth & Factions |
| [Faction and Reputation System](#faction-and-reputation-system) | M | Quest Depth & Factions |
| [Named Random Tables](#named-random-tables) | S | Content Reuse |
| [Content Inheritance / Prototypes](#content-inheritance--prototypes) | M | Content Reuse |
| [Multi-Manifest YAML Files](#multi-manifest-yaml-files) | S | Authoring Tooling |
| [JSON Schema for IDE Support](#json-schema-for-ide-support) | M | Authoring Tooling |
| [Content Validation CLI Improvements](#content-validation-cli-improvements) | M | Authoring Tooling |
| [Plugin and Extension System](#plugin-and-extension-system) | L | Engine Architecture |
| [Remove `base_adventure_count` Field](#remove-base_adventure_count-field) | XS | Technical Debt |
| [HTTP API for Multi-User Support](#http-api-for-multi-user-support) | XL | Multi-User Platform |
| [Front End Website](#front-end-website) | XL | Multi-User Platform |
| [Picture Selection and ASCII Art](#picture-selection-and-ascii-art) | M | — |

---

## Condition System

### Remove Condition Shorthand Syntax

**Effort: S** · **Group: —**

The engine's condition parser supports two syntaxes for the same condition. The explicit (type-tagged) form is what `conditions.md` documents and what every doc except `world-building.md` uses:

```yaml
requires:
  type: level
  value: 5
```

A shorthand (bare-key) form also exists, handled by `normalise_condition()` in `oscilla/engine/models/base.py`:

```yaml
unlock:
  level: 5
```

Both parse to identical Pydantic models. However, having two valid syntaxes creates inconsistency across the docs, surprise for authors switching between files, and ongoing maintenance burden on the normalizer. The shorthand was added as a convenience but predates a stable authoring convention.

What needs to happen:

- Remove `normalise_condition()` and the `_LEAF_MAPPINGS` / `_DICT_LEAVES` normalisation logic
- Update the loader to require the explicit `type:`-tagged form everywhere
- Migrate all content in `content/` that uses the shorthand to the explicit form
- Update `world-building.md` unlock examples and `adventures.md` shorthand examples to use the explicit form throughout
- Add a load-time error (or migration warning) if bare-key conditions are encountered, to guide authors with existing content

Until this is done, authors reading different doc pages will encounter two different-looking syntaxes with no explanation that they are equivalent.

### Date and Time Conditions

**Effort: S** · **Group: Calendar Conditions**

Add date and time predicates to the condition evaluator so content authors can create holiday events, time-of-day atmosphere, and seasonal content without requiring any template logic.

Example use cases:

- Show a special greeting every December 25th
- Play a spooky encounter only in October
- Display a morning/evening variant of a location description

This pairs naturally with the `now()` and `today()` template functions added in `dynamic-content-templates`, but belongs in the condition system so that entire adventure branches — not just narrative text — can be gated on the calendar.

Candidate condition types: `date_is`, `month_is`, `day_of_week_is`, `time_between`.

### Calendar and Astronomical Functions in Conditions

**Effort: XS** · **Group: Calendar Conditions**

The `dynamic-content-templates` change introduces `oscilla/engine/calendar_utils.py` — a dependency-free module with `season`, `month_name`, `day_name`, `week_number`, `mean`, `zodiac_sign`, `chinese_zodiac`, and `moon_phase`. This module was deliberately separated from the template engine so the condition evaluator can import the same functions without duplication.

When calendar conditions are added to the condition evaluator, the implementation details (zodiac boundary tables, lunar cycle math, etc.) are already solved and available in `calendar_utils`. The condition system only needs to expose them as evaluable predicates (e.g., `season_is: summer`, `moon_phase_is: Full Moon`, `zodiac_is: Aries`).

### In-Game Time System

**Effort: M** · **Group: Calendar Conditions**

The existing calendar functions (`season()`, `moon_phase()`, etc.) operate on real-world time via `today()` and `now()`. Some games have no real-world tie-in — a dungeon crawler, a space opera, a mythological world — and want time to flow according to in-game rules rather than the Gregorian calendar.

Add an opt-in in-game time system declared in `game.yaml`:

```yaml
spec:
  time:
    ticks_per_day: 10        # one "day" passes every 10 adventure completions
    days_per_season: 30
    seasons:
      - name: "The Bright Season"
      - name: "The Frost Season"
      - name: "The Thaw"
```

The in-game time counter increments automatically on adventure completion (or on other configurable events). Templates and conditions expose an `ingame_time` object with the current day, season name, and tick count alongside the existing real-world `today()` and `now()`. Authors who omit `time:` entirely continue using real-world calendar functions with no change.

### Season Hemisphere Configuration

**Effort: XS** · **Group: Calendar Conditions**

The `season()` function in `calendar_utils.py` uses Northern Hemisphere meteorological season boundaries. Authors writing games set in a Southern Hemisphere context (or a fictional world with a different seasonal calendar) have no way to change this.

Add an optional `season_hemisphere` field in `game.yaml` — and a per-character override — that controls which hemisphere's boundaries `season()` uses. Valid values: `northern` (default), `southern`. This pairs naturally with the In-Game Time System, which would render the real-world hemisphere setting irrelevant for games using fictitious calendars.

---

## Adventure System

### Triggered Adventures

**Effort: M** · **Group: —**

Adventures that fire automatically in response to engine lifecycle events rather than being selected by the player from a location menu. The trigger type is declared in the adventure manifest; the engine detects the event and queues the adventure before normal flow resumes.

Candidate trigger events:

- `on_character_create` — runs immediately after a new character is created; ideal for starting gear selection, backstory questions, or tutorial sequences
- `on_death` — runs when a character's HP reaches zero; allows a narrative death scene, a resurrection mechanic, or a permadeath epilogue
- `on_game_rejoin` — runs when a player resumes a session after a configurable absence; useful for recap narratives or "time has passed" world events
- `on_level_up` — runs immediately after a level-up is applied; allows a narrative acknowledgment or a class-advancement choice sequence
- `on_stat_threshold` — fires when a tracked stat crosses a defined boundary (e.g., fame reaches 100, an experience stat reaches its cap); this is the generic hook for content-level events like prestige that have no corresponding engine lifecycle fact

Authors can also declare custom trigger names in `game.yaml`; the engine fires them when an `emit_trigger` effect is applied anywhere in content. This allows content-defined lifecycle events without any engine knowledge of what those events mean.

Design considerations:

- A triggered adventure is structurally identical to a normal adventure; only the activation mechanism differs
- Multiple adventures may be registered for the same trigger; the engine runs them in declaration order
- Triggers declared in `character_config.yaml` or `game.yaml` apply globally; triggers in a region or location manifest apply only while that region/location is active
- The normal condition system applies — a triggered adventure can still have `conditions:` that gate whether it actually runs

---

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
  exclusion_group: thorns   # only the highest-priority instance in this group applies
  priority: 60              # numeric priority; higher wins
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
    stat_growth:          # per-level stat bonuses stack across all held archetypes
      hp: 3
      strength: 1
    skill_categories:     # union of all held archetypes' lists determines what can be learned
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
  guild_member:           # a social archetype with no mechanical stat growth
    label: "Guild Member"
  wanderer:               # open archetype — no restrictions added or removed
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
apiVersion: game/v1
kind: TalentNode
metadata:
  name: iron-constitution
spec:
  displayName: "Iron Constitution"
  cost:
    stat: talent_points   # any author-defined stat; omit entirely for free nodes
    amount: 1
  requires:               # standard condition — prerequisite nodes, stats, milestones, archetypes
    type: talent_unlocked
    name: basic-endurance
  effects:                # standard effect list — the same as used everywhere else
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
    formula: "{{ base_hp + player.stats.constitution * 3 }}"   # recalculated on level-up

level_xp_formula: "{{ 100 * player.level ** 2 }}"
```

Formulas are evaluated using the standard template engine with the player's current stats as context. This is consistent with how `xp_grant.amount` and `stat_change.amount` already support template strings.

### Player-Defined Pronouns

**Effort: S** · **Group: Character Configuration**

The engine currently supports three built-in pronoun sets (`they/them`, `she/her`, `he/him`) and game-defined custom sets declared in `CharacterConfig`. Neither allows a player to enter their own pronoun forms at character creation without the author pre-registering them.

Add a pronoun input mode at character creation where players can type in their own subject, object, possessive, possessive standalone, and reflexive forms. The resulting pronoun set behaves identically to author-defined sets — all placeholder shorthand and `player.pronouns.*` template expressions work unchanged.

This feature is already noted as coming in the author documentation for `game-configuration.md`.

### Skill Slot Naming Revisit

**Effort: XS** · **Group: Character Configuration**

The `passive_1`, `passive_2` etc. slot names used in `skill_grants` within passive effects and NPC manifests are confusing. They imply a fixed UI grid that may not match how a given game surfaces skills, and the term "passive" conflicts with the existing "passive effects" concept.

Revisit the slot naming scheme so that it is either author-defined in `game.yaml` (allowing names like `utility`, `combat`, `exploration`) or removed entirely if the TUI does not actually display slots in a position-dependent way.

---

## Adventure Authoring

### Passive Event Step

**Effort: S** · **Group: Adventure Authoring**

A step type that applies effects automatically — no player input, no choice — with an optional condition that lets the character bypass it entirely. Currently, any automatic effect within an adventure requires workarounds (a fake single-option combat, or bare stat_change effects with no narrative framing). A dedicated passive step makes the intent explicit and the manifest readable.

The step is not inherently negative. Authors use it for traps, environmental hazards, blessing shrines, automatic rewards, time-passing events, or any other scripted outcome with optional narrative text.

```yaml
- type: passive
  text: "The pressure plate triggers a dart trap!"
  effects:
    - type: stat_change
      stat: hp
      amount: -15
  bypass:           # optional: skip this step entirely if the condition is true
    type: character_stat
    name: dexterity
    gte: 14

- type: passive
  text: "You step into the healing spring and feel restored."
  effects:
    - type: stat_change
      stat: hp
      amount: 20
```

The `bypass` condition uses the existing condition evaluator; no new predicate types are required.

### Adventure Repeat Controls

**Effort: S** · **Group: Adventure Authoring**

Currently unclear from the content model whether adventures are inherently repeatable. Explicit repeat controls would allow authors to express:

- `repeatable: false` — one-shot adventure; once completed, it is removed from the pool
- `cooldown_days: 1` — adventure cannot be selected again until the next in-game day
- `max_completions: 3` — adventure can be done multiple times but has a hard cap

These are declared per-adventure in the manifest and enforced by the pool selection logic.

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

### Adventure Outcome Definitions

**Effort: S** · **Group: Adventure Authoring**

Adventure outcomes (`completed`, `defeated`, `fled`) are currently hard-coded strings in the engine. Authors cannot define their own outcome types, and the default outcome (`completed`) must be explicitly set even when there is no branching.

Two improvements:

1. Allow `game.yaml` to declare the valid outcome set and which is the default, so that a game with custom outcomes (e.g. `banished`, `escaped`, `surrendered`) can be expressed cleanly.
2. Track per-adventure outcome counts as player statistics alongside `adventures_completed`, enabling conditions and templates that branch on how an adventure previously resolved.

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

### Enemy Loot Table Reference in on_win

**Effort: S** · **Group: Item System**

Enemy manifests declare an inline loot table, but there is currently no way to reference that table from an `on_win` outcome branch in a combat step. The `on_win` effects list accepts `item_drop` entries directly — but those require their own inline loot list, completely duplicating the enemy's declared table. As a result, the loot table on an enemy manifest is effectively useless unless the author duplicates it.

The fix is to allow `item_drop` effects to reference an enemy's loot table by name (e.g. `loot_ref: goblin`) so the `on_win` branch can delegate to the enemy's own declared drops without duplication.

### Inventory Storage

**Effort: L** · **Group: Item System**

Players currently have a single flat inventory. Some games need a way to move items into separate storage — a home chest, a guild vault, a ship's hold — that is distinct from the active carrying inventory and may have conditional access.

Key design points:

- A new `Storage` manifest kind declares named containers with an optional access condition and an optional attachment scope (`iteration` for per-character, `global` for shared across characters)
- The TUI gains a storage panel accessible from the inventory screen when the player is at a location that has a linked storage container
- Items in storage are not available for use or equipping until moved to the active inventory
- Storage access uses the standard condition system, so a vault can be gated behind a milestone, a key item, or a minimum level

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

### Quest Activation Engine

**Effort: S** · **Group: Quest Depth**

The `Quest` manifest, player state fields (`active_quests`, `completed_quests`), and database persistence are all in place, but the engine never connects milestone grants to quest state changes. `grant_milestone()` in `character.py` only adds the milestone name to `player.milestones` — it does not inspect loaded quests to activate them or advance their stages.

What is needed:

- When a milestone is granted, scan all loaded quests in the registry.
- If a quest is not yet active and the granted milestone appears in `entry_stage.advance_on`, set `active_quests[quest_ref] = entry_stage`.
- If a quest is already active and the granted milestone appears in the current stage's `advance_on`, advance to `next_stage` (or move it to `completed_quests` if the new stage is terminal).

This logic belongs in `grant_milestone()` (or a wrapper called from it) and requires a `ContentRegistry` reference to look up quest manifests. The session's `sync()` method already persists whatever is in `active_quests` and `completed_quests`, so persistence requires no changes.

Until this is implemented, Quest manifests are parsed and validated but never activated at runtime — the `Starting a Quest` section of the author docs is aspirational.

### Quest Stage Condition

**Effort: S** · **Group: Quest Depth**

There is no condition type for checking the current stage of an active quest. Authors currently use milestone conditions as a proxy (gating on the milestone that triggered a stage transition), but this breaks down when multiple milestones can trigger the same stage, or when the quest hasn't activated yet and there is no milestone to check.

Add a `quest_stage` condition type:

```yaml
requires:
  type: quest_stage
  quest: missing-merchant
  stage: active-search   # true when quest is active AND in this named stage
```

This gives authors direct, explicit control over adventure gating without relying on implicit milestone-as-stage-proxy assumptions. It also creates a natural integration point with the Quest Activation Engine — once quests can actually advance stages, conditions can meaningfully reflect them.

### Quest Failure States

**Effort: S** · **Group: Quest Depth**

Quests currently only have stages that advance forward. Adding explicit failure conditions would allow time-limited quests and quests that can be permanently failed (not just abandoned).

```yaml
stages:
  - name: "Rescue the Hostage"
    advance_milestone: hostage-rescued
    fail_condition:
      type: milestone
      name: hostage-killed    # Set by an enemy loot effect on the hostage enemy
```

Failure triggers a `on_fail` outcome with its own effects (narrative, stat changes, milestone), mirrors how combat has `on_defeat`.

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

### Multi-Manifest YAML Files

**Effort: S** · **Group: Authoring Tooling**

Allow multiple manifests to be defined in a single YAML file, separated by `---` document dividers. This is the standard Kubernetes-style multi-document YAML pattern and significantly reduces file clutter for small or closely related manifests.

```yaml
apiVersion: game/v1
kind: Item
metadata:
  name: rusty-sword
spec:
  displayName: "Rusty Sword"
  base_damage: 5
---
apiVersion: game/v1
kind: Item
metadata:
  name: iron-sword
spec:
  displayName: "Iron Sword"
  base_damage: 10
```

The directory scanner and manifest loader need to use a multi-document YAML parser (the `ruamel.yaml` library already supports this via `load_all`). File naming and directory layout remain unchanged — authors can continue using one-manifest-per-file if they prefer.

### Named Random Tables

**Effort: S** · **Group: Content Reuse**

A reusable, named loot/random table that can be referenced by multiple adventures, enemies, and items. Today, every loot table is inline — if the same forest loot should drop from three different enemies, the author must duplicate the table in all three places.

```yaml
apiVersion: game/v1
kind: RandomTable
metadata:
  name: forest-loot
spec:
  entries:
    - item: herbs
      weight: 60
    - item: small-gem
      weight: 30
    - item: ancient-coin
      weight: 10
```

Referenced in item_drop effects as `table_ref: forest-loot` instead of an inline `loot:` list.

### Content Inheritance / Prototypes

**Effort: M** · **Group: Content Reuse**

Allow manifests to declare a `base:` reference and inherit all unspecified fields from it. Particularly useful for enemy variants (goblin-scout, goblin-chief, goblin-king all sharing the same loot table and description prefix) and item families (five sword tiers that differ only in damage and value).

```yaml
# base manifest
apiVersion: game/v1
kind: Enemy
metadata:
  name: goblin-base
spec:
  description: "A small, aggressive humanoid with yellowed fangs."
  loot_table:
    - item: goblin-ear
      weight: 80

# variant inherits and overrides
apiVersion: game/v1
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

### JSON Schema for IDE Support

**Effort: M** · **Group: Authoring Tooling**

Publish JSON Schema files for all manifest kinds so content authors get autocomplete, inline documentation, and red underlines for invalid fields in VS Code, Neovim, and other editors without any extra plugins. This is a documentation/tooling deliverable, not an engine change.

Schema files live in `schemas/` and are registered in the project so editors can associate them with `game/v1` manifests automatically via a `.vscode/settings.json` mapping or a `yaml-language-server` directive.

### Content Validation CLI Improvements

**Effort: M** · **Group: Authoring Tooling**

The `oscilla validate` command currently reports schema errors. Extend it to catch semantic errors that are currently only discovered at runtime:

- References to undefined items, enemies, skills, milestones, or regions
- `goto` targets that never exist in the same adventure (already caught, but error messages could be richer)
- Unreachable adventures (an adventure pool entry whose `requires` condition can never be met given the content package)
- Circular region parent chains
- Orphaned content (manifests that are defined but never referenced anywhere)

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

### Picture Selection and ASCII Art

**Effort: M** · **Group: —**

Allow content manifests to associate images with locations, characters, enemies, items, and adventures. In the terminal TUI, images are rendered as ASCII art; in the web front end, they are displayed as standard images.

Implementation notes:

- The [`ascii-magic`](https://pypi.org/project/ascii-magic/) library converts images (local paths or URLs) to ASCII art suitable for terminal display — zero custom rasterization code required
- Manifests declare an optional `image:` field pointing to a bundled asset path within the content package
- The TUI rendering layer checks terminal width and scales ASCII output accordingly
- The web front end ignores the ASCII conversion and serves the original image
- Content authors are not required to provide images; the field is always optional and the engine renders gracefully without one

---

## Technical Debt

### Remove base_adventure_count Field

**Effort: XS** · **Group: Technical Debt**

The `base_adventure_count` field exists in the `GameSpec` Pydantic model (in `oscilla/engine/models/game.py`) and in the `testlandia/game.yaml` content package, but is never read anywhere in the engine. It was likely a placeholder that was superseded before it was ever implemented.

- Remove `base_adventure_count` from the `GameSpec` model
- Remove the field from `testlandia/game.yaml` and any other content packages that still declare it
- Add a load warning (or schema validation error) for a grace period if backward compatibility is needed

This was already removed from the author documentation; the code simply needs to catch up.

### Remove Condition Shorthand Syntax

**Effort: S** · **Group: Technical Debt**

The condition evaluator currently supports two syntaxes for conditions: an explicit form (`{type: level, value: 5}`) and a shorthand form (`{level: 5}`). The `normalise_condition()` function in `oscilla/engine/models/base.py` converts shorthand to explicit at load time.

The shorthand syntax adds maintenance surface, makes condition schemas harder to validate, and creates inconsistency in the author docs (some examples use one form, some use the other). The explicit form is unambiguous and already well-documented.

Migration plan:

1. Emit a load warning when shorthand syntax is detected (see the Load Warnings spec)
2. Update all content packages (`content/`, `tests/fixtures/`) to use explicit syntax
3. Remove `normalise_condition()` and all shorthand handling from the engine
