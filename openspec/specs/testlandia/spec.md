# Testlandia

## Purpose

Testlandia is the built-in developer sandbox game package. It provides a complete, minimal game that lets developers manually exercise every major engine feature without relying on narrative content or the production game package.

## Requirements

### Requirement: Testlandia is a developer sandbox game package

Testlandia SHALL be a complete game package located at `content/testlandia/` within the game library root. It SHALL contain a `game.yaml`, a `character_config.yaml`, and a set of regions and locations that collectively allow a developer to manually exercise every major engine feature without relying on narrative content.

#### Scenario: Testlandia loads cleanly with no errors

- **WHEN** `oscilla validate --game testlandia` is run
- **THEN** the command exits with code 0

#### Scenario: Testlandia is available in multi-game selection

- **WHEN** `oscilla game` is run and both `the-kingdom` and `testlandia` are present
- **THEN** both games appear in the selection screen

---

### Requirement: Testlandia CharacterConfig covers all supported stat types

The Testlandia `character_config.yaml` SHALL declare stats covering all three supported stat types (`int`, `float`, `bool`) and SHALL include at least one stat with a `null` default.

**Public stats:** `strength` (int, default 10), `speed` (float, default 1.0), `is_blessed` (bool, default false), `gold` (int, default 0).

**Hidden stats:** `debug_counter` (int, default 0).

#### Scenario: New Testlandia character has correct defaults

- **WHEN** a new character is created in Testlandia
- **THEN** `strength = 10`, `speed = 1.0`, `is_blessed = false`, `gold = 0`, `debug_counter = 0`

---

### Requirement: Testlandia Character Realm exercises stat and level manipulation

The Character Realm SHALL contain locations that allow a developer to directly manipulate character stats, HP, XP, and level.

Required locations and their primary adventures:

| Location        | Adventure          | Primary mechanic tested                                                   |
| --------------- | ------------------ | ------------------------------------------------------------------------- |
| `heal`          | `full-heal`        | `heal: full` effect                                                       |
| `heal`          | `partial-heal`     | `heal: 10` effect                                                         |
| `xp-lab`        | `gain-xp-small`    | small `xp_grant` (50 XP)                                                  |
| `xp-lab`        | `gain-xp-level-up` | large `xp_grant` causing level-up                                         |
| `xp-lab`        | `lose-xp-delevel`  | large negative `xp_grant` causing de-level                                |
| `stat-workshop` | `bump-strength`    | `stat_change: strength +1`                                                |
| `stat-workshop` | `drop-strength`    | `stat_change: strength -1`                                                |
| `stat-workshop` | `bump-speed`       | `stat_change: speed +0.5`                                                 |
| `stat-workshop` | `set-strength`     | `stat_set: strength 15`                                                   |
| `stat-workshop` | `toggle-blessed`   | `stat_set: is_blessed true/false` (two adventures: `bless` and `unbless`) |

#### Scenario: Developer can heal to full from Character Realm

- **WHEN** the developer navigates to the `heal` location and runs `full-heal`
- **THEN** the player's HP is restored to `max_hp`

#### Scenario: Developer can de-level from Character Realm

- **WHEN** the developer navigates to `xp-lab` and runs `lose-xp-delevel`
- **THEN** the player loses levels and the TUI displays de-level messages

---

### Requirement: Testlandia Combat Realm exercises combat at multiple difficulties

The Combat Realm SHALL provide locations with enemies of different difficulties so a developer can test combat outcomes (win, defeat, flee).

Required locations: `easy-arena` (enemy always defeatable at level 1), `hard-arena` (enemy strong enough to regularly defeat a fresh character), `flee-arena` (adventure with a clear flee path).

#### Scenario: Developer can defeat easy enemy

- **WHEN** the developer runs the easy-arena adventure at level 1
- **THEN** a level 1 character can reliably win

#### Scenario: Developer can test flee

- **WHEN** the developer runs the flee-arena adventure and chooses to flee
- **THEN** the adventure ends with outcome `fled`

---

### Requirement: Testlandia Conditions Realm exercises condition-gated content

The Conditions Realm SHALL contain locations and adventures that test condition evaluation: milestone gates, stat gates, `and` conditions, and `or` conditions.

Required locations: `badge-issuer` (grants milestone `dev-badge`), `milestone-gate` (unlocked only with `dev-badge`), `stat-gate` (unlocked only when `strength >= 15`), `condition-lab` (open, contains adventures testing `and` and `or` conditions inline).

#### Scenario: Milestone-gated location is inaccessible before badge

- **WHEN** a developer has not visited `badge-issuer`
- **THEN** `milestone-gate` does not appear in the available locations list

#### Scenario: Milestone-gated location is accessible after badge

- **WHEN** a developer runs the `get-badge` adventure in `badge-issuer`
- **THEN** `milestone-gate` appears in the available locations list

---

### Requirement: Testlandia Choices Realm exercises adventure flow control

The Choices Realm SHALL contain adventures that test the narrative step types: binary choice, nested choices, `stat_check` branching, and `goto` label jumps.

Required adventures: `binary-choice` (two options, each with a distinct narrative), `nested-choice` (a choice whose branch contains another choice), `stat-check-branch` (outcome differs based on a stat condition), `goto-demo` (uses a label and goto to loop or skip).

#### Scenario: Binary choice presents two options

- **WHEN** a developer runs `binary-choice`
- **THEN** two options are displayed and selecting each leads to a different narrative outcome

#### Scenario: stat_check branch is taken correctly

- **WHEN** a developer with `strength >= 12` runs `stat-check-branch`
- **THEN** the pass branch narrative is shown

---

### Requirement: Testlandia Items Realm exercises inventory operations

The Items Realm SHALL contain at least one item manifest and adventures that test item granting, multi-item drops, and item presence in the inventory panel.

Required adventures: `gain-item` (guaranteed single item drop), `multi-item` (item_drop with count: 3).

#### Scenario: Developer receives a guaranteed item

- **WHEN** the developer runs `gain-item`
- **THEN** the item appears in the player's inventory

---

### Requirement: Testlandia includes a template system QA region

Testlandia SHALL contain a `template-system` region that allows a developer to manually exercise every major dynamic content template feature. The region SHALL contain the following locations and adventures:

| Location                | Adventure               | Feature exercised                                                            |
| ----------------------- | ----------------------- | ---------------------------------------------------------------------------- |
| `pronoun-selection`     | `choose-pronouns`       | Pronoun set selection (all three built-ins shown as choices)                 |
| `narrative-test`        | `personalized-greeting` | `{{ player.name }}`, `{{ player.level }}`, `{they}`, `{their}`, `{is}`       |
| `variable-rewards`      | `treasure-hunt`         | `roll()` in `xp_grant.amount` and `stat_change.amount`; variable reward text |
| `conditional-narrative` | `fame-check`            | `{% if player.milestones.has(...) %}` branching narrative                    |

The region SHALL load cleanly with `oscilla validate --game testlandia` and SHALL exercise all major template features when played by a developer.

#### Scenario: Template system region loads without errors

- **WHEN** `oscilla validate --game testlandia` is run after adding the template-system region
- **THEN** the command exits with code 0

#### Scenario: Personalized greeting displays correct pronoun for she/her player

- **WHEN** a developer sets pronouns to she/her and plays `personalized-greeting`
- **THEN** the narrative text uses `"she"`, `"her"`, and `"is"` correctly

#### Scenario: Personalized greeting displays correct pronoun for they/them player

- **WHEN** a developer plays `personalized-greeting` with they/them pronouns
- **THEN** the narrative text uses `"they"`, `"their"`, and `"are"` correctly

#### Scenario: Treasure hunt grants variable XP on each play

- **WHEN** a developer plays `treasure-hunt` multiple times
- **THEN** the XP reward varies across plays (confirming `roll()` is active)

#### Scenario: Fame check branches on milestone presence

- **WHEN** a developer with the `hero-of-testlandia` milestone plays `fame-check`
- **THEN** the hero narrative branch is displayed

#### Scenario: Fame check shows default branch without milestone

- **WHEN** a developer without the `hero-of-testlandia` milestone plays `fame-check`
- **THEN** the standard narrative branch is displayed

---

### Requirement: Testlandia CharacterConfig declares they/them as default pronoun set

The Testlandia `character_config.yaml` SHALL NOT declare custom `extra_pronoun_sets` (the three built-in sets are sufficient). New Testlandia characters SHALL default to the `they_them` pronoun set.

#### Scenario: New Testlandia character has they/them pronouns by default

- **WHEN** a new character is created in Testlandia
- **THEN** `character.pronouns` is the `they_them` built-in set
