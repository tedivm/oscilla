# Prestige System

## Purpose

The prestige system enables content authors to design games with an explicit "new game plus" mechanic: characters can reset to their starting state while carrying forward selected stats, skills, and bonuses from previous runs. The prestige configuration lives in `game.yaml` under the `prestige:` key, making it a single authoritative declaration rather than per-adventure logic.

## Requirements

### Requirement: PrestigeConfig declared in game.yaml

A game manifest MAY declare a `prestige:` block in `game.yaml`. When declared, it SHALL configure the prestige mechanic for the entire package. When absent, the `type: prestige` effect is unavailable and any adventure that contains it causes a hard `ContentLoadError` at content load time. There is no prestige "version" or count ceiling — authors use `condition` blocks to gate content by `prestige_count`.

The `prestige:` block SHALL support the following fields:

- `carry_stats` (list of stat names, default `[]`): stat names whose current value (post-pre_prestige_effects) is copied from the old iteration state to the new.
- `carry_skills` (list of skill refs, default `[]`): skill manifest refs whose membership in `known_skills` is copied to the new iteration.
- `pre_prestige_effects` (list of effects, default `[]`): effects run against the OLD (pre-reset) character state immediately before the reset. Useful for granting legacy bonuses.
- `post_prestige_effects` (list of effects, default `[]`): effects run against the NEW (reset + carry-applied) character state immediately after the reset. Useful for granting starting bonuses on repeat runs.

#### Scenario: PrestigeConfig is optional

- **WHEN** `game.yaml` has no `prestige:` key
- **THEN** `registry.game.spec.prestige` is `None` and the content package loads without error

#### Scenario: PrestigeConfig with all defaults

- **WHEN** `game.yaml` has `prestige: {}` (empty block)
- **THEN** `prestige.carry_stats == []`, `prestige.carry_skills == []`, and both effects lists are empty

#### Scenario: carry_stats names are not validated against CharacterConfig at load time

- **WHEN** `prestige.carry_stats` lists a stat name that exists in `character_config.yaml`
- **THEN** the config loads without error

---

### Requirement: Prestige execution pipeline

When `run_effect()` dispatches a `PrestigeEffect`, the following sequence SHALL execute atomically within the `CharacterState` (in-memory only; DB transition is deferred):

1. Run each effect in `prestige_config.pre_prestige_effects` via `run_effect()` against the current player state.
2. Snapshot the current values of each stat in `carry_stats` and the skill membership for each skill in `carry_skills` from the post-pre_effects state.
3. Reset the player state to config defaults: level 1, xp 0, hp/max_hp from `game_manifest.hp_formula.base_hp`, all stats reset to their declared defaults, milestones cleared, stacks cleared, instances cleared, equipment cleared, quests cleared, known_skills cleared, cooldowns cleared, adventure history cleared, tick counters cleared.
4. Apply carry-forward: overwrite the reset stat values with the snapshotted values; overwrite known_skills with the snapshotted skill set.
5. Increment `player.prestige_count` by 1.
6. Run each effect in `prestige_config.post_prestige_effects` via `run_effect()` against the new (reset + carried) player state.
7. Set `player.prestige_pending = PrestigeCarryForward(carry_stats=..., carry_skills=...)`.

#### Scenario: pre_prestige_effects fire before carry snapshot

- **WHEN** `pre_prestige_effects` includes `{type: stat_change, stat: legacy_power, amount: 1}` and player has `legacy_power = 0` and `carry_stats: [legacy_power]`
- **THEN** after prestige, the new state has `legacy_power == 1` (pre-effect ran → legacy_power became 1 → carry captured 1)

#### Scenario: carry_stats preserve post-pre_effects values across reset

- **WHEN** `carry_stats: [legacy_power]` and player has `legacy_power = 5` (with no pre_prestige_effects changing it)
- **THEN** the reset state has `legacy_power == 5` (carried) while other stats reset to defaults

#### Scenario: Non-carried stats reset to defaults

- **WHEN** `carry_stats` does not include `cunning` and the config default for `cunning` is 0
- **THEN** after prestige, `player.stats["cunning"] == 0` regardless of previous value

#### Scenario: carry_skills preserves known_skills membership

- **WHEN** `carry_skills: [master-swordplay]` and player has `master-swordplay` in `known_skills`
- **THEN** after prestige, `master-swordplay` is in `player.known_skills`

#### Scenario: prestige_count increments by exactly 1

- **WHEN** prestige fires on a player with `prestige_count = 2`
- **THEN** after prestige, `player.prestige_count == 3`

---

### Requirement: prestige_count in template context

The template context SHALL expose `player.prestige_count` as an integer so authors can write narrative text that acknowledges repeat runs.

#### Scenario: prestige_count accessible in Jinja template

- **WHEN** an adventure step has text `"This is your {{ player.prestige_count }} prestige run."`
- **AND THEN** the player has `prestige_count == 2`
- **THEN** the rendered text is `"This is your 2 prestige run."`

---

### Requirement: prestige_count usable in conditions and unlock blocks

Content authors SHALL be able to gate adventure availability, choice options, stat checks, and other condition-carrying constructs using `prestige_count`. The condition must use `type: prestige_count` as the YAML discriminator (see condition-evaluator spec).

#### Scenario: Adventure gated on first prestige

- **WHEN** an adventure's `requires:` block is `{type: prestige_count, gte: 1}` and the player has `prestige_count == 0`
- **THEN** the adventure does not appear in available adventures for that location

#### Scenario: Adventure visible after one prestige

- **WHEN** an adventure's `requires:` block is `{type: prestige_count, gte: 1}` and the player has `prestige_count == 1`
- **THEN** the adventure appears in available adventures for that location

---

### Requirement: Testlandia validates the prestige authoring surface end-to-end

The testlandia content package SHALL include a working prestige demonstration covering:

- A stat threshold trigger at level 5 that fires a `prestige-ceremony` adventure.
- A `prestige:` block in `game.yaml` that carries `legacy_power` forward and grants +1 via `pre_prestige_effects`.
- A `prestige-ceremony.yaml` adventure containing a `type: prestige` effect step and a post-prestige narrative step.
- A prestige-gated adventure accessible only with `prestige_count >= 1`.

#### Scenario: Testlandia prestige content passes validation

- **WHEN** `oscilla content test` is run against testlandia
- **THEN** the `prestige-ceremony` adventure validates without errors and the `prestige:` block is present in the loaded game spec

#### Scenario: Testlandia prestige-gated adventure requires prestige_count >= 1

- **WHEN** the testlandia content is loaded and a location has an adventure with `requires: {type: prestige_count, gte: 1}`
- **THEN** the condition parses correctly and the adventure is present in the registry

---

### Requirement: Author documentation for prestige

`docs/authors/game-configuration.md` SHALL include a `prestige:` section documenting all fields, the execution order (pre_prestige_effects → reset → carry → increment → post_prestige_effects), and at least one complete `game.yaml` example. `docs/authors/adventures.md` SHALL document the `type: prestige` effect with a clear note that no parameters are needed on the effect itself — all configuration is in `game.yaml`.

#### Scenario: Author can configure prestige from documentation alone

- **WHEN** an author reads `docs/authors/game-configuration.md`
- **THEN** they find the `prestige:` block documented with field descriptions and a working example
