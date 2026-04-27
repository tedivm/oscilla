# Manifest Inheritance

Related manifests — enemy variant families, weapon tiers, location clusters — often share the same YAML blocks verbatim. Manifest inheritance lets you declare a base manifest once and have variants inherit from it, so shared data is defined in one place.

---

## How It Works

Any manifest can declare `metadata.base` to inherit all unspecified `spec` fields from another manifest of the same `kind`. The child's own fields replace the base's fields.

```yaml
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin-base
  abstract: true
spec:
  displayName: "Goblin"
  description: "A goblin enemy."
  stats:
    hp: 10
    attack: 3
    defense: 1
  loot:
    - entries:
        - item: copper-coin
          weight: 100

---
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin-scout
  base: goblin-base
spec:
  displayName: "Goblin Scout"
  stats:
    hp: 8
    attack: 2
```

The `goblin-scout` inherits `description`, `defense`, and `loot` from `goblin-base`. Its own `displayName`, `hp`, and `attack` replace the base values. The `stats` dict is replaced entirely — `goblin-scout` will **not** have a `defense` stat unless it declares one.

---

## Abstract Manifests

Set `metadata.abstract: true` to mark a manifest as a template-only base. Abstract manifests:

- Are **never registered** in the game's content registry
- Are **invisible at runtime** — the player can never encounter them
- May omit required fields that their children will supply
- Serve as the merge source for any child that declares `base: <name>`

```yaml
apiVersion: oscilla/v1
kind: Item
metadata:
  name: sword-base
  abstract: true
spec:
  displayName: "Sword"
  category: weapon
  stackable: false
  equip:
    slots:
      - weapon
    stat_modifiers:
      - stat: strength
        amount: 1
  grants_skills_equipped:
    - basic-slash
```

A child can then override just what's different:

```yaml
apiVersion: oscilla/v1
kind: Item
metadata:
  name: iron-sword
  base: sword-base
spec:
  displayName: "Iron Sword"
  value: 10
```

The `iron-sword` inherits `category`, `stackable`, `equip`, and `grants_skills_equipped` from `sword-base`.

---

## Extending Lists and Dicts with `+`

By default, child fields **replace** base fields. Use a `+` suffix on the field name to **extend** instead:

```yaml
apiVersion: oscilla/v1
kind: Item
metadata:
  name: silver-sword
  base: sword-base
spec:
  displayName: "Silver Sword"
  grants_skills_equipped+:
    - silver-strike
```

The `silver-sword` will have both `basic-slash` (inherited) and `silver-strike` (added).

The `+` suffix works on any list or dict field at any nesting depth:

```yaml
spec:
  equip+:
    stat_modifiers+:
      - stat: defense
        amount: 2
```

This extends the inherited `equip` block's `stat_modifiers` list rather than replacing it.

---

## Properties and `this`

Every manifest can carry a `properties` dict — static, author-defined key-value pairs available in formula and template contexts as `this`:

```yaml
apiVersion: oscilla/v1
kind: Item
metadata:
  name: iron-sword
  base: sword-base
spec:
  displayName: "Iron Sword"
  properties:
    damage_die: 4
  combat_damage_formulas:
    - target_stat: hp
      target: enemy
      formula: "{{ this.get('damage_die', 4) * player['strength'] }}"
```

The `this` variable exposes the manifest's `properties` dict:

- In **combat damage formulas**, `this` is the triggering item/skill/enemy's properties
- In **adventure step templates**, `this` is the adventure's properties
- In **load-time template validation**, `this` is populated from the manifest's own `properties`

This lets a base manifest define a formula like `{{ this.get('damage_die', 4) * player['strength'] }}` while each child sets a different `damage_die` value.

---

## Chained Inheritance

A child can itself be a base for another manifest. The engine resolves chains at load time:

```yaml
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin-chief
  base: goblin-base
spec:
  displayName: "Goblin Chief"
  stats:
    hp: 20
    attack: 5
    defense: 3

---
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin-king
  base: goblin-chief
spec:
  displayName: "Goblin King"
  stats:
    hp: 30
    attack: 8
    defense: 5
```

The `goblin-king` inherits from `goblin-chief`, which inherits from `goblin-base`. The final merged result includes all fields from the chain, with each level's overrides applied in order.

---

## Rules and Limitations

- **Same-kind only**: An `Enemy` cannot inherit from an `Item`. The `kind` must match.
- **Same-package only**: Inheritance is scoped to the content package. A manifest in `testlandia` cannot inherit from a manifest in `the-kingdom`.
- **Circular chains are errors**: `A → B → A` will fail at load time with a clear error naming the cycle.
- **Missing base references are errors**: If `base: nonexistent` refers to a manifest that doesn't exist, loading fails.
- **Unused abstract manifests produce a warning**: If an abstract manifest is never referenced as a base, you'll see a warning during validation.

---

## Common Patterns

### Enemy Variant Families

Define a base enemy with shared loot, description, and behavior. Each variant overrides stats and displayName:

```yaml
# goblin-base (abstract)
# goblin-scout (base: goblin-base) — low HP, low attack
# goblin-chief (base: goblin-base) — medium HP, medium attack
# goblin-king (base: goblin-chief) — high HP, high attack
```

### Weapon Tiers

Define a base weapon with shared equip slots, stat modifiers, and skills. Each tier overrides `properties.damage_die`, `value`, and displayName:

```yaml
# sword-base (abstract)
# iron-sword (base: sword-base) — damage_die: 4
# steel-sword (base: sword-base) — damage_die: 6
# silver-sword (base: sword-base) — damage_die: 8, extra skill with +
```

### Location Clusters

Define a base location with shared unlock conditions and region. Each variant overrides displayName, description, and adventure pool.
