# Adventures

An adventure is a single interactive encounter: a conversation, a fight, a mystery to solve. Adventures are the primary way players experience your world. Each adventure is a sequence of **steps** — narrative passages, combat encounters, branching choices, and conditional checks.

---

## Basic Structure

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: rat-infestation
spec:
  displayName: "Rat Infestation"
  description: "The innkeeper needs the cellar cleared."
  steps:
    - type: narrative
      text: |
        The innkeeper leads you downstairs. A skittering sound echoes in the dark.
```

The `metadata.name` is what you reference in a location's [adventure pool](./world-building.md#adventure-pools) (the `ref` field). `displayName` and `description` appear in loading screens and elsewhere in the UI.

## Browser Interface

Adventures run in the web browser through the **play screen** (`/characters/{id}/play`). The browser connects to the backend via a POST-based SSE stream. Each step type maps to a distinct UI widget:

| Step type    | Browser widget                            |
| ------------ | ----------------------------------------- |
| `narrative`  | Text entry appended to the narrative log  |
| `choice`     | Choice menu with keyboard shortcuts (1–9) |
| `ack`        | Continue prompt (Enter / Space)           |
| `combat`     | Combat HUD with HP bars per combatant     |
| `text_input` | Free-text input form                      |
| `skill_menu` | Skill card grid with cooldown indicators  |

After an adventure ends, the player is returned to the **overworld view**, which shows their current location, available adventures, and navigation options.

As an author you do not need to configure the browser interface — the engine drives it automatically based on step types. The `displayName` and `description` fields from your adventure manifest are used when the adventure appears in the overworld adventure list.

Adventures live inside their owning location directory:

A common convention is to place adventure manifests alongside their owning location:

```
regions/kingdom/locations/village-square/
├── village-square.yaml
└── adventures/
    ├── rat-infestation.yaml
    └── merchant-dispute.yaml
```

Because the engine discovers manifests by scanning all `.yaml` files recursively, adventures can be placed anywhere in your package — folder names and nesting depth don't affect which adventure pool they belong to. That's determined entirely by the location manifest's `adventures` list (by `ref` name).

### Access Control

An adventure can declare a `requires` [condition](./conditions.md). Players who don't meet it are never shown this adventure (the pool entry is filtered out).

```yaml
spec:
  displayName: "Elite Training"
  description: "A master warrior offers advanced lessons."
  requires:
    type: level
    value: 10 # only appears for players level 10 or above
  steps: …
```

---

## Step Types

There are four step types. Steps run in order; each step must complete before the next begins.

### Narrative

The simplest step: display text and wait for the player to continue. Attach [`effects`](./effects.md) to fire silently once the player acknowledges.

```yaml
- type: narrative
  text: |
    You push through the iron gate and step into the moonlit courtyard.
    Something rustles in the hedgerow.
  effects:
    - type: milestone_grant
      milestone: entered-the-courtyard
```

Use narrative steps to set scenes, deliver story beats, and describe the outcome of choices. They don't require any decisions from the player.

### Combat

Turn-based combat against an [enemy](./enemies.md). The player and enemy trade attacks each round until one dies or the player flees. Attach branching outcomes for each resolution.

```yaml
- type: combat
  enemy: town-rat # must match an Enemy manifest's metadata.name
  on_win:
    effects:
      - type: xp_grant
        amount: 25
    steps:
      - type: narrative
        text: "The rat is dead. The cellar is quiet again."
  on_defeat:
    effects:
      - type: end_adventure
        outcome: defeated
  on_flee:
    effects:
      - type: end_adventure
        outcome: fled
```

`on_win`, `on_defeat`, and `on_flee` are **outcome branches**. Each branch can carry:

- [`effects`](./effects.md) — fire silently (XP grants, item drops, milestones, stat changes)
- `steps` — run additional steps (narrative, more combat, choices)
- `goto` — jump to a labeled step elsewhere in the adventure

`effects` and `steps`/`goto` are independent: you can have both. Effects fire first, then steps run (or the jump happens).

### Choice

Present a menu of options. Options with unmet `requires` conditions are hidden entirely — the player never sees them.

```yaml
- type: choice
  prompt: "Two doors. Which do you try?"
  options:
    - label: "The iron door (requires Dungeon Key)"
      requires:
        type: item
        item_ref: dungeon-key
        quantity: 1
      steps:
        - type: narrative
          text: "The key turns smoothly. The door opens onto a treasure vault."
      effects:
        - type: milestone_grant
          milestone: found-vault

    - label: "The wooden door"
      steps:
        - type: combat
          enemy: door-guard
          on_win:
            steps:
              - type: narrative
                text: "You step over the guard. A damp storeroom."
          on_defeat:
            effects:
              - type: end_adventure
                outcome: defeated
```

Each option has:

- `label` — the text shown to the player
- `requires` — optional condition; option hidden when false
- `effects` — fire before nested steps or before a goto jump
- `steps` — nested step sequence to run when the option is selected
- `goto` — jump to a labeled top-level step instead of running nested steps

`goto` and `steps` are mutually exclusive in a single option. Use `steps` when the option leads to its own short sequence of narrative, combat, or further choices. Use `goto` when the option should converge on a step that already exists elsewhere in the adventure — for example, multiple choices that all lead to the same "you were caught" scene. You cannot combine them because the engine would have no way to determine which to run first or whether to run both. If you need to both run some steps _and_ then continue at a label, add your steps inline and place the label on the step you want to reach; inline steps naturally fall through to whatever follows them in the adventure.

```yaml
# Scenario: two options both end up at a shared "alarm raised" scene,
# but one option runs some extra steps first.

- type: choice
  prompt: "How do you enter the vault?"
  options:
    - label: "Sneak through the window"
      steps:
        - type: narrative
          text: "You squeeze through—and knock over a candlestick. Alarm bells ring."
        # Falls through to the next top-level step (alarm-raised) automatically.

    - label: "Kick down the door"
      goto: alarm-raised # skip straight to the shared scene

- label: alarm-raised
  type: narrative
  text: "Guards pour into the corridor from every direction."
  effects:
    - type: end_adventure
      outcome: defeated
```

In this example the sneaking option needs its own narrative before the shared outcome, so it uses `steps`. Those steps run in order and then the adventure simply continues to the next top-level step — which carries the `alarm-raised` label. The door-kicking option has nothing unique to say, so it jumps directly with `goto`.

If all options in a choice step are hidden (none of their conditions are met), the step is skipped silently. Design your adventures so there is always at least one visible option when a choice step could be reached.

### Stat Check

Branch automatically based on any [condition](./conditions.md) — no player input.

```yaml
- type: stat_check
  condition:
    type: character_stat
    name: strength
    gte: 15
  on_pass:
    steps:
      - type: narrative
        text: "You heave the boulder aside with ease."
    effects:
      - type: xp_grant
        amount: 10
  on_fail:
    steps:
      - type: narrative
        text: "The boulder won't budge. You look for another path."
```

`on_pass` and `on_fail` are outcome branches with the same `effects`/`steps`/`goto` structure as combat outcomes.

Use stat checks for anything that should branch on player state without presenting a menu: perception checks, passive skill triggers, milestone-based dialogue forks, and so on.

## Passive Steps

Apply effects automatically — no player input, no branching. A passive step fires its `effects` in order and continues to the next step.

```yaml
- type: passive
  text: "A warm glow washes over you. You feel restored."
  effects:
    - type: heal
      amount: 15
```

All fields are optional. Omit `text` to apply effects silently:

```yaml
- type: passive
  effects:
    - type: milestone_grant
      milestone: entered-inner-sanctum
```

#### Bypass condition

Declare a `bypass` condition to skip the step (and its effects) automatically when the condition is met. Use this for traps or challenges that skilled or well-equipped players sidestep without a choice menu.

```yaml
- type: passive
  text: "A pressure plate triggers a dart trap. You take 10 damage."
  effects:
    - type: stat_change
      stat: hp
      amount: -10
  bypass:
    type: character_stat
    name: dexterity
    gte: 12
  bypass_text: "Your quick reflexes carry you past the pressure plate unscathed."
```

When `bypass` evaluates to **true**:

- `bypass_text` is shown to the player (if set).
- The step's `effects` and `text` are **not** shown or applied.

When `bypass` evaluates to **false** (or is absent):

- `text` is shown (if set).
- `effects` are applied in order.

Omit `bypass_text` for a fully silent bypass.

---

## Goto and Labels

Any step can carry a `label`. This makes it a target for `goto` jumps from outcome branches and choice options.

```yaml
- type: combat
  enemy: boss-one
  on_win:
    steps:
      - type: narrative
        text: "The first guardian falls."
  on_defeat:
    goto: shared-defeat # jumps to the labeled step below

- type: combat
  enemy: boss-two
  on_win:
    steps:
      - type: narrative
        text: "The second guardian falls."
  on_defeat:
    goto: shared-defeat # both combats share the same defeat text

- label: shared-defeat
  type: narrative
  text: "The ancient magic overwhelms you. The dungeon expels your broken body."
  effects:
    - type: end_adventure
      outcome: defeated
```

Labels must be unique across all steps in an adventure. The engine validates this at load time.

`goto` is especially useful when multiple branches converge on the same narrative outcome. It avoids duplicating text.

---

## Ending Adventures Early

By default, an adventure ends when all top-level steps have run. Use [`end_adventure`](./effects.md#end-adventure) in an effects list to force an early end with a specific outcome.

```yaml
effects:
  - type: milestone_grant
    milestone: chose-to-flee
  - type: end_adventure
    outcome: fled
```

The three built-in outcome names — `completed`, `defeated`, `fled` — are always valid without any extra declaration. To use custom outcome names in your content package, declare them in `game.yaml` first. See [Outcome Definitions](#outcome-definitions) below.

Effects appearing before `end_adventure` in the same list still fire.

---

## Outcome Definitions

Adventures report an outcome when they end. Three outcome names are built into the engine and are always valid:

| Outcome     | Meaning                                     |
| ----------- | ------------------------------------------- |
| `completed` | The adventure ran to its normal conclusion. |
| `defeated`  | The player was beaten in combat.            |
| `fled`      | The player retreated via a flee option.     |

You can define additional outcome names in `game.yaml` to track story-specific results:

```yaml
# game.yaml
spec:
  outcomes:
    - discovered
    - rescued
    - fled-early
```

Once declared, your custom outcome name can be used in any `end_adventure` effect across the content package:

```yaml
effects:
  - type: end_adventure
    outcome: discovered
```

The loader enforces this: using an outcome name that is not built-in and not declared in `game.yaml` is a load-time error.

> **Note:** Outcome tracking is per-adventure. The engine records how many times each outcome fired for each adventure. Built-in analytics and future questing features can inspect these counts.

---

## A Complete Example

This adventure uses all four step types and demonstrates goto:

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: forest-shrine
spec:
  displayName: "Forest Shrine"
  description: "An old shrine pulses with faint light."
  steps:
    - type: narrative
      text: |
        Moss-covered stones form a ring around a cracked altar.
        A faint glow emanates from its center.

    - type: stat_check
      condition:
        type: milestone
        name: lore-scholar
      on_pass:
        steps:
          - type: narrative
            text: "You recognize the sigils — this is a binding altar."
        effects:
          - type: milestone_grant
            milestone: identified-shrine

    - type: choice
      prompt: "What do you do at the altar?"
      options:
        - label: "Offer your blood"
          steps:
            - type: narrative
              text: "A sharp sting. The glow intensifies, then fades."
          effects:
            - type: stat_change
              stat: hp
              amount: -5
            - type: xp_grant
              amount: 60
            - type: milestone_grant
              milestone: offered-blood-shrine

        - label: "Smash the altar"
          steps:
            - type: combat
              enemy: shrine-guardian
              on_win:
                effects:
                  - type: xp_grant
                    amount: 100
                steps:
                  - type: narrative
                    text: "The guardian falls. The glow is gone."
              on_defeat:
                goto: guardian-wins
              on_flee:
                goto: fled-shrine

        - label: "Leave it alone"
          steps:
            - type: narrative
              text: "Some things are better left undisturbed."

    - label: guardian-wins
      type: narrative
      text: "The guardian drives you from the grove."
      effects:
        - type: end_adventure
          outcome: defeated

    - label: fled-shrine
      type: narrative
      text: "You retreat through the trees. The glow watches you go."
      effects:
        - type: end_adventure
          outcome: fled
```

---

## Reference

### Adventure manifest fields

| Field              | Required | Description                                                  |
| ------------------ | -------- | ------------------------------------------------------------ |
| `metadata.name`    | yes      | Identifier used in location pool `ref` fields                |
| `spec.displayName` | yes      | Player-facing title                                          |
| `spec.description` | no       | Short description                                            |
| `spec.requires`    | no       | Condition that prevents this adventure appearing in any pool |
| `spec.steps`       | yes      | Ordered list of steps (at least one)                         |

### Step types

| Type         | Description                                          |
| ------------ | ---------------------------------------------------- |
| `narrative`  | Display text; optional silent effects                |
| `combat`     | Turn-based fight with win/defeat/flee branches       |
| `choice`     | Player-facing menu; options may have conditions      |
| `stat_check` | Automatic condition branch; no player input          |
| `passive`    | Silent auto-apply effects; optional bypass condition |

### Outcome branch fields (on_win, on_defeat, on_flee, on_pass, on_fail)

| Field     | Type   | Description                          |
| --------- | ------ | ------------------------------------ |
| `effects` | list   | Effects that fire silently           |
| `steps`   | list   | Nested steps to run                  |
| `goto`    | string | Label of a top-level step to jump to |

`steps` and `goto` are mutually exclusive. Both are optional (an empty branch is valid).

### Choice option fields

| Field      | Required | Description                                    |
| ---------- | -------- | ---------------------------------------------- |
| `label`    | yes      | Player-facing option text                      |
| `requires` | no       | Condition; option hidden when false            |
| `effects`  | no       | Fire before steps or goto                      |
| `steps`    | no       | Nested steps to run                            |
| `goto`     | no       | Step label to jump to (exclusive with `steps`) |

---

## Repeat Controls

By default, every adventure can be run as many times as the player likes. Use the optional fields to limit how often an adventure appears in the pool.

| Field             | Type           | Default | Description                                                                                |
| ----------------- | -------------- | ------- | ------------------------------------------------------------------------------------------ |
| `repeatable`      | bool           | `true`  | Set to `false` to make an adventure a one-shot that disappears after the first completion. |
| `max_completions` | int            | none    | Hard cap: the adventure is hidden once the player has completed it this many times.        |
| `cooldown`        | Cooldown block | none    | Time or tick constraint that must pass between runs. See [Cooldowns](./cooldowns.md).      |

`repeatable: false` and `max_completions` are mutually exclusive — choose one or the other.

### One-shot adventure

An adventure that can only ever be played once:

```yaml
displayName: "The Lost Shrine"
repeatable: false
steps:
  - type: narrative
    name: start
    text: "You find a hidden shrine. It crumbles as you leave."
    choices:
      - label: "Leave"
        effects:
          - type: end_adventure
            outcome: completed
```

### Cooldown adventure

An adventure that can be replayed, but only after 3 more adventures have been completed:

```yaml
displayName: "The Bandit Camp"
repeatable: true
cooldown:
  ticks: 3
steps:
  - type: combat
    name: fight
    enemy: bandit-leader
    on_win:
      effects:
        - type: end_adventure
          outcome: completed
    on_defeat:
      effects:
        - type: end_adventure
          outcome: defeated
```

For time-based cooldowns (e.g. once per day) and combining multiple constraints, see the [Cooldowns reference](./cooldowns.md).

### Notes on cooldown tracking

- `cooldown.ticks` counts total adventures completed across all locations, not just in the current region.
- All repeat-control state resets when the character starts a new iteration (prestige run).

---

## Triggered Adventures

Adventures can also be run automatically in response to game events — without the player selecting them from a location's pool. These are called **triggered adventures**.

A triggered adventure uses exactly the same manifest structure as any other adventure. There is nothing special about the YAML file itself. What makes an adventure "triggered" is how it is wired in `game.yaml`:

```yaml
# game.yaml
spec:
  trigger_adventures:
    on_level_up:
      - level-up-fanfare # runs every time the player levels up
```

Triggered adventures respect the same `requires`, `repeatable`, `max_completions`, `cooldown_days`, and `cooldown_ticks` controls as pool adventures. If the condition is not met, that adventure is silently skipped; others in the list still run.

See [Game Configuration — Triggered Adventures](./game-configuration.md#triggered-adventures) for the full list of trigger event types and the complete `triggers` + `trigger_adventures` schema.

---

## Character Creation Adventures

When a new character is created, the engine fires the `on_character_create` trigger. Any adventure wired to that event runs automatically before the player reaches the world map. This is the canonical place to welcome new players, collect a character name, prompt for pronouns, and apply backstory bonuses.

### Wiring a creation adventure

```yaml
# game.yaml
spec:
  trigger_adventures:
    on_character_create:
      - your-character-creation-adventure
```

### Collecting a name with `set_name`

The `type: set_name` effect always prompts the player and replaces their current name. Use a `requires` condition on the step to control when the prompt is shown — for example, only run the step when the character still has the engine's default name (`"Adventurer"`):

```yaml
- type: narrative
  text: "A stranger stirs at the threshold."
  requires:
    type: name_equals
    value: "Adventurer"
  effects:
    - type: set_name
      prompt: "What is your name, traveler?"
```

The `requires` condition is evaluated before the step runs. If the condition fails, the step is silently skipped. This means:

- Players who supplied `--character-name` at the CLI already have a non-default name, so the step is automatically skipped.
- Games that set `character_creation.default_name` in `game.yaml` (to something other than `"Adventurer"`) must adjust the `value` in the condition accordingly.

### Pronoun selection

Use `type: set_pronouns` (in a choice step) to let players pick their pronouns:

```yaml
- type: choice
  prompt: "How should others refer to you?"
  options:
    - label: "They / Them"
      effects:
        - type: set_pronouns
          set: they_them
    - label: "She / Her"
      effects:
        - type: set_pronouns
          set: she_her
    - label: "He / Him"
      effects:
        - type: set_pronouns
          set: he_him
```

### Backstory bonuses

Give players a small starting advantage via stat changes or milestone grants inside choice options — same as any other adventure step.

### Complete creation adventure example

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: character-creation
spec:
  displayName: "Who Are You?"
  repeatable: false
  steps:
    - type: narrative
      text: "A new traveler arrives at the crossroads."
      requires:
        type: name_equals
        value: "Adventurer"
      effects:
        - type: set_name
          prompt: "What is your name?"

    - type: choice
      prompt: "How should others refer to you?"
      options:
        - label: "They / Them"
          effects:
            - type: set_pronouns
              set: they_them
        - label: "She / Her"
          effects:
            - type: set_pronouns
              set: she_her
        - label: "He / Him"
          effects:
            - type: set_pronouns
              set: he_him

    - type: choice
      prompt: "What drove you to adventure?"
      options:
        - label: "Hard labour (Strength +2)"
          effects:
            - type: stat_change
              stat: strength
              amount: 2
        - label: "Shady dealings (Gold +15)"
          effects:
            - type: stat_change
              stat: gold
              amount: 15

    - type: narrative
      text: "Welcome, {{ player.name }}. {They} {are} ready to write {their} legend."
```

---

## The Prestige Effect

The `type: prestige` effect resets the character's progression (level, XP, HP, items, skills, quests) while carrying forward any stats, skills, or milestones configured in the game's `prestige:` block. After the effect runs, the engine increments `prestige_count` and signals the session layer to open a new DB iteration row at adventure end.

```yaml
- type: narrative
  text: "You have reached the peak of your power. Legacy: {{ player.stats.legacy_power }}."

- type: choice
  prompt: "Will you step through the ritual and begin again?"
  options:
    - label: "Prestige"
      effects:
        - type: prestige
    - label: "Turn back"
      effects:
        - type: end_adventure
          outcome: completed
```

The `type: prestige` effect is only valid when the game package declares a `prestige:` block in `game.yaml`. Loading a content package where an adventure uses `type: prestige` without a prestige block configured is a content load error.

See [Game Configuration — Prestige](./game-configuration.md#prestige) for the complete prestige block schema.

---

_See [Effects](./effects.md) for the full list of effect types._
_See [Conditions](./conditions.md) for the full condition syntax used in `requires` and `stat_check`._
_See [Enemies](./enemies.md) for enemy manifest syntax._
