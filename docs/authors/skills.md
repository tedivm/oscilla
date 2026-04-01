# Skills and Buffs

This guide covers the `Skill` and `Buff` manifest kinds, how to wire them to characters, enemies, and items, and how the combat system uses them.

For a quick overview of all manifest kinds, see the [Content Authoring Guide](./content-authoring.md).

---

## Skills (`skills/`)

A **Skill** is a learnable, activatable ability. Skills are declared once and referenced by name from character config, items, and effects that grant them to the player.

### Minimal Example

```yaml
apiVersion: game/v1
kind: Skill
metadata:
  name: arcane-shield
spec:
  displayName: Arcane Shield
  description: "Conjure a barrier that absorbs 40% of incoming damage for 3 turns."
  contexts:
    - combat
  use_effects:
    - type: apply_buff
      buff_ref: shielded
```

### `SkillSpec` Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `displayName` | `str` | required | Player-facing name shown in menus |
| `description` | `str` | `""` | Flavor text |
| `category` | `str` | `""` | Informational grouping label; engine enforced only when `skill_category_rules` are configured in `CharacterConfig` |
| `contexts` | list of `"combat"` \| `"overworld"` | required (min 1) | Contexts where this skill may be activated |
| `requires` | Condition \| null | `null` | Condition gate checked on every activation attempt (not just at grant time) |
| `cost` | SkillCost \| null | `null` | Resource consumed on each use |
| `cooldown` | SkillCooldown \| null | `null` | Cooldown between uses |
| `use_effects` | list of Effects | `[]` | Effects dispatched once when the skill is activated |

### `SkillCost` Fields

```yaml
cost:
  stat: mana          # Stat name for the resource pool
  amount: 20          # Amount deducted per use (minimum 1)
```

If the player lacks sufficient resource, the skill is blocked and an error message is shown.

### `SkillCooldown` Fields

```yaml
cooldown:
  scope: turn         # "turn" (resets each combat) or "adventure" (persists across adventures)
  count: 1            # Number of turns/adventures required between uses
```

- **`turn`** scope: the skill cannot be used more than once per combat turn (handy for once-per-turn abilities).
- **`adventure`** scope: the cooldown persists between adventures and is stored in the character's save data. The counter decrements when an adventure ends.

### Skill Effects

`use_effects` supports all standard Effects plus `apply_buff`:

```yaml
use_effects:
  # Deal immediate damage to the enemy
  - type: heal
    amount: -10
    target: enemy     # "player" (default) or "enemy"

  # Apply a timed combat buff (defined as a Buff manifest)
  - type: apply_buff
    buff_ref: on-fire
    target: player    # Who receives the buff (default: "player")
    variables:        # Optional per-call overrides for the buff's variables
      reflect_percent: 60
```

See the [Effects reference](./content-authoring.md#all-effect-types) for the full list. Note that `StatSetEffect` cannot target enemies.

### Skill with `requires` Condition

The `requires` condition is evaluated each time the player tries to activate a skill during combat. If it fails, the skill is shown as unavailable. This allows skills to have activation pre-conditions beyond cooldowns and resources:

```yaml
requires:
  type: character_stat
  stat: hp
  operator: lte
  value: 20           # Only usable when HP is at or below 20%
```

---

## Buffs (`buffs/`)

A **Buff** is a named, reusable timed combat effect. Buffs are always granted through `apply_buff` effects — in `SkillSpec.use_effects`, `ItemSpec.use_effects`, or `ItemSpec.grants_buffs_equipped`/`grants_buffs_held`. The same buff manifest can be applied by multiple different sources without duplication.

The buff's manifest `name` is its stable identity. `DispelEffect` targets buffs by this name.

### Minimal Example

```yaml
apiVersion: game/v1
kind: Buff
metadata:
  name: shielded
spec:
  displayName: Arcane Shield
  description: "A shimmering barrier that absorbs 40% of incoming damage."
  duration_turns: 3
  modifiers:
    - type: damage_reduction
      percent: 40
      target: player
```

### `BuffSpec` Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `displayName` | `str` | required | Player-facing name shown when the buff is applied |
| `description` | `str` | `""` | Flavor text |
| `duration_turns` | `int` | required (≥ 1) | Number of combat turns this buff remains active |
| `per_turn_effects` | list of Effects | `[]` | Effects dispatched at the start of each round while active |
| `modifiers` | list of CombatModifiers | `[]` | Passive damage-arithmetic adjustments active until the buff expires |
| `variables` | dict[str, int] | `{}` | Named integer parameters with default values; can be overridden at apply time |

**At least one of `per_turn_effects` or `modifiers` must be non-empty.** A buff with neither is rejected at load time.

### Tick Effects (`per_turn_effects`)

These effects fire once at the start of each round for as long as the buff is active. Usually used for damage-over-time or healing-over-time:

```yaml
apiVersion: game/v1
kind: Buff
metadata:
  name: on-fire
spec:
  displayName: On Fire
  description: "Burning flames — deals 10 damage per turn."
  duration_turns: 3
  per_turn_effects:
    - type: heal
      amount: -10        # negative heal = damage
      target: player
```

### Passive Modifiers (`modifiers`)

Modifiers adjust damage arithmetic while the buff is active. There are four types:

#### `damage_reduction`

Reduces all **incoming** damage received by `target` by `percent`%.

```yaml
modifiers:
  - type: damage_reduction
    percent: 40          # 1–99 (100 would be invulnerability, which is disallowed)
    target: player       # "player" (default) or "enemy"
```

#### `damage_amplify`

Increases all **outgoing** damage dealt by `target` by `percent`%.

```yaml
modifiers:
  - type: damage_amplify
    percent: 50          # ≥ 1
    target: player
```

#### `damage_reflect`

Returns `percent`% of all damage received by `target` back to the attacker.

```yaml
modifiers:
  - type: damage_reflect
    percent: 30          # 1–100
    target: player
```

#### `damage_vulnerability`

Increases all **incoming** damage received by `target` by `percent`% (a debuff).

```yaml
modifiers:
  - type: damage_vulnerability
    percent: 25          # ≥ 1
    target: player
```

**Combined modifiers:** When both `damage_reduction` and `damage_vulnerability` are active on the same target simultaneously, the engine combines them additively. For example, 40% reduction + 25% vulnerability = net 15% reduction (factor 0.85).

### Buff Variables

The `variables` block declares named integer parameters with default values. `modifier` `percent` fields can reference these names instead of hardcoding values, then be overridden at each apply site:

```yaml
apiVersion: game/v1
kind: Buff
metadata:
  name: thorns
spec:
  displayName: Thorns
  description: "Reflects a percentage of incoming damage back at attackers."
  duration_turns: 3
  variables:
    reflect_percent: 30     # default value
  modifiers:
    - type: damage_reflect
      percent: reflect_percent   # variable reference
      target: player
```

When this buff is applied without overrides, `reflect_percent` resolves to `30`. A call site may supply a different value:

```yaml
- type: apply_buff
  buff_ref: thorns
  variables:
    reflect_percent: 60   # overrides the manifest default
```

Referencing an undeclared variable name in a modifier is a load-time error.

---

## Applying Buffs: `apply_buff` Effect

`apply_buff` is the only way to grant a buff. It can appear in skill `use_effects`, item `use_effects`, or as a `grants_buffs_equipped`/`grants_buffs_held` entry on items.

```yaml
- type: apply_buff
  buff_ref: shielded     # Buff manifest name (required)
  target: player         # "player" or "enemy" (default: "player")
  variables:             # Optional — overrides buff manifest variable defaults
    reflect_percent: 60
```

If `apply_buff` is used outside of combat (e.g., in an overworld adventure effect), it is silently skipped — buffs only exist within a combat context.

---

## Removing Buffs: `dispel` Effect

The `dispel` effect removes an active buff from a target by its manifest name:

```yaml
- type: dispel
  label: on-fire         # Buff manifest name to remove (exact match)
  target: player         # "player" or "enemy" (default: "player")
```

Outside combat, `dispel` is silently skipped. This allows consumables (like Water) to have a `dispel` that safely does nothing when used from the main menu.

---

## Skills on Items

Items can grant skills or buffs while equipped or held in inventory.

### `grants_skills_equipped`

Skills granted only while this item occupies an equipment slot. Removed when unequipped:

```yaml
grants_skills_equipped:
  - battle-cry       # Skill manifest name
  - shield-bash
```

### `grants_skills_held`

Skills granted while this item is anywhere in the character's inventory (equipped or not):

```yaml
grants_skills_held:
  - identify-item    # Granted even if the item is not equipped
```

### `grants_buffs_equipped`

Buff grants applied automatically at the start of every combat while this item occupies an equipment slot. The buff is re-applied fresh each time combat begins:

```yaml
grants_buffs_equipped:
  - buff_ref: thorns          # Buff manifest name
    # No variables — uses manifest defaults (reflect_percent: 30)
```

With a variable override:

```yaml
grants_buffs_equipped:
  - buff_ref: thorns
    variables:
      reflect_percent: 60     # This item grants thorns at 60% instead of the default 30%
```

### `grants_buffs_held`

Same as `grants_buffs_equipped` but triggers for any item in inventory, not just equipped ones:

```yaml
grants_buffs_held:
  - buff_ref: shielded
```

### Complete Item Example

```yaml
apiVersion: game/v1
kind: Item
metadata:
  name: master-thorns-sword
spec:
  category: weapon
  displayName: Master Thorns Sword
  description: "A masterwork blade crackling with barbs. Reflects 60% of damage back at attackers."
  consumed_on_use: false
  stackable: false
  equip:
    slots:
      - main_hand
  grants_buffs_equipped:
    - buff_ref: thorns
      variables:
        reflect_percent: 60
```

---

## Skills in CharacterConfig

`CharacterConfig` supports two skill-related configuration blocks.

### `skill_resources`

Maps the resource names used by `SkillCost` to actual character stats:

```yaml
skill_resources:
  - name: mana             # Resource name used in SkillCost.stat
    stat: mana             # Stat holding the current value
    max_stat: max_mana     # Stat holding the maximum (shown in UI)
```

Both `stat` and `max_stat` must reference stats declared in `public_stats` or `hidden_stats`. A load-time error is raised if either is missing.

### `skill_category_rules`

Optional rules that govern which skills from a category a character can learn simultaneously:

```yaml
skill_category_rules:
  - category: magic
    max_known: 3            # At most 3 magic skills at once (null = unlimited)
  - category: warrior
    max_known: 2
    exclusive_with:
      - magic               # Cannot know warrior OR magic skills simultaneously
```

- **`max_known`**: if set, `grant_skill` will refuse to add a skill in this category once the limit is reached.
- **`exclusive_with`**: if set, knowing any skill in any named category blocks learning skills in this category (and vice versa).

Rules are entirely optional. If `skill_category_rules` is omitted or empty, no restrictions are applied.

---

## Enemy Skills

Enemies declare skills directly on their spec:

```yaml
apiVersion: game/v1
kind: Enemy
metadata:
  name: fire-mage
spec:
  displayName: Fire Mage
  hp: 40
  attack: 6
  defense: 2
  xp_reward: 60
  skills:
    - skill_ref: enemy-fireball
      use_every_n_turns: 3      # Fires on turn 3, 6, 9, …
    - skill_ref: enemy-weakness-curse
      use_every_n_turns: 4      # Fires on turn 4, 8, 12, …
  skill_resources:
    mana: 80                    # Starting mana pool
```

### `EnemySkillEntry` Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `skill_ref` | `str` | required | Skill manifest name |
| `use_every_n_turns` | `int` | `0` | Trigger on every nth turn (starting turn 1). `0` = never triggered automatically |

### Enemy Skill Resources (`skill_resources`)

`skill_resources` is a flat `name → starting_value` dictionary. These values are not persisted — they reset at the start of each combat. If the enemy runs out of a required resource, the skill is skipped.

```yaml
skill_resources:
  mana: 80
  rage: 40
```

---

## Overworld vs. Combat Contexts

Skills declare which contexts they support via `contexts`:

```yaml
contexts:
  - combat      # Can be used during combat
  - overworld   # Can be used from the overworld actions screen
```

At least one context must be declared. A skill with only `overworld` does not appear in combat menus, and vice versa.

> **Note:** Buff-related effects (`apply_buff`, `dispel`) are silently skipped outside combat. This ensures that items and skills are safe to use in overworld contexts even if they include buff effects alongside other effects (such as heals).

---

## Reference: All Buff Modifier Types

| Type | Effect | `percent` Range |
|---|---|---|
| `damage_reduction` | Reduces incoming damage to `target` | 1–99 |
| `damage_amplify` | Increases outgoing damage from `target` | ≥ 1 |
| `damage_reflect` | Returns damage from `target` to attacker | 1–100 |
| `damage_vulnerability` | Increases incoming damage to `target` | ≥ 1 |

All modifier `percent` fields accept either an integer literal or a variable name declared in the buff's `variables` block.

---

*For engine implementation details — CombatContext, cooldown tracking, and `run_effect()` internals — see the [Game Engine Documentation](../dev/game-engine.md#skill-and-buff-system).*
