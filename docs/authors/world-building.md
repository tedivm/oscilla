# World Building

The world players explore is organized in three tiers: **regions** contain **locations**, and locations contain **adventure pools**. Regions handle access control for broad areas. Locations host the moment-to-moment encounters and can be weighted however you like.

This document covers map structure, unlock conditions, and adventure pools. Adventures themselves are covered in [Adventures](./adventures.md).

---

## Regions

A region is a named area of your world: a kingdom, a forest, a dungeon depth. Every location belongs to exactly one region.

```
content/my-kingdom/
└── regions/
    └── the-forest/
        ├── the-forest.yaml      ← region manifest
        └── locations/
            └── hunters-camp/
                ├── hunters-camp.yaml
                └── adventures/
```

### Minimal Region

```yaml
apiVersion: oscilla/v1
kind: Region
metadata:
  name: the-forest
spec:
  displayName: "The Forest"
  description: "Ancient woodland that hides many dangers."
```

`metadata.name` is the region's unique identifier. It does not need to match the directory name — the engine finds manifests by scanning all `.yaml` files recursively, not by path.

### Nested Regions

Regions can nest inside other regions using the `parent` field. This is useful for representing areas with hierarchical access — you must reach the wilderness before finding the dungeon within it.

```yaml
apiVersion: oscilla/v1
kind: Region
metadata:
  name: dungeon
spec:
  displayName: "The Ancient Dungeon"
  description: "A labyrinth beneath the wilderness."
  parent: wilderness
  unlock:
    type: all
    conditions:
      - type: level
        value: 7
      - type: milestone
        name: found-dungeon-entrance
```

Players can only enter a child region when they meet its unlock condition _and_ they can already access the parent region.

### Unlocking Regions

The `unlock` field accepts any [condition](./conditions.md). The region is hidden from the player until the condition is met.

```yaml
unlock:
  type: level
  value: 5 # simple: unlock at level 5
```

```yaml
unlock:
  type: all
  conditions:
    - type: level
      value: 10
    - type: milestone
      name: joined-guild # all conditions must be true
```

```yaml
unlock:
  type: any
  conditions:
    - type: milestone
      name: guild-pass # either condition is enough
    - type: milestone
      name: noble-escort
```

Omitting `unlock` entirely means the region is always available from the start of the game.

---

## Locations

A location is a specific explorable place within a region. When a player chooses to visit a location, the engine picks an adventure from its pool and runs it.

```
regions/the-forest/
└── locations/
    └── dark-clearing/
        ├── dark-clearing.yaml   ← location manifest
        └── adventures/          ← adventure manifests
```

### Minimal Location

```yaml
apiVersion: oscilla/v1
kind: Location
metadata:
  name: dark-clearing
spec:
  displayName: "Dark Clearing"
  description: "Light barely reaches the floor through the canopy."
  region: the-forest
  adventures:
    - ref: ambush
      weight: 60
    - ref: mushroom-patch
      weight: 40
```

The `region` field must match the region's `metadata.name`. The engine resolves this by name across all loaded manifests — the location file does not need to be physically inside a region folder.

### Adventure Pools

The `adventures` list is your location's weighted pool. Each entry names an [adventure](./adventures.md) (by its `metadata.name`) and gives it a relative weight.

```yaml
adventures:
  - ref: patrol-guard
    weight: 50
  - ref: lost-merchant
    weight: 30
  - ref: hidden-shrine
    weight: 20
```

**Weights are relative.** A 60/40 pool and a 3/2 pool behave the same way. The engine randomly picks one entry using these weights each time the player visits.

### Locked Adventures

An adventure can be conditionally included in the pool. The `condition` field accepts any [condition](./conditions.md).

```yaml
adventures:
  - ref: normal-forage
    weight: 70
  - ref: herb-expert-forage
    weight: 30
    condition:
      type: skill
      name: herbalism # only available once the player has this skill
```

Adventures whose conditions aren't met are excluded from that visit's pool entirely. If all adventures in a pool are excluded, the player is told there is nothing to do at this location.

### Unlock Conditions on Locations

Locations can also be hidden until unlocked — using the same `unlock` field as regions.

```yaml
spec:
  displayName: "Smuggler's Cave"
  description: "A hidden cove only the well-informed know about."
  region: coast
  unlock:
    type: milestone
    name: heard-rumor-of-cave
  adventures:
    - ref: smuggler-cache
      weight: 100
```

---

## How the Loader Discovers Your World

The engine recursively scans **all** `.yaml` files anywhere under your package directory and loads each one by its `kind` field. Folder names, file names, and nesting depth are irrelevant to discovery.

This means folder structure is entirely up to you:

```
# Completely flat — works fine
my-game/
  game.yaml
  character_config.yaml
  the-forest.yaml
  forest-clearing.yaml
  bandit-camp.yaml
  goblin.yaml
  collect-herbs.yaml

# Nested to mirror the world hierarchy — recommended for larger games
my-game/
  game.yaml
  character_config.yaml
  regions/
    forest/
      forest.yaml
      locations/
        clearing/
          clearing.yaml
          adventures/
            …
```

Organize your files however makes sense to you. The nested convention is recommended for larger packages because it keeps related files together and makes the world structure legible at a glance, but it is not enforced.

---

## Reference

### Region manifest fields

| Field              | Required | Description                                                  |
| ------------------ | -------- | ------------------------------------------------------------ |
| `apiVersion`       | yes      | Must be `oscilla/v1`                                         |
| `kind`             | yes      | Must be `Region`                                             |
| `metadata.name`    | yes      | Unique identifier for this region; used for cross-references |
| `spec.displayName` | yes      | Player-facing region name                                    |
| `spec.description` | no       | Short description shown in navigation                        |
| `spec.parent`      | no       | `metadata.name` of a parent region                           |
| `spec.unlock`      | no       | Condition that controls access; omit for always-available    |

### Location manifest fields

| Field              | Required | Description                                                    |
| ------------------ | -------- | -------------------------------------------------------------- |
| `apiVersion`       | yes      | Must be `oscilla/v1`                                           |
| `kind`             | yes      | Must be `Location`                                             |
| `metadata.name`    | yes      | Unique identifier for this location; used for cross-references |
| `spec.displayName` | yes      | Player-facing location name                                    |
| `spec.description` | no       | Short description shown in navigation                          |
| `spec.region`      | yes      | `metadata.name` of the owning region                           |
| `spec.unlock`      | no       | Condition that controls access                                 |
| `spec.adventures`  | yes      | List of adventure pool entries (at least one)                  |

### Adventure pool entry fields

| Field       | Required | Description                               |
| ----------- | -------- | ----------------------------------------- |
| `ref`       | yes      | `metadata.name` of the adventure manifest |
| `weight`    | yes      | Relative probability (positive integer)   |
| `condition` | no       | Any condition; entry excluded when false  |

---

_Next: [Adventures](./adventures.md) — building individual encounters with branching narrative._
_See [Conditions](./conditions.md) for the full unlock and pool-condition syntax._
