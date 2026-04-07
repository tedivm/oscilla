# Getting Started

This tutorial walks you through creating a minimal Oscilla content package from scratch. By the end you will have a working game: one region, one location, one adventure, one enemy, and a player character with a stat.

You don't need to understand every field before you begin. Start simple, run it, then build from there.

---

## Prerequisites

Make sure Oscilla is installed and your `GAMES_PATH` environment variable points to a directory where you want to create content. By default it's the `content/` folder in the project root.

```bash
uv run oscilla --help   # confirms the CLI works
```

---

## Step 1: Create the Package Directory

Every game starts as a named directory under your content path.

```bash
mkdir content/my-first-kingdom
```

All your files will live in or under this directory. The directory name becomes the game's identifier — use lowercase with hyphens.

> **Folder structure is a suggestion, not a requirement.** The engine recursively scans your entire package directory for `.yaml` files and loads them by their `kind` field — not by where they sit on disk. The only hard path requirement is `game.yaml` at the package root. Every other file can be placed and named however you like. The nested structure used in this tutorial is a convention that keeps large content packages organized, but a flat directory works equally well.

---

## Step 2: Write `game.yaml`

This file defines your game's rules. Create `content/my-first-kingdom/game.yaml`:

```yaml
apiVersion: oscilla/v1
kind: Game
metadata:
  name: my-first-kingdom
spec:
  displayName: "My First Kingdom"
  description: "A humble beginning."
  xp_thresholds: [100, 300, 600, 1000]
  hp_formula:
    base_hp: 20
    hp_per_level: 8
```

This gives you 5 levels (1 baseline + 4 thresholds). Max HP at level 5: 20 + 4×8 = 52.

`metadata.name` is your game's identifier and must match the directory name. This is the one place where name and path are connected — everything else in the engine uses `metadata.name` for cross-references, not file paths.

---

## Step 3: Write `character_config.yaml`

This file defines the player. Create `content/my-first-kingdom/character_config.yaml`:

```yaml
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: my-first-kingdom-character
spec:
  public_stats:
    - name: strength
      type: int
      default: 10
      description: "Physical power."
    - name: gold
      type: int
      default: 0
      description: "Coins carried."
      bounds:
        min: 0
```

Two stats: `strength` (no bounds — can go negative if something reduces it) and `gold` (clamped at 0).

---

## Step 4: Create a Region

Regions are named areas. Create the directory and manifest:

```bash
mkdir -p content/my-first-kingdom/regions/the-village
```

Create `content/my-first-kingdom/regions/the-village/the-village.yaml`:

```yaml
apiVersion: oscilla/v1
kind: Region
metadata:
  name: the-village
spec:
  displayName: "The Village"
  description: "A quiet settlement at the edge of the wilderness."
```

---

## Step 5: Create a Location

Locations are explorable places within a region. Create the directory:

```bash
mkdir -p content/my-first-kingdom/regions/the-village/locations/market-square
```

Create `content/my-first-kingdom/regions/the-village/locations/market-square/market-square.yaml`:

```yaml
apiVersion: oscilla/v1
kind: Location
metadata:
  name: market-square
spec:
  displayName: "Market Square"
  description: "Merchants and travelers gather here. Trouble is never far."
  region: the-village
  adventures:
    - ref: bandit-shakedown
      weight: 1
```

The `region` field must match the region's `metadata.name`. The weight here is just `1` — it doesn't matter for a single-adventure pool.

---

## Step 6: Create an Enemy

Adventures need something to fight. Create the directory and manifest:

```bash
mkdir -p content/my-first-kingdom/regions/the-village/locations/market-square/enemies
```

Create `content/my-first-kingdom/regions/the-village/locations/market-square/enemies/street-thug.yaml`:

```yaml
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: street-bandit
spec:
  displayName: "Street Bandit"
  description: "A desperate criminal looking for an easy mark."
  hp: 20
  attack: 8
  defense: 2
  xp_reward: 30
```

---

## Step 7: Create an Adventure

Adventures are what players actually do inside a location. Create the directory:

```bash
mkdir -p content/my-first-kingdom/regions/the-village/locations/market-square/adventures
```

Create `content/my-first-kingdom/regions/the-village/locations/market-square/adventures/bandit-shakedown.yaml`:

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: bandit-shakedown
spec:
  displayName: "Bandit Shakedown"
  description: "A rough-looking figure demands your coin."
  steps:
    - type: narrative
      text: |
        A scar-faced man blocks the narrow alley. "Pay the toll," he growls,
        "or I'll take it from your corpse."

    - type: choice
      prompt: "What do you do?"
      options:
        - label: "Fight back"
          steps:
            - type: combat
              enemy: street-bandit
              on_win:
                effects:
                  - type: xp_grant
                    amount: 30
                steps:
                  - type: narrative
                    text: |
                      The thug goes down clutching his ribs. Passers-by pretend not
                      to notice. You find a few coins on him.
                    effects:
                      - type: stat_change
                        stat: gold
                        amount: 5
              on_defeat:
                effects:
                  - type: end_adventure
                    outcome: defeated
              on_flee:
                steps:
                  - type: narrative
                    text: "You sprint away, heart pounding. The thug doesn't follow."
                effects:
                  - type: end_adventure
                    outcome: fled

        - label: "Pay the toll"
          steps:
            - type: narrative
              text: |
                You hand over a few coins. The thug pockets them without a word
                and slinks back into the shadows.
            effects:
              - type: stat_change
                stat: gold
                amount: -3
```

---

## Step 8: Review Your File Tree

Your package should look like this:

```
content/my-first-kingdom/
├── game.yaml
├── character_config.yaml
└── regions/
    └── the-village/
        ├── the-village.yaml
        └── locations/
            └── market-square/
                ├── market-square.yaml
                ├── enemies/
                │   └── street-thug.yaml
                └── adventures/
                    └── bandit-shakedown.yaml
```

---

## Step 9: Validate Your Package

Before playing, ask Oscilla to check your files for errors:

```bash
uv run oscilla validate --game my-first-kingdom
```

If the loader finds any problems — unknown references, missing required fields, a condition that names an undeclared stat — it will tell you exactly what's wrong and in which file. Fix any errors reported before continuing.

You can also run without `--game` to validate all packages at once:

```bash
uv run oscilla validate
```

Add `--strict` to treat warnings as errors, which is useful before publishing your content:

```bash
uv run oscilla validate --game my-first-kingdom --strict
```

---

## Multi-Manifest Files

As your content package grows you may want to group related manifests in a single file rather than creating a separate file for each one. Oscilla supports multiple YAML documents in one file using the standard `---` divider.

Each document is validated independently, so you can mix different manifest kinds freely:

```yaml
apiVersion: oscilla/v1
kind: Item
metadata:
  name: bronze-coin
spec:
  displayName: "Bronze Coin"
  description: "A common copper coin."
  category: currency
  stackable: true
  value: 1

---
apiVersion: oscilla/v1
kind: Item
metadata:
  name: silver-coin
spec:
  displayName: "Silver Coin"
  description: "Worth ten bronze coins."
  category: currency
  stackable: true
  value: 10
```

File naming is unrestricted — you can call the file `coins.yaml`, `currency.yaml`, or anything else. Single-manifest files continue to work exactly as before; multi-document support is purely additive.

If a document in a multi-manifest file has an error, the error message includes the document index (e.g., `[doc 2]`) so you can locate the problem without counting `---` dividers manually.

---

## Step 10: Run the Game

Once validation passes, start the game:

```bash
uv run oscilla game start
```

Select **My First Kingdom**, create a character, and navigate to **The Village → Market Square** to play your first adventure.

---

## What to Build Next

From this minimal base, the natural next steps are:

**Add more combat variety.** Give your enemy skills. Add item drops. Create a second enemy with different stats.

**Add depth to the adventure.** Add a `stat_check` step that branches based on `strength`. Add a `milestone_grant` so you can track whether the player has encountered this thug.

**Expand the world.** Add a second location to the village. Create a second region with an `unlock` condition (like reaching level 2). Nest a dungeon inside the wilderness.

**Give players items.** Define some items and add `item_drop` effects to combat outcomes. Define equipment slots in `character_config.yaml` and create gear the player can equip.

---

_The rest of this documentation covers each of these systems in depth:_

- [Conditions](./conditions.md) — branching logic
- [Effects](./effects.md) — rewards and state changes
- [Templates](./templates.md) — dynamic text
- [Game Configuration](./game-configuration.md) — `game.yaml` and `character_config.yaml` in full
- [World Building](./world-building.md) — regions and locations
- [Adventures](./adventures.md) — all step types
- [Items](./items.md) — consumables, gear, crafting ingredients
- [Enemies](./enemies.md) — combat encounters
- [Skills](./skills.md) — skills and buffs
- [Quests](./quests.md) — multi-stage storylines
- [Recipes](./recipes.md) — crafting
