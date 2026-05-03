# Custom Effects

Custom effects are named, parameterized sequences of standard effects. They let you define reusable effect compositions once, then call them from anywhere with different parameters — like functions in a scripting language.

## Manifest Format

Custom effects are defined as `CustomEffect` manifests:

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: heal_percentage
spec:
  displayName: "Heal Percentage"
  description: "Heals the player for a percentage of their max HP."
  parameters:
    - name: percent
      type: float
      default: 25
  effects:
    - type: stat_change
      stat: hp
      amount: "{{ min(player.stats['max_hp'] - player.stats['hp'], floor(player.stats['max_hp'] * params.percent / 100)) }}"
      target: player
```

### Fields

| Field         | Type  | Required | Description                                                              |
| ------------- | ----- | -------- | ------------------------------------------------------------------------ |
| `name`        | `str` | yes      | Unique manifest name; used to reference this custom effect at call sites |
| `displayName` | `str` | no       | Human-readable name for tooling and debug output                         |
| `description` | `str` | no       | Documentation string for this custom effect                              |
| `parameters`  | list  | no       | Typed parameter schema (empty list = no parameters)                      |
| `effects`     | list  | yes      | Effect body — one or more standard effects (or nested custom effects)    |

### Parameters

Each parameter declares a name, type, and optional default:

| Field     | Type                                          | Required | Description                                                        |
| --------- | --------------------------------------------- | -------- | ------------------------------------------------------------------ |
| `name`    | `str`                                         | yes      | Parameter name; must be unique within the custom effect            |
| `type`    | `"int"` \| `"float"` \| `"str"` \| `"bool"`   | yes      | Parameter type for validation                                      |
| `default` | `int` \| `float` \| `str` \| `bool` \| `null` | no       | Default value; if omitted, the parameter is required at call sites |

Parameter types:

- **`int`**: Integer values. `bool` is rejected (Python bool is a subclass of int).
- **`float`**: Numeric values. `int` is accepted as a valid float.
- **`str`**: String values.
- **`bool`**: Boolean values (`true` / `false`).

## Call Sites

At any `effects:` list, use `type: custom_effect` to call a custom effect:

```yaml
effects:
  - type: custom_effect
    name: heal_percentage
    params:
      percent: 50
```

### Fields

| Field    | Type  | Required | Description                                                      |
| -------- | ----- | -------- | ---------------------------------------------------------------- |
| `name`   | `str` | yes      | CustomEffect manifest name to invoke                             |
| `params` | dict  | no       | Per-call parameter overrides; merged on top of declared defaults |

**Important**: `params` values must be **literal scalars** (`int`, `float`, `str`, `bool`). Template expressions like `"{{ player.stats.hp }}"` are not allowed in params.

## Composition

Custom effects can call other custom effects, enabling reusable compositions:

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: full_recovery
spec:
  displayName: "Full Recovery"
  parameters: []
  effects:
    - type: custom_effect
      name: heal_percentage
      params:
        percent: 100
    - type: custom_effect
      name: grant_reward
      params:
        stat: gold
        amount: 50
```

Each level of nesting gets its own isolated `params` frame — parameters from one level never leak into another.

## Where Custom Effects Can Be Used

Custom effects can be called from any `effects:` list:

- **Adventures**: narrative steps, choice options, stat check branches, combat outcomes
- **Items**: `use_effects`
- **Skills**: `use_effects`
- **Archetypes**: `gain_effects` and `lose_effects`
- **Buffs**: `per_turn_effects`
- **Other custom effects**: nested composition

## Load-Time Validation

The engine validates all custom effect references at load time:

- **Dangling references**: `name` must match a declared CustomEffect manifest
- **Circular dependencies**: A → B → A chains are rejected with a clear error
- **Unknown parameters**: `params` keys must be declared in the target's parameter schema
- **Type mismatches**: Values must match the declared parameter type
- **Missing required parameters**: Parameters without defaults must be supplied

## Examples

### Simple Stat Grant

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: grant_xp
spec:
  displayName: "Grant XP"
  parameters:
    - name: amount
      type: int
  effects:
    - type: stat_change
      stat: experience
      amount: "{{ params.amount }}"
      target: player
```

### Multi-Effect with Defaults

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: reward_and_milestone
spec:
  displayName: "Reward and Milestone"
  parameters:
    - name: stat
      type: str
    - name: amount
      type: int
    - name: milestone
      type: str
  effects:
    - type: stat_change
      stat: "{{ params.stat }}"
      amount: "{{ params.amount }}"
      target: player
    - type: milestone_grant
      milestone: "{{ params.milestone }}"
```

### Nested Composition

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: chain_demo
spec:
  displayName: "Chain Demo"
  parameters: []
  effects:
    - type: custom_effect
      name: heal_percentage
      params:
        percent: 50
    - type: custom_effect
      name: reward_and_milestone
      params:
        stat: strength
        amount: 5
        milestone: chain_demo_completed
```

---

_See [Effects](./effects.md#custom-effects) for the call site syntax and usage patterns._
_See [Templates](./templates.md) for `params` template variable usage in effect fields._
