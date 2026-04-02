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

| Item | Effort | Group |
|------|--------|-------|
| Date and Time Conditions | S | Calendar Conditions |
| Calendar Functions in Conditions | XS | Calendar Conditions |
| Triggered Adventures | M | — |
| Decision Tree AI for Enemies | L | Combat Overhaul |
| Combat System Refactor | XL | Combat Overhaul |
| Documentation Refactor and Rebuild | M | — |
| Character Archetypes | M | Character Progression |
| Talent Trees / Passive Upgrades | L | Character Progression |
| Passive Event Step | S | Adventure Authoring |
| Adventure Repeat Controls | S | Adventure Authoring |
| Shop and Vendor System | L | Economy & NPCs |
| Item Requirements (Prerequisites) | S | Item Enhancements |
| Item Charges | S | Item Enhancements |
| Conditional Passive Effects | M | Item Enhancements |
| Item Labels / Display Tags | M | Item Enhancements |
| Persistent NPCs and Dialogue | L | Economy & NPCs |
| Quest Failure States | S | Quest Depth |
| Quest Branching | M | Quest Depth & Factions |
| Faction and Reputation System | M | Quest Depth & Factions |
| Named Random Tables | S | Content Reuse |
| Content Inheritance / Prototypes | M | Content Reuse |
| JSON Schema for IDE Support | M | Authoring Tooling |
| Content Validation CLI Improvements | M | Authoring Tooling |
| HTTP API for Multi-User Support | XL | Multi-User Platform |
| Front End Website | XL | Multi-User Platform |
| Picture Selection and ASCII Art | M | — |

---

## Condition System

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

---

## Documentation

### Documentation Refactor and Rebuild

**Effort: M** · **Group: —**

The current documentation has grown incrementally alongside the codebase and needs a holistic review and restructure. Goals:

- Audit all existing documents in `docs/dev/` and `docs/authors/` for accuracy and completeness
- Establish a clear information architecture: orientation (what is this?), how-to guides (how do I do X?), reference (what are all the options?), and explanation (why does it work this way?)
- Ensure every major engine subsystem has a corresponding developer document
- Ensure every content authoring concept (stats, conditions, skills, templates, combat, regions) has a corresponding author document
- Add a top-level `docs/README.md` that orients both audiences and links to both `docs/dev/README.md` and `docs/authors/README.md`
- Remove or archive stale documents that describe features that no longer exist or have changed significantly

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

---

## Adventure System

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

---

## Item System

### Shop and Vendor System

**Effort: L** · **Group: Economy & NPCs**

There is currently no mechanism for authors to define item exchanges — trading one resource for another. A vendor system gives content authors a manifest kind for declaring merchants with stock, prices, and availability, without the engine ever knowing what currency or items mean.

The economic model is entirely author-defined: prices are costs expressed as stat deltas (whatever stat the author uses as currency), and item value for resale is any field the author declares on their items. A fantasy game uses `gold`; a sci-fi game uses `credits`; a barter economy uses any combination of item grants and removals.

Key design points:

- Vendors are a manifest kind (`kind: Vendor`) where each stock entry declares an availability condition and a transaction effect list (deduct currency stat, grant item)
- Buying and selling are both just choice steps whose effects are the transaction — no special engine logic for commerce
- Vendor-exclusive items are simply items whose only `item_grant` source is a vendor manifest entry
- Stock availability uses the standard condition system; a vendor can have items that appear only after a milestone, only while the player holds a certain archetype, or only during a specific season

### Item Requirements (Prerequisites)

**Effort: S** · **Group: Item Enhancements**

Allow items to declare requirements — conditions that must be met for the player to equip or use an item effectively. A player can still carry the item but cannot equip it (or its stat modifiers do not apply) until the requirement is met.

```yaml
equip:
  slots:
    - main_hand
  requires:
    type: character_stat
    name: strength
    gte: 15           # Must have 15 strength to wield
  stat_modifiers:
    - stat: strength
      amount: 5
```

Uses the existing condition system; no new predicate types needed.

### Item Charges

**Effort: S** · **Group: Item Enhancements**

A consumable variant where the item has multiple uses before being fully consumed. Distinct from stackable items (multiple copies) — charges are uses remaining on a single instance.

```yaml
spec:
  displayName: "Arcane Lantern"
  charges: 5                # Uses remaining before the item is depleted
  consumed_on_use: true     # Decrements charge; removed when charges reach 0
  use_effects:
    - type: stat_change
      stat: light_radius
      amount: 1
```

### Conditional Passive Effects

**Effort: M** · **Group: Item Enhancements**

A general mechanism for declaring passive `stat_modifiers` and `skill_grants` that are only active while a condition is true. The condition is evaluated continuously against the full character state — inventory, equipped items, stats, and milestones — so bonuses appear and disappear automatically as state changes.

This naturally subsumes item sets (bonus when specific items are equipped together) but is far more expressive: the triggering condition is any condition the engine already knows how to evaluate.

```yaml
# Declared in game.yaml or a dedicated PassiveEffect manifest
passive_effects:
  - name: ranger-focus
    condition:
      type: and
      conditions:
        - type: item_equipped
          item: rangers-cloak
        - type: any_item_equipped
          labels:
            - ranger-bow     # matches any bow tagged 'ranger-bow', not one specific item
    stat_modifiers:
      - stat: dexterity
        amount: 5
    skill_grants:
      - skill: hunters-mark

  - name: veterans-resolve
    condition:
      type: and
      conditions:
        - type: item_equipped
          item: veterans-sword
        - type: milestone
          name: survived-the-siege   # also requires a story milestone
    stat_modifiers:
      - stat: strength
        amount: 3
```

Because the triggering condition uses the existing condition evaluator:

- A "set" can require one item from a list (`any_item_equipped`) rather than one specific item
- Bonuses can also gate on stats, milestones, archetypes, or any combination
- The same condition predicates used in adventure gating work here — no new engine concepts required
- Authors can declare effects in `game.yaml` (global), or inside an item manifest (scoped to that item's presence)

### Item Labels / Display Tags

**Effort: M** · **Group: Item Enhancements**

A generic, author-defined label system for items that allows game content to signal display intent to the TUI without the engine hardcoding any specific taxonomy. Labels are free-form strings declared on each item; the TUI maps them to colors, icons, sort order, or other visual treatments via a lookup table defined in `game.yaml`.

This deliberately avoids baking a fixed rarity tier system into the engine. Authors who want a traditional rarity system can define one (`common`, `uncommon`, `rare`, `legendary`). Authors who want something else entirely — quality grades (`crude`, `standard`, `masterwork`), material families (`iron`, `silver`, `mithril`), provenance tags (`cursed`, `blessed`, `contraband`) — can do so without any engine changes.

```yaml
# In game.yaml: declare the label display rules for this game
item_labels:
  - name: legendary
    color: gold
    sort_priority: 1
  - name: rare
    color: blue
    sort_priority: 2
  - name: cursed
    color: red
    sort_priority: 3

# On an item: assign one or more labels
spec:
  displayName: "Vorpal Blade"
  labels:
    - legendary
    - cursed
```

Items can carry multiple labels simultaneously. Labels are exposed in all three authoring systems:

- **TUI / presentation**: `game.yaml` maps each label name to a color, icon, and sort priority. No engine behavior is hardcoded.
- **Condition system**: an `item_has_label` predicate allows content to gate adventures, choices, or regions on whether the player is carrying any item with a given label (e.g., gate a pawnbroker's fence dialogue behind possessing a `contraband`-labeled item).
- **Template system**: the player's inventory view exposes labels, so templates can branch on or display them (e.g., `{% if item.labels contains 'cursed' %}`).

This makes labels a first-class authoring primitive rather than a purely cosmetic annotation, while keeping the engine agnostic about what the labels mean.

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
