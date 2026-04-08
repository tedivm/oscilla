# Cooldowns

Cooldowns control how often an adventure or skill can be used. All cooldowns use a single shared `cooldown:` block with the same set of fields, whether you're writing an adventure manifest or a skill manifest.

---

## The `cooldown:` Block

```yaml
cooldown:
  ticks: 5 # Internal ticks that must elapse since last completion
  game_ticks: 10 # In-world time ticks that must elapse (requires ingame-time module)
  seconds: 3600 # Real-world seconds that must elapse
  turns: 2 # Combat turns between uses (skills only, requires scope: turn)
  scope: turn # "turn" for per-combat skills; omit for persistent cooldowns
```

All fields are optional. You must provide at least one, and any combination is valid — all constraints are AND-ed together. If any single constraint isn't satisfied, the cooldown is still active.

### Field Reference

| Field        | Type            | Applies to         | Description                                                                              |
| ------------ | --------------- | ------------------ | ---------------------------------------------------------------------------------------- |
| `ticks`      | int or template | adventures, skills | Internal ticks that must pass since the last run. One tick per adventure.                |
| `game_ticks` | int or template | adventures         | In-world time ticks since the last run.                                                  |
| `seconds`    | int or template | adventures, skills | Real-world wall-clock seconds since the last completion.                                 |
| `turns`      | int or template | skills only        | Combat turns between uses. **Requires `scope: turn`.**                                   |
| `scope`      | `"turn"`        | skills only        | When `"turn"`, cooldown is per-combat. Omit for persistent adventure-spanning cooldowns. |

### Constraint rules

- `turns` may only be used with `scope: turn`.
- `ticks`, `game_ticks`, and `seconds` may **not** be used with `scope: turn`.
- A `cooldown:` block with no constraint fields is a validation error.

---

## Adventure Cooldowns

Place a `cooldown:` block under `spec:` alongside `repeatable` and `max_completions`:

```yaml
spec:
  displayName: "The Patrol Route"
  repeatable: true
  cooldown:
    ticks: 3
  steps: …
```

This adventure will not appear in the pool until 3 adventures have been completed since the last run.

### Real-world time cooldown

Use `seconds` for a wall-clock cooldown. You can use the built-in `SECONDS_PER_*` [template constants](./templates.md#built-in-globals) so the intent stays readable:

```yaml
cooldown:
  seconds: "{{ SECONDS_PER_HOUR * 6 }}" # 6 hours
```

### Combining constraints

Multiple fields are AND-ed — the adventure is blocked until **all** constraints pass:

```yaml
cooldown:
  ticks: 5 # at least 5 adventures since last run
  seconds: "{{ SECONDS_PER_DAY }}" # AND at least 24 real-world hours
```

### Complete example

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: raid-the-vault
spec:
  displayName: "Raid the Vault"
  description: "A high-stakes heist. You can only pull this off once per day."
  repeatable: true
  cooldown:
    seconds: "{{ SECONDS_PER_DAY }}"
  steps:
    - type: narrative
      name: heist
      text: "You slip inside the vault..."
      choices:
        - label: "Loot and escape"
          effects:
            - type: end_adventure
              outcome: completed
```

For more details on `repeatable` and `max_completions`, see the [Adventures reference](./adventures.md#repeat-controls).

---

## Skill Cooldowns

### Turn-scope cooldown

Use `scope: turn` with `turns` to limit how often a skill can be used within a single combat. The cooldown resets at the start of every combat.

```yaml
# A skill usable once per turn
cooldown:
  scope: turn
  turns: 1
```

```yaml
# A skill usable only once per combat (cost is effectively "once every infinite turns")
cooldown:
  scope: turn
  turns: 9999
```

### Adventure-scope cooldown (persistent)

Omit `scope` to make the cooldown persist across adventures. Use `ticks` or `seconds`:

```yaml
# Usable once per adventure (ticks=1 means "at least 1 adventure must pass")
cooldown:
  ticks: 1
```

```yaml
# Usable once per real-world hour
cooldown:
  seconds: "{{ SECONDS_PER_HOUR }}"
```

### Complete skill example

```yaml
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: arcane-mend
spec:
  displayName: "Arcane Mend"
  description: "Restores 30 HP. Can only be used once per adventure."
  contexts:
    - overworld
  cost:
    stat: mana
    amount: 20
  cooldown:
    ticks: 1
  use_effects:
    - type: heal
      amount: 30
```

---

## Template Constants

The following constants are available in any template expression inside a `cooldown:` field:

| Constant             | Value  | Equivalent to |
| -------------------- | ------ | ------------- |
| `SECONDS_PER_MINUTE` | 60     | 1 minute      |
| `SECONDS_PER_HOUR`   | 3600   | 1 hour        |
| `SECONDS_PER_DAY`    | 86400  | 24 hours      |
| `SECONDS_PER_WEEK`   | 604800 | 7 days        |

These constants make template expressions self-documenting:

```yaml
cooldown:
  seconds: "{{ SECONDS_PER_WEEK * 2 }}" # two weeks
```

For the full list of template globals, see [Templates](./templates.md#built-in-globals).
