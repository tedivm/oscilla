# Recipes

A recipe defines a crafting formula: a list of ingredient items the player contributes and the item they receive in exchange. The crafting screen automatically discovers all loaded recipes and presents only those for which the player has enough materials.

Recipes are a straightforward way to let players convert raw materials from adventures into useful gear or consumables.

---

## Basic Structure

```yaml
apiVersion: game/v1
kind: Recipe
metadata:
  name: brew-healing-potion
spec:
  displayName: "Brew Healing Potion"
  description: "Combine cave mushrooms and spring water into a restorative draught."
  inputs:
    - item: cave-mushroom
      quantity: 2
    - item: spring-water
      quantity: 1
  output:
    item: healing-potion
    quantity: 1
```

All items in `inputs` and `output` must match the `metadata.name` of loaded Item manifests. The loader validates references at startup.

`metadata.name` is the recipe's identifier — keep it descriptive (e.g., `forge-iron-sword` rather than just `recipe-1`).

---

## Ingredients (`inputs`)

The `inputs` list names which items to consume and how many of each. Items are consumed from the player's stacks inventory.

```yaml
inputs:
  - item: rusty-dagger
    quantity: 3
  - item: leather-scraps
    quantity: 1
```

Each ingredient entry requires `item` (an [Item](./items.md) manifest name) and `quantity` (a positive integer). All quantities must be available simultaneously — if the player has only 2 of a needed 3, the recipe is locked.

---

## Output

The `output` section declares what the player receives.

```yaml
output:
  item: iron-sword
  quantity: 1
```

For stackable output items, `quantity` controls how many copies are added. For non-stackable items, `quantity` should be `1`; higher values are not recommended since non-stackable items track as individual instances.

---

## Recipe Placement

Recipe manifests can live anywhere under your package directory — the engine scans all `.yaml` files recursively regardless of folder. A dedicated `recipes/` folder is a convenient convention for larger packages:

```
content/my-kingdom/
└── recipes/
    ├── brew-healing-potion.yaml
    ├── forge-iron-sword.yaml
    └── craft-wolf-tooth-necklace.yaml
```

Recipes are game-wide — there is no scoping by region or location. Every recipe that loads appears in the crafting menu for all players of that game.

---

## Example: Materials Pipeline

A well-designed recipe system creates a loop: adventures drop raw materials, recipes convert materials into useful items, items enable better adventures.

```yaml
# Step 1 — players gather wolf teeth from wilderness creatures
# (wolf-tooth is an item_drop in a combat adventure)

# Step 2 — combine with leather to make protective gear
apiVersion: game/v1
kind: Recipe
metadata:
  name: craft-wolf-tooth-necklace
spec:
  displayName: "Craft Wolf-Tooth Necklace"
  description: "String wolf teeth onto leather cord for a warrior's charm."
  inputs:
    - item: wolf-tooth
      quantity: 5
    - item: leather-scraps
      quantity: 1
  output:
    item: wolf-tooth-necklace
    quantity: 1
```

---

## Reference

### Recipe manifest fields

| Field | Required | Description |
|---|---|---|
| `metadata.name` | yes | Unique identifier |
| `spec.displayName` | yes | Player-facing recipe name in the crafting menu |
| `spec.description` | no | Flavor text explaining the recipe |
| `spec.inputs` | yes | List of ingredient entries (at least one) |
| `spec.output` | yes | The item and quantity produced |

### Input entry fields

| Field | Required | Description |
|---|---|---|
| `item` | yes | `metadata.name` of an Item manifest |
| `quantity` | yes | Number of this item required (positive integer) |

### Output fields

| Field | Required | Description |
|---|---|---|
| `item` | yes | `metadata.name` of an Item manifest |
| `quantity` | yes | Number of items produced (positive integer) |

---

*See [Items](./items.md) for item manifest syntax.*
*See [Effects](./effects.md) for `item_drop` — the effect that places items into a player's inventory during an adventure.*
