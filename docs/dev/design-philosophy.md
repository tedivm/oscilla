# Design Philosophy

Oscilla is built around a small number of recurring ideas. Understanding them makes it easier to evaluate proposed features, spot designs that work against the grain of the system, and write content and engine code that fits naturally alongside everything else.

---

## The Engine Is a Platform, Not a Game

Oscilla ships no assumptions about what kind of game you are making. There is no hardcoded class system, no fixed rarity taxonomy, no mandatory faction structure, and no single correct combat model. The engine's job is to provide expressive, composable primitives that content authors assemble into whatever experience they want to build.

A design that forces all games to look like one specific genre is a design failure, even if that genre is a perfectly good one.

---

## Author-Defined Vocabulary, Not Engine-Hardcoded Mechanics

Whenever the engine needs a named category — item quality, character class, faction, archetype, label — the vocabulary must be defined by the content package in `game.yaml`, not compiled into the engine source.

**Why this matters:** An engine that hard-codes `common / uncommon / rare / epic / legendary` has already made a genre choice. A content package set in a historical fiction world, a comedy game, or a sci-fi setting must either fight those names or work around them. Author-defined vocabularies eliminate that constraint entirely.

**The pattern in practice:**

- Item labels: authors declare `item_labels` in `game.yaml` and map each name to display rules (color, sort order). The engine stores and exposes the labels; it never interprets them.
- Character archetypes: authors declare the archetype vocabulary in `game.yaml` with optional per-archetype stat growth and skill category lists. A package that does not want a class system simply omits the key.
- Factions: authors declare faction names in `game.yaml`; the engine tracks reputation as bounded stats with first-class syntax. The engine does not know or care what the factions represent.

A feature is correctly designed when a content author can build two completely different implementations of that feature — traditional RPG classes and guild membership in a merchant game, for example — without any engine changes.

---

## Condition Evaluator as the Universal Gate

The condition evaluator is the engine's most reusable primitive. Any place in the system where a decision depends on character state — adventure pool gating, step branching, item requirements, passive effect activation, triggered adventure guards, skill locks — should use the same condition evaluator with the same predicate vocabulary.

**Consequences of this principle:**

- Adding a new predicate type once makes it available everywhere conditions appear.
- Content authors learn one syntax and apply it throughout their manifests.
- Engine developers do not build bespoke "check logic" for each subsystem.

When a proposed feature requires its own one-off condition-like syntax in a single manifest kind, that is a sign the condition evaluator should be extended rather than bypassed.

---

## Opt-In Complexity

Features must be invisible to content packages that do not use them. A game that does not declare `archetypes` in `game.yaml` must behave identically to a game that predates the archetype system. A game with no `item_labels` must not experience any difference in behavior or validation errors.

This holds for both authoring ergonomics (no required boilerplate) and runtime behavior (no empty-list checks forced on every pipeline evaluation).

The corollary: global defaults and fallback behavior must always be defined. When the engine evaluates a condition against a character with no archetypes, it must produce a sensible result, not an exception.

---

## Effects Are Composable, Not Hardcoded

Effects — `stat_change`, `item_grant`, `skill_grant`, `milestone_set`, and so on — are the atomic units of change in the game world. Complex behaviors are built by composing effects, not by adding special-case logic to the engine.

**Examples:**

- "Set bonus when two specific items are equipped" is not a special set-bonus system. It is a conditional passive effect whose condition happens to check equipped items.
- "Multi-classing" is not a special multi-class screen. It is an adventure that applies `archetype_add` effects based on player choices.
- "Class change quest" is not a special class-change event. It is an adventure with `archetype_remove` and `archetype_add` effects.

When a proposed feature can be expressed as an adventure with standard effects, it should be. New effect types and new engine subsystems are warranted only when the required behavior genuinely cannot be composed from existing primitives.

---

## Three Authoring Systems, One Consistent Model

Content authors interact with character state through three surfaces:

1. **Condition system** — gates on what is true about the character right now
2. **Effect system** — changes character state
3. **Template system** — renders character state into narrative text

Any first-class data attached to a character — stats, milestones, inventory, equipped items, archetypes, labels — must be fully accessible from all three surfaces. A feature that is visible in templates but not queryable in conditions, or queryable in conditions but not modifiable by effects, is only partially implemented.

---

## Separation of Content from Engine

Content packages live in the `content/` directory and are loaded at runtime. The engine in `oscilla/` must never import from, reference by name, or depend on any specific content package.

This separation allows:

- Multiple independent content packages to coexist in the same installation
- The test suite to use minimal synthetic fixture content without any dependency on `content/testlandia/` or `content/the-example-kingdom/`
- Content packages to be distributed, versioned, and swapped independently of the engine

Engine code that would only work with a specific content package is always wrong.

---

## Manifest-Driven Over Code-Driven

Content is data. Behavior that content authors need to express should be achievable by writing YAML manifests, not by writing Python. The engine's role is to make the manifest language expressive enough that authors do not need to reach for code.

The threshold for "expressive enough" is: can a non-programmer author build a complete, interesting game using only manifests? When the answer is no for a common authoring need, the engine needs a new primitive — not a workaround that requires authors to understand Python internals.
