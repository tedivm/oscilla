## Context

The engine's combat step (`oscilla/engine/steps/combat.py`) hardcodes three player stat names (`strength`, `dexterity`, `hp`) and treats `EnemySpec` fields `attack`, `defense`, and `hp` as universal primitives. Any game with different stat names silently produces broken combat: player damage is calculated against a stat that evaluates to `None`, defaulting to `10`. No error is raised at load time or runtime — it just silently misbehaves.

Separately, the `EnemySpec` model carries `xp_reward: int` as a fixed field wired to a specific reward behavior. This is inconsistent with the fully author-defined design of every other engine primitive (stats, conditions, effects) and prevents games that track progression differently from granting meaningful enemy rewards.

The fix is to strip all stat assumptions from the engine. Combat resolution is delegated entirely to a `CombatSystem` manifest that each content package provides. The engine contributes the dispatch interface and the turn loop structure; it contributes no combat arithmetic of its own.

> **On the word "combat":** The manifest kind is named `CombatSystem` because the existing step is named `type: combat`, but the system has no inherent connection to physical violence. Any adversarial or contested encounter can be modeled — a courtroom trial where the player is a defense lawyer and the enemy is a prosecutor, an arm-wrestling match, a negotiation, a chess game. "Defeat" and "victory" are author-defined concepts driven by conditions on whatever stats the game declares. The engine makes no assumptions about what the stats or formulas mean.

### Current Combat Flow

```
run_combat(step, player, registry, tui)
  │
  ├── init enemy_hp from step_state or enemy.spec.hp
  │     (CombatContext.enemy_hp: int)
  │
  ├── per round:
  │   ├── show_combat_round(player_hp=player.stats["hp"], enemy_hp=ctx.enemy_hp, ...)
  │   ├── player attacks:
  │   │     strength = player.stats.get("strength", 10)
  │   │     damage = max(0, strength - enemy.spec.defense)
  │   ├── enemy attacks:
  │   │     dexterity = player.stats.get("dexterity", 10)
  │   │     mitigation = dexterity // 5
  │   │     incoming = max(0, enemy.spec.attack - mitigation)
  │   │     player.set_stat("hp", player_hp - incoming)
  │   └── _enemy_skill_phase() — periodic N-turn skill auto-fire
  │
  └── victory: run on_win branch
      defeat: run on_defeat branch
```

### Target Combat Flow

```
run_combat(step, player, registry, tui)
  │
  ├── resolve combat_system from step.combat_system ?? game.default_combat_system
  │     hard error at load time if unresolvable
  │
  ├── merge step.combat_overrides (if any) over resolved CombatSystemSpec
  │     produces an effective CombatSystemSpec used for this encounter only
  │     step.combat_overrides fields are validated at adventure load time (same
  │     rules as CombatSystemSpec — e.g. initiative formulas required if turn_order='initiative')
  │
  ├── init enemy_stats from step_state["enemy_stats"] or enemy.spec.stats
  │     (CombatContext.enemy_stats: Dict[str, int])
  ├── init combat_stats from step_state["combat_stats"]
  │     or {e.name: e.default for e in combat_system.spec.combat_stats}
  │     (CombatContext.combat_stats: Dict[str, int])
  │
  ├── if new combat (not a resume from saved state):
  │     fire each effect in on_combat_start (if any)
  │
  ├── per round:
  │   ├── show_combat_round(
  │   │     player_hud={e.target_stat: (player.stats[e.target_stat], e.display)
  │   │                 for e in player_damage_formulas if e.display},
  │   │     enemy_hud={e.target_stat: (ctx.enemy_stats[e.target_stat], e.display)
  │   │                for e in enemy_damage_formulas if e.display}, ...)
  │   │
  │   ├── if turn_order is "simultaneous":
  │   │     player phase: player_action_phase() — use_effects only; no damage formulas fire
  │   │     enemy phase:  for entry in enemy_damage_formulas: apply formula (sets enemy intent in
  │   │                   combat_stats and/or applies direct enemy-side effects)
  │   │                   enemy_action_phase()
  │   │     (no mid-round defeat check; both phases always complete)
  │   │
  │   ├── else (sequential turn order):
  │   │     resolve_turn_order() → (first_actor, second_actor):
  │   │       "player_first" (default): first=player, second=enemy
  │   │       "enemy_first":            first=enemy,  second=player
  │   │       "initiative":             render player_initiative_formula and
  │   │                                 enemy_initiative_formula in CombatFormulaContext;
  │   │                                 higher result acts first;
  │   │                                 tie resolved by initiative_tie (default "player_first")
  │   │     first actor's phase:
  │   │       player: player_action_phase() — see below
  │   │               defeat if evaluate(enemy_defeat_condition, ...)
  │   │               → if enemy defeated, skip second actor and resolution_formulas
  │   │       enemy:  for entry in enemy_damage_formulas: apply formula
  │   │               enemy_action_phase()
  │   │               defeat if evaluate(player_defeat_condition, ...)
  │   │               → if player defeated, skip second actor and resolution_formulas
  │   │     second actor's phase (only if first actor's defeat check was not satisfied):
  │   │       player: player_action_phase()
  │   │               defeat if evaluate(enemy_defeat_condition, ...)
  │   │               → if enemy defeated, skip resolution_formulas
  │   │       enemy:  for entry in enemy_damage_formulas: apply formula
  │   │               enemy_action_phase()
  │   │               defeat if evaluate(player_defeat_condition, ...)
  │   │               → if player defeated, skip resolution_formulas
  │   │
  │   ├── resolution_formulas phase (if no mid-round defeat occurred, or always in "simultaneous"):
  │   │     for entry in combat_system.spec.resolution_formulas:
  │   │       result = render_formula(entry.formula, CombatFormulaContext)
  │   │       apply result to entry.target / entry.target_stat (same routing as damage formulas)
  │   │       fire entry.threshold_effects if any
  │   │
  │   ├── defeat conditions (post-resolution):
  │   │     if evaluate(enemy_defeat_condition, ...): victory
  │   │     if evaluate(player_defeat_condition, ...): defeat
  │   │     if both satisfied simultaneously (possible in "simultaneous" mode):
  │   │       outcome determined by simultaneous_defeat_result field
  │   │       (default "player_wins"; options: "player_wins", "enemy_wins", "both_lose")
  │
  │   player_action_phase():
  │     mode = combat_system.spec.player_turn_mode
  │     "auto": for entry in combat_system.spec.player_damage_formulas
  │               + [e for item in equipped_items if contexts_match(item)
  │                    for e in item.equip.combat_damage_formulas]:
  │               damage = render_formula(entry.formula, CombatFormulaContext)
  │               stats = resolve_target(entry.target or "enemy", enemy_stats, combat_stats)
  │               stats[entry.target_stat] = max(0, stats[entry.target_stat] - damage)
  │     "choice": build action menu:
  │                 system_skills where entry.condition is None
  │                   or evaluate(entry.condition, player_state) is True
  │                 + player-owned skills whose contexts ∩ skill_contexts is non-empty
  │                 + items from inventory whose contexts ∩ skill_contexts is non-empty
  │                 + "Do Nothing" (always appended as final option)
  │               if selected is skill:
  │                 fire skill.use_effects
  │                 for entry in skill.combat_damage_formulas:
  │                   damage = render_formula(entry.formula, CombatFormulaContext)
  │                   stats = resolve_target(entry.target or "enemy", enemy_stats, combat_stats)
  │                   stats[entry.target_stat] = max(0, stats[entry.target_stat] - damage)
  │               if selected is item:
  │                 fire item.use_effects
  │                 for entry in item.combat_damage_formulas:
  │                   damage = render_formula(entry.formula, CombatFormulaContext)
  │                   stats = resolve_target(entry.target or "enemy", enemy_stats, combat_stats)
  │                   stats[entry.target_stat] = max(0, stats[entry.target_stat] - damage)
  │                 consume/decrement item (consumed_on_use / charges)
  │               if selected is "Do Nothing": no effects, no formulas — turn passes
  │   └── fire on_round_end effects (if any) — only reached if round completed without a defeat
  │
  ├── victory:
  │     fire each effect in on_combat_end (if any)
  │     fire each effect in on_combat_victory (if any)
  │     run on_defeat_effects from enemy spec, then loot, then on_win branch
  └── defeat:
        fire each effect in on_combat_end (if any)
        fire each effect in on_combat_defeat (if any)
        run on_defeat branch
```

## Goals / Non-Goals

**Goals:**

- Remove all hardcoded stat names (`strength`, `dexterity`, `hp`) from the engine combat layer
- Replace fixed `EnemySpec` fields with `stats: Dict[str, int]` and `on_defeat_effects: List[Effect]`
- Introduce `CombatSystem` as a manifest kind; engine dispatches to it with no combat logic of its own
- Support multiple `CombatSystem` manifests per game; per-step override via `CombatStep.combat_system`
- Auto-promote single registered system to default; hard error at load time if no system resolves
- Replace `player_vitals`/`enemy_vitals` defeat checks with `player_defeat_condition` and `enemy_defeat_condition` — both are full `Condition` trees evaluated each round; this allows the condition system (stat checks, milestone checks, `all`/`any`/`not`) to define any arbitrary defeat rule
- Introduce an `enemy_stat` condition leaf that evaluates against `enemy_stats: Dict[str, int]` during combat; extends `evaluate()` with an optional `enemy_stats` parameter and is invalid outside combat context
- Support multiple damage formulas per turn (`player_damage_formulas`, `enemy_damage_formulas` as ordered lists); each entry targets one stat; all formulas apply before the defeat condition is evaluated
- `DamageFormulaEntry` gains an optional `display: str | None` field; stats with a display label are shown in the combat HUD
- Validate at load time that every enemy carries all stat names referenced in the damage formulas of its resolved `CombatSystem`; missing stats are a hard load-time error
- Persist full `enemy_stats` dict in `step_state` for save/resume across rounds
- Fix `stat_change target='enemy'` to use the named `stat` field against `enemy_stats`
- Deprecate `heal target='enemy'` with a load-time warning
- Extract `enemy_action_phase()` as the single enemy-turn dispatch hook for future Decision Tree AI
- Extract `player_action_phase()` as the player-turn dispatch hook; supports `"auto"` and `"choice"` turn modes
- Support `player_turn_mode: "choice"` on `CombatSystem` — player selects a combat skill each round; no auto-attack fires
- Add `combat_damage_formulas: List[DamageFormulaEntry]` to `SkillSpec` — per-skill damage formulas rendered in `CombatFormulaContext` when the skill is used as a move in `"choice"` mode; a single skill can target multiple enemy vitals in one turn
- Add `turn_order: "player_first" | "enemy_first" | "initiative" | "simultaneous"` to `CombatSystemSpec` — controls which side acts first each round; defaults to `"player_first"` (preserves current behavior); `"simultaneous"` causes both phases to always complete with no mid-round defeat check — defeat is evaluated only after all phases and `resolution_formulas` have executed; mutual defeat is possible and its outcome is governed by `simultaneous_defeat_result`
- When `turn_order` is `"initiative"`: two formula fields `player_initiative_formula` and `enemy_initiative_formula` (rendered in `CombatFormulaContext`, must return `int`) determine the acting order each round — higher value acts first; an `initiative_tie: "player_first" | "enemy_first"` field (default `"player_first"`) resolves equal rolls
- Add `simultaneous_defeat_result: "player_wins" | "enemy_wins" | "both_lose"` to `CombatSystemSpec` (default `"player_wins"`) — governs the outcome when both defeat conditions are satisfied simultaneously; only meaningful when `turn_order` is `"simultaneous"` (in sequential modes a mid-round short-circuit makes mutual defeat impossible)
- Defeat check after the first actor's phase short-circuits the round (in sequential modes) — if the first actor wins, the second actor's phase and `resolution_formulas` do not execute
- Add `resolution_formulas: List[DamageFormulaEntry]` to `CombatSystemSpec` — an optional ordered list of damage formulas that fire once per round after all actor phases have completed, before defeat conditions are evaluated; fires in all `turn_order` modes; in sequential modes fires only if no mid-round defeat occurred; uses the same `DamageFormulaEntry` shape as `player_damage_formulas` / `enemy_damage_formulas` including `target`, `target_stat`, `display`, and `threshold_effects`; the formula renders in `CombatFormulaContext` with full visibility into the final committed state of both `enemy_stats` and `combat_stats`; entries are applied in order and each entry's result is visible to subsequent entries via updated `combat_stats`; useful for simultaneous-resolution mechanics where both sides commit intent first (RPS, card games), end-of-round area effects, or any calculation that requires seeing both sides' complete state before applying results; an empty list is the default (no-op)
- Relax `SkillSpec.contexts` from a fixed enum (`"combat"`, `"overworld"`) to arbitrary strings; each `CombatSystem` declares `skill_contexts: List[str]` — a skill is eligible in a combat system when its `contexts` list intersects with the system's `skill_contexts`; `"overworld"` remains a built-in context reserved for the overworld phase
- Add `ItemSpec.contexts: List[str]` — items that declare combat contexts can be used as combat actions in `"choice"` mode; an item is eligible when its `contexts` intersects the active `CombatSystem.skill_contexts`; existing `consumed_on_use`/`charges` mechanics apply when the item is used
- Add `ItemSpec.combat_damage_formulas: List[DamageFormulaEntry]` — damage formulas applied when an item is used as a combat action; follows the same `CombatFormulaContext` as skill formulas; a combat item without formulas is a pure-effect action (e.g., a combat healing potion)
- Add `EquipSpec.combat_damage_formulas: List[DamageFormulaEntry]` — formulas automatically applied to the player's attack each round while the item is equipped; the parent item's `contexts` field scopes which combat systems these fire in; allows weapons to passively contribute damage without consuming a choice-mode action
- Expose `combat.enemy_stats` (dict) and `turn_number` in template context; remove `combat.enemy_hp`
- Add `on_combat_start: List[Effect]`, `on_combat_end: List[Effect]`, `on_combat_victory: List[Effect]`, and `on_combat_defeat: List[Effect]` lifecycle hooks to `CombatSystemSpec` — `on_combat_start` fires once when a new combat begins (not on resume from saved state); `on_combat_end` fires once when combat resolves regardless of outcome, before outcome-specific hooks; `on_combat_victory` fires after `on_combat_end` on a player win, before `on_defeat_effects` / loot / branch dispatch; `on_combat_defeat` fires after `on_combat_end` on a player loss, before branch dispatch; all default to empty
- Add `combat_stats: List[CombatStatEntry]` to `CombatSystemSpec` — ephemeral integer stats scoped to the combat instance; initialized from declared defaults when a new combat begins (not on resume from saved state); persisted in `step_state["combat_stats"]` for mid-combat save/resume; discarded at combat end and never written to the player's global stat store; accessible in all formula expressions as `combat_stats['name']` and mutable via `stat_change target='combat'` / `stat_set target='combat'` effects; a new `combat_stat` condition leaf (`CombatStatCondition`) allows defeat conditions and `system_skills` conditions to check these values; `DamageFormulaEntry` gains an optional `target: Literal["player", "enemy", "combat"] | None` field to route formula damage to the appropriate stat namespace (defaults to `"enemy"` for player/skill formulas and `"player"` for enemy formulas when `None`)
- Add `on_round_end: List[Effect]` to `CombatSystemSpec` — fires at the end of each complete round after all actors have acted and defeat conditions have been evaluated, but only if no defeat occurred that round; useful for incrementing round counters, clearing per-round tracking values, or applying persistent per-round effects (e.g. regen); defaults to empty
- Add `system_skills: List[SystemSkillEntry]` to `CombatSystemSpec` — each entry names a skill ref available in the choice-mode action menu for this combat system regardless of whether the player has acquired it; an optional player-state `condition` gates visibility per round — a skill whose condition evaluates to `False` is silently hidden that round; useful for context-specific built-in moves (e.g. "Push Harder"/"Hold Steady" in arm wrestling, "Object!"/"Present Evidence" in a courtroom) and for conditional fallbacks (e.g. hide "Unarmed Strike" when the player is carrying a weapon)
- Guarantee a "Do Nothing" option is always present in the choice-mode action menu; this prevents a player from becoming permanently stuck if their skill list and inventory produce no eligible actions for the active combat system
- Migrate testlandia content to the new schema; provide reference `CombatSystem` manifest
- Add `rollpool(n, sides, threshold) -> int` to `SAFE_GLOBALS` — roll `n` dice of `sides` sides and return the count of dice whose result is ≥ `threshold`; enables dice-pool mechanics (Blades in the Dark, World of Darkness, Shadowrun, Exalted) with no schema changes
- Add `rollsum(n, sides) -> int` to `SAFE_GLOBALS` — roll `n` dice of `sides` sides and return their sum; equivalent to the XdY notation (e.g. `rollsum(3, 6)` = 3d6); complements `rollpool` (which counts successes) for sum-based damage mechanics
- Add `keephigh(n, sides, k) -> int` to `SAFE_GLOBALS` — roll `n` dice of `sides` sides (all same size) and return the sum of the highest `k`; enables "roll and drop lowest" mechanics (e.g. `keephigh(4, 6, 3)` = D&D 5e ability score generation; `keephigh(3, 6, 2)` = sum of two highest of three d6); `k` must be ≤ `n`, otherwise `ValueError`
- Add `clamp(x, lo, hi) -> int` to `SAFE_GLOBALS` — return `x` clamped to [lo, hi] inclusive; equivalent to `max(lo, min(hi, x))` but more readable; useful for bounded counters like the 13th Age escalation die cap (`clamp(combat_stats['escalation'], 0, 6)`)
- Allow multi-statement formula strings using Jinja2 `{% set %}` declarations — a formula string may contain one or more `{% set name = expression %}` blocks before the final `{{ result }}` output expression; intermediate values assigned via `{% set %}` are scoped to the single formula evaluation and are accessible in subsequent expressions within the same string; this solves the double-roll correctness problem (bind the roll once, reference it multiple times), enables multi-step intermediate calculations, and generalizes to any value that needs to be computed once and used in several places within a formula; `{% set %}` blocks are validated and mock-rendered at load time alongside the formula's output expression
- Add `threshold_effects: List[ThresholdEffectBand]` to `DamageFormulaEntry` — after applying formula damage, fire the first matching band's `effects` list; `ThresholdEffectBand` has inclusive `min`/`max` bounds and any player-context `Effect` list; enables tiered outcomes (PbtA 7–9 / miss / full success patterns) layered on top of the existing formula model
- Allow `DamageFormulaEntry.target_stat` to be `None` (YAML `null`) — when `null`, the formula's integer result is not applied as damage to any stat; only `threshold_effects` fire; this "threshold-only" mode enables systems where the formula roll selects an outcome tier rather than dealing a damage amount (e.g. PbtA move rolls determine which tier fires; the actual stat changes live entirely in the tier's `effects` list); a formula with `target_stat: null` and no `threshold_effects` is a hard load error (it would do nothing)
- Allow `stat_change.value` inside `threshold_effects` bands to accept either an `int` or a Jinja2 formula string — when a string, it is rendered in the same `CombatFormulaContext` as the parent formula and must evaluate to an `int`; validated and mock-rendered at load time; enables tier-specific computed magnitudes (e.g. a PbtA 7–9 band that deals `roll(player.stats['damage_die'])` damage); string values are only valid inside `threshold_effects` bands and are a hard load error if used outside that context

**Non-Goals:**

- Decision Tree AI for enemies — the `enemy_action_phase()` hook is forward-shaped here, but AI logic ships separately
- Enemy derived stats (formula-based enemy stats) — `stats: Dict[str, int]` shape does not block this but the feature is deferred
- `HealEffect` player path — unchanged and out of scope
- Custom Effects — `heal target='enemy'` deprecation warning points toward Custom Effects when they ship; that feature is out of scope here
- Any database schema migration — `adventure_step_state` is already `JSON`/`Any`
- Multi-sub-phase turns (action + bonus action + reaction) — the model is single-action-per-phase; action economy systems such as D&D 5e require a structural change to the turn model
- Truly sealed simultaneous input — `turn_order: "simultaneous"` guarantees correct ordering (player commits intent via `use_effects` before enemy formula runs, both committed before `resolution_formulas` resolve), but the player's choice is not hidden from the player; a cryptographically sealed reveal phase is out of scope
- Provenance-aware dice — formula expressions return a scalar integer; tracking which dice in a pool were special-category dice (e.g. Vampire Hunger dice) requires non-scalar return types, which are out of scope

## Decisions

### CombatSystem Manifest Structure

The `CombatSystem` manifest declares the minimum engine needs to execute a combat step. The helper types used throughout the schema:

```python
class ThresholdEffectBand(BaseModel):
    min: int | None = None   # inclusive lower bound on the formula result; None = no lower bound
    max: int | None = None   # inclusive upper bound on the formula result; None = no upper bound
    effects: List[Effect]    # effects fired when the result falls within this band
                             # Inside threshold_effects bands only: stat_change.value may be a
                             # Jinja2 formula string rendered in CombatFormulaContext (e.g.
                             # value: "{{ roll(player.stats['damage_die']) }}"); validated at load time


class DamageFormulaEntry(BaseModel):
    target_stat: str | None    # stat this formula's result is subtracted from;
                               # None = "threshold-only": formula fires threshold_effects but
                               # applies no raw integer damage; hard error if None and threshold_effects is empty
    target: Literal["player", "enemy", "combat"] | None = None
    # None = auto: player/skill formulas default to "enemy"; enemy formulas default to "player"
    formula: str           # int-returning Jinja2 template expression
    display: str | None = None  # if set, shown in combat HUD with this label
    threshold_effects: List[ThresholdEffectBand] = []  # optional side-effects fired based on roll result


class CombatStatEntry(BaseModel):
    name: str       # identifier; accessible in all formula contexts as combat_stats['name']
    default: int = 0  # value assigned at the start of a new combat; preserved across save/resume


class SystemSkillEntry(BaseModel):
    skill: str                          # ref to a loaded Skill manifest
    condition: Condition | None = None  # if set, skill is only shown when condition passes
```

`SystemSkillEntry.condition` is evaluated against **player state** at the start of each choice-mode round (same evaluation path as all other player-state conditions). Skills whose condition evaluates to `False` are silently omitted from the menu that round — the player never sees them. This lets authors gate system skills on player inventory, stats, or quest state (e.g. hide "Unarmed Strike" when the player is carrying a weapon).

`CombatStatEntry` declares a **combat-internal stat** — an ephemeral integer initialized at combat start and discarded when combat ends. It is never written to the player's global stat store. Combat-internal stats live in `step_state["combat_stats"]` alongside `step_state["enemy_stats"]` so they survive a save/resume mid-combat. Authors use them for tracking that is meaningful only within a single encounter (e.g. lives in a lives-based mini-game, a round counter, a per-round throw encoding). The `combat_stats` dict is available in `CombatFormulaContext` and may be mutated via `stat_change target='combat'` or `stat_set target='combat'` effects anywhere that player-state effects are valid during combat.

`ThresholdEffectBand` enables **tiered outcomes** on a formula entry. After the formula result is applied as damage, the engine walks `threshold_effects` in declaration order and fires the first band whose `[min, max]` range contains the result. If no band matches, no side effects fire. Both `min` and `max` are inclusive and optional — omitting `min` means “any result up to `max`”; omitting `max` means “any result at or above `min`”; omitting both means “always fires” (catch-all fallback). Any `Effect` type valid in a player-state context is allowed in a band’s `effects` list, as well as `stat_change target='enemy'` and `stat_set target='enemy'` — unlike lifecycle hooks, `threshold_effects` bands fire during the round when the full combat context (including `enemy_stats`) is in scope.

The template engine’s `rollpool(n, sides, threshold)` global function (see below) extends formula expressiveness to dice-pool mechanics.

Victory and defeat are driven by the existing **condition system**. A new condition leaf, `enemy_stat`, is added to the `Condition` union:

```python
class EnemyStatCondition(BaseModel):
    type: Literal["enemy_stat"]
    name: str            # key in enemy_stats dict (mirrors CharacterStatCondition.name)
    # at least one comparator required (same rules as CharacterStatCondition)
    gte: int | None = None
    lte: int | None = None
    gt:  int | None = None
    lt:  int | None = None
    eq:  int | None = None
```

`evaluate()` gains an optional `enemy_stats: Dict[str, int] | None = None` parameter. `EnemyStatCondition` is only meaningful inside a combat call; outside that context it evaluates to `False` and logs a warning. Because `EnemyStatCondition` joins the main `Condition` union, the full logical combinators (`all`, `any`, `not`) and every other condition leaf compose freely with it.

A parallel `CombatStatCondition` checks `combat_stats`:

```python
class CombatStatCondition(BaseModel):
    type: Literal["combat_stat"]
    name: str            # key in the combat_stats dict
    gte: int | None = None
    lte: int | None = None
    gt:  int | None = None
    lt:  int | None = None
    eq:  int | None = None
```

`CombatStatCondition` is valid wherever combat context is available: `player_defeat_condition`, `enemy_defeat_condition`, and `system_skills` conditions (evaluated at round start when `combat_stats` are in scope). Outside combat it evaluates to `False` and logs a warning. `evaluate()` gains an optional `combat_stats: Dict[str, int] | None = None` parameter alongside `enemy_stats`.

A `CombatSystemSpec` with either `player_defeat_condition` or `enemy_defeat_condition` absent is a hard load-time error.

The `player_defeat_condition` is evaluated against **player state** (no enemy stats needed; standard condition path). The `enemy_defeat_condition` typically uses `enemy_stat` leaves and is evaluated with the current `enemy_stats` dict.

```yaml
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: standard-combat
spec:
  # Defeat conditions — evaluated after each side's damage formulas apply.
  # player_defeat_condition: standard Condition evaluated against player state.
  # enemy_defeat_condition: Condition that may use enemy_stat leaves.
  player_defeat_condition:
    type: character_stat
    name: hp
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    name: hp
    lte: 0

  # Damage formula lists — each entry targets one stat.
  # display: if set, this stat is shown in the combat HUD with the given label.
  # Available context: player (PlayerContext, effective stats),
  #                    enemy_stats (Dict[str, int]), combat_stats (Dict[str, int]), turn_number (int)
  # player_damage_formulas required when player_turn_mode is "auto".
  player_damage_formulas:
    - target_stat: hp
      display: "HP"
      formula: "{{ max(0, player.stats['strength'] - enemy_stats['defense']) }}"
  enemy_damage_formulas:
    - target_stat: hp
      display: "HP"
      formula: "{{ max(0, enemy_stats['attack'] - player.stats['dexterity'] // 5) }}"

  # Player turn mode:
  #   "auto"   (default) — player_damage_formulas fire each round automatically.
  #   "choice" — player selects a combat skill each round; player_damage_formulas must be absent.
  player_turn_mode: "auto"

  # Turn order: who acts first each round.
  #   "player_first" (default) — player always acts first.
  #   "enemy_first"            — enemy always acts first.
  #   "initiative"             — both sides roll initiative formulas each round;
  #                              higher result acts first. Requires player_initiative_formula
  #                              and enemy_initiative_formula.
  #   "simultaneous"           — both actor phases always complete (no mid-round defeat check);
  #                              player phase fires use_effects only (no damage formulas);
  #                              defeat checked after all phases and resolution_formulas complete.
  turn_order: "player_first"

  # simultaneous_defeat_result: used when turn_order is "simultaneous" and both defeat conditions
  # are satisfied in the same round. Options: "player_wins" (default), "enemy_wins", "both_lose".
  # simultaneous_defeat_result: "player_wins"

  # Resolution formulas — fire after all actor phases, before defeat conditions are checked.
  # In sequential modes: only fires if no mid-round defeat occurred.
  # In "simultaneous" mode: always fires (actor phases never short-circuit).
  # Useful for comparing both sides' committed combat_stats (e.g. RPS throw, card draw).
  # Same DamageFormulaEntry shape as player_damage_formulas / enemy_damage_formulas.
  # Entries applied in order; earlier entries update combat_stats visible to later entries.
  # resolution_formulas: []

  # initiative_tie: used when turn_order is "initiative" and both sides roll equal values.
  # Defaults to "player_first". Options: "player_first", "enemy_first", "random" (coin flip).
  # initiative_tie: "player_first"

  # Initiative formulas — required when turn_order is "initiative"; forbidden otherwise.
  # Rendered in CombatFormulaContext (player, enemy_stats, turn_number). Must return int.
  # player_initiative_formula: "{{ player.stats['initiative'] }}"
  # enemy_initiative_formula: "{{ enemy_stats['initiative'] }}"

  # Lifecycle hooks — effect lists that fire once per combat, not per round.
  # on_combat_start:   fires when a new combat begins (not on resume from saved state).
  # on_combat_end:     fires when combat resolves (victory or defeat), before outcome-specific hooks.
  # on_combat_victory: fires after on_combat_end on a player win, before on_defeat_effects/loot.
  # on_combat_defeat:  fires after on_combat_end on a player loss, before branch dispatch.
  # All default to empty. Any Effect type is valid; enemy_stats is not in scope here.
  # stat_change/stat_set with target: "combat" is valid and mutates combat_stats.
  # on_combat_start:   []
  # on_combat_end:     []
  # on_combat_victory: []
  # on_combat_defeat:  []

  # Round-end hook — fires at the end of each complete round if no defeat occurred.
  # Useful for round counters, persistent per-round effects (regen), or clearing
  # per-round tracking values stored in combat_stats.
  # on_round_end: []

  # Combat-internal stats — ephemeral; initialized at new combat start; discarded at end.
  # Declared stats are available as combat_stats['name'] in all formula contexts.
  # Damage formulas that target these stats use target: "combat" on DamageFormulaEntry.
  # Never written to global player stats — safe for anything that should not persist.
  # combat_stats: []

  # Skill context strings — a skill is available in this combat system when at
  # least one of its contexts appears in this list. Defaults to ["combat"] if omitted.
  skill_contexts:
    - combat

  # System skills — skills available in the choice-mode menu for this combat
  # system regardless of whether the player has acquired them. Each entry names
  # a skill ref and an optional condition evaluated against player state each
  # round. Skills whose condition evaluates to false are hidden that round.
  # Omit or leave empty for a standard inventory-only skill menu.
  # system_skills:
  #   - skill: push-harder
  #   - skill: unarmed-strike
  #     condition:
  #       type: not
  #       condition:
  #         type: has_item
  #         item: any-weapon
```

> **"Do Nothing" is always present in `"choice"` mode.** The engine appends a "Do Nothing" option as the final entry in every choice-mode combat menu. Selecting it passes the player's turn without firing any effects or formulas. This prevents a player from becoming permanently stuck when no skills or items are eligible for the active combat system — for example, a player who has not acquired any `arm-wrestling` context skills facing an arm-wrestling encounter still has a legal action each round. `system_skills` reduces the likelihood of that empty-menu scenario, but "Do Nothing" is the unconditional safety valve.

Formula templates are compiled and mock-rendered at load time (same validation path as all other template expressions). A formula that references a stat not declared in `character_config.yaml` or `enemy.spec.stats` is caught as a load-time validation error.

### Formula Template Globals

All combat formula expressions are rendered in the sandboxed Jinja2 environment. Beyond the standard arithmetic and comparison operators, the following global functions are available:

| Function   | Signature                         | Description                                                                                                                                                                                                      |
| ---------- | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `roll`     | `roll(sides)` or `roll(min, max)` | Roll one die with the given number of sides, or return a random integer in [min, max] inclusive. Each call is independent.                                                                                       |
| `rollpool` | `rollpool(n, sides, threshold)`   | Roll `n` dice of `sides` sides; return the count of dice whose result is ≥ `threshold`. Enables dice-pool mechanics (Blades in the Dark, World of Darkness, Shadowrun).                                          |
| `rollsum`  | `rollsum(n, sides)`               | Roll `n` dice of `sides` sides; return their sum. Equivalent to the XdY notation (e.g. `rollsum(3, 6)` = 3d6).                                                                                                   |
| `keephigh` | `keephigh(n, sides, k)`           | Roll `n` dice of `sides` sides (all uniform); return the sum of the highest `k`. E.g. `keephigh(4, 6, 3)` = D&D ability score generation; `keephigh(3, 8, 2)` = sum of two highest d8s. `ValueError` if `k > n`. |
| `clamp`    | `clamp(x, lo, hi)`                | Return `x` clamped to [lo, hi] inclusive. Equivalent to `max(lo, min(hi, x))` but readable. Useful for bounded counters (e.g. escalation die capped at 6).                                                       |
| `max`      | `max(a, b)`                       | Return the larger of two values.                                                                                                                                                                                 |
| `min`      | `min(a, b)`                       | Return the smaller of two values.                                                                                                                                                                                |
| `abs`      | `abs(x)`                          | Absolute value.                                                                                                                                                                                                  |

`rollpool` example — a Blades-in-the-Dark-style pool where successes are dice showing 4 or higher:

```
rollpool(player.stats['action_rating'], 6, 4)
```

Returns 0–N successes. A result of 0 is a miss; 1–2 is a partial success (pair with `threshold_effects` to fire a complication effect); 3+ is a full success. Because `rollpool` returns an integer, it composes directly with `threshold_effects` bands:

```yaml
- target_stat: hp
  formula: "{{ rollpool(player.stats['action_rating'], 6, 4) }}"
  threshold_effects:
    - max: 0 # miss — enemy retaliates harder
      effects:
        - type: stat_change
          stat: momentum
          target: combat
          value: -1
    - min: 1
      max: 2 # partial — player takes stress alongside dealing damage
      effects:
        - type: stat_change
          stat: stress
          value: 1
```

All formula globals follow the existing `SAFE_GLOBALS` conventions: pure Python, sandboxed, `ValueError` on invalid input, precompile-and-mock-rendered at load time.

To illustrate that the engine is fully agnostic to combat semantics, the following examples each use a different `CombatSystem` manifest with no engine changes required.

### Example Manifests

#### Turn-Based Stat-vs-Stat Combat

The classic RPG model:

```yaml
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: standard-combat
spec:
  player_defeat_condition:
    type: character_stat
    name: hp
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    name: hp
    lte: 0
  player_damage_formulas:
    - target_stat: hp
      display: "HP"
      formula: "{{ max(0, player.stats['strength'] - enemy_stats['defense']) }}"
  enemy_damage_formulas:
    - target_stat: hp
      display: "HP"
      formula: "{{ max(0, enemy_stats['attack'] - player.stats['dexterity'] // 5) }}"
```

#### Card-Draw Resolution

Both sides draw from a hand stat; the higher draw wins the round. Each side commits a random draw
to `combat_stats` during their action phase; `resolution_formulas` compare the two committed values
and discard a card from the loser. Delta-encode pattern: to set a `combat_stat` to value `V`, emit
`current - V` so that `stat = max(0, current - (current - V)) = V`.

```yaml
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: card-draw-combat
spec:
  player_defeat_condition:
    type: character_stat
    name: hand_size
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    name: hand_size
    lte: 0
  # Player action phase: commit a random draw to combat_stats['player_draw'].
  # Delta-encode: (current - new) so stat ends up at new after subtraction.
  # target: combat means this formula writes to combat_stats, not enemy_stats.
  # The mid-round defeat check cannot trigger here — hand_size is unchanged.
  player_damage_formulas:
    - target_stat: player_draw
      target: combat
      formula: "{{ combat_stats['player_draw'] - roll(1, player.stats['hand_size']) }}"
  # Enemy action phase: commit a random draw to combat_stats['enemy_draw'].
  enemy_damage_formulas:
    - target_stat: enemy_draw
      target: combat
      formula: "{{ combat_stats['enemy_draw'] - roll(1, enemy_stats['hand_size']) }}"
  # After both draws are committed, compare and discard a card from the loser.
  # Ties: enemy discards (player-favored).
  resolution_formulas:
    - target_stat: hand_size
      target: enemy
      display: "Enemy Cards"
      formula: "{{ 1 if combat_stats['player_draw'] >= combat_stats['enemy_draw'] else 0 }}"
    - target_stat: hand_size
      target: player
      display: "Your Cards"
      formula: "{{ 1 if combat_stats['enemy_draw'] > combat_stats['player_draw'] else 0 }}"
  # Combat-internal draw accumulators — reset each round via delta-encode in the formulas above.
  combat_stats:
    - name: player_draw
      default: 0
    - name: enemy_draw
      default: 0
```

#### Elemental Weapon Affinity

A fire dagger deals bonus damage against an ice enemy. Because `CombatFormulaContext` uses effective stats (including equipment `stat_modifiers`), a weapon's elemental properties surface naturally in damage formulas. The enemy's vulnerability is an author-defined stat on the enemy manifest.

```yaml
# character_config.yaml — declare fire_bonus with a default of 0
stats:
  - name: strength
    type: int
    default: 10
  - name: fire_bonus # 0 when no fire weapon is equipped; raised by item stat_modifiers
    type: int
    default: 0
```

```yaml
# Item: Dagger of Fire
apiVersion: oscilla/v1
kind: Item
metadata:
  name: dagger-of-fire
spec:
  displayName: "Dagger of Fire"
  category: weapon
  equip:
    slots: [main_hand]
    stat_modifiers:
      - stat: fire_bonus
        amount: 10 # player.stats['fire_bonus'] == 10 while this is equipped
```

```yaml
# Enemy: Ice Golem — declares fire_vulnerability as an enemy stat
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: ice-golem
spec:
  displayName: "Ice Golem"
  stats:
    hp: 80
    defense: 5
    fire_vulnerability: 50 # percentage bonus damage from fire
```

```yaml
# CombatSystem: reads player.stats['fire_bonus'] (effective) and enemy_stats['fire_vulnerability']
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: elemental-combat
spec:
  player_defeat_condition:
    type: character_stat
    name: hp
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    name: hp
    lte: 0
  player_damage_formulas:
    - target_stat: hp
      display: "HP"
      # Base damage: strength minus enemy defense.
      # Elemental bonus: fire_bonus * fire_vulnerability% added on top.
      # Against an Ice Golem (fire_vulnerability=50) with the Dagger of Fire equipped:
      #   base = max(0, 10 - 5) = 5
      #   bonus = 10 * 50 // 100 = 5
      #   total = 10 damage (vs 5 without the fire weapon)
      # Against an enemy with no fire_vulnerability stat, .get() returns 0 — no bonus.
      formula: "{{ max(0, player.stats['strength'] - enemy_stats['defense'] + player.stats['fire_bonus'] * enemy_stats.get('fire_vulnerability', 0) // 100) }}"
  enemy_damage_formulas:
    - target_stat: hp
      display: "HP"
      formula: "{{ max(0, enemy_stats['attack'] - player.stats['dexterity'] // 5) }}"
```

The load-time validator confirms that every enemy in this game carries the stats referenced by the formula (`defense` is required; `fire_vulnerability` is accessed via `.get()` and therefore optional). A non-fire enemy simply omits `fire_vulnerability` from its stats dict and takes no elemental bonus.

#### Move-Selection Combat

Pokémon-style — the player picks a move each round:

```yaml
# CombatSystem: no player_damage_formulas; player turn mode is "choice"
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: move-select-combat
spec:
  player_defeat_condition:
    type: character_stat
    name: hp
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    name: hp
    lte: 0
  player_turn_mode: "choice" # no player_damage_formulas; skills provide per-move formulas
  enemy_damage_formulas:
    - target_stat: "hp"
      display: "HP"
      formula: "{{ max(0, enemy_stats['attack'] - player.stats['defense']) }}"
```

```yaml
# Skill: Tackle — a basic physical move, damage only
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: tackle
spec:
  displayName: "Tackle"
  contexts: ["combat"]
  # combat_damage_formulas renders in CombatFormulaContext; each entry applied to its target_stat.
  combat_damage_formulas:
    - target_stat: "hp"
      formula: "{{ max(1, player.stats['strength'] * 2 - enemy_stats['defense']) }}"

---
# Skill: Ember — deals fire damage AND applies a burn debuff to the enemy.
# use_effects fire first, then combat_damage_formulas apply damage.
# The burn debuff can deal per-turn stat_change damage via the buff's per_turn_effects.
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: ember
spec:
  displayName: "Ember"
  contexts: ["combat"]
  cost:
    stat: pp
    amount: 5
  use_effects:
    - type: apply_buff
      buff_ref: burn
      target: enemy # debuff the enemy — burn deals periodic fire damage each turn
  combat_damage_formulas:
    - target_stat: "hp"
      formula: "{{ max(1, player.stats['sp_attack'] * 3 - enemy_stats['sp_defense']) }}"

---
# Skill: Recover — pure-effect move, no damage contribution.
# Heals the player and applies a defense buff for 2 turns.
# A skill with no combat_damage_formulas is a valid choice-mode action.
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: recover
spec:
  displayName: "Recover"
  contexts: ["combat"]
  cost:
    stat: pp
    amount: 3
  use_effects:
    - type: heal
      amount: 20 # restore 20 HP
    - type: apply_buff
      buff_ref: iron-defense
      target: player # player gains +defense modifier for 2 turns
  # No combat_damage_formulas — this move deals zero damage by design.
```

In `"choice"` mode the combat menu presents combat-context skills **and** combat-context items from the player's inventory — no "Attack" option. A `skill.use_effects` list still fires alongside `combat_damage_formulas` — a skill can both deal damage and apply a buff in the same turn. A skill without `combat_damage_formulas` is a pure-effect move (e.g., a heal or a buff application) with no direct damage contribution. Items follow the same pattern: `use_effects` fire first, then `combat_damage_formulas`, then the item is consumed/decremented. In auto mode, equipped items with `equip.combat_damage_formulas` matching the active combat system's `skill_contexts` contribute their formulas to the player's attack phase automatically, after the system's `player_damage_formulas`.

**Load-time validation:**

- Every `CombatSystem` must declare both `player_defeat_condition` and `enemy_defeat_condition` — a hard load error if either is absent
- Each `enemy_stat` condition leaf must reference a stat present in every enemy registered for that `CombatSystem`; missing stats are a hard load error
- In `"choice"` mode: `player_damage_formulas` must be absent/empty — a hard load error if both `player_turn_mode: "choice"` and `player_damage_formulas` are present
- In `"choice"` mode: the engine always guarantees a "Do Nothing" option, so an empty skill/item menu is not an error; the load-time check for at least one eligible skill or item is removed
- `on_combat_start`, `on_combat_end`, `on_combat_victory`, `on_combat_defeat`, and `on_round_end` accept any `Effect` type that is valid in a player-state context; effects that require enemy context (e.g. `stat_change target='enemy'`) are a hard load error in these hooks; `stat_change target='combat'` and `stat_set target='combat'` are valid in all lifecycle hooks including `on_round_end` — they mutate `combat_stats`
- `combat_stats` names within a single `CombatSystemSpec` must be unique (hard load error); `DamageFormulaEntry.target` may be `"player"`, `"enemy"`, or `"combat"` — unknown values are a hard load error; `target: "combat"` in a formula entry requires that `target_stat` names a stat declared in `combat_stats` (hard load error if missing); `combat_stat` condition leaves in defeat conditions must reference a stat declared in `combat_stats` (hard load error if missing)
- Each `SystemSkillEntry.skill` ref must resolve to a loaded `Skill` manifest — a hard load error for an unknown ref
- Each `SystemSkillEntry.condition`, when present, must be a valid player-state `Condition`; `combat_stat` leaves are permitted in `system_skills` conditions (they are in scope during combat rounds); `enemy_stat` leaves inside a `system_skills` condition are a hard load error (those leaves are only valid inside defeat-condition context)
- `combat_damage_formulas` on `system_skills` skill refs are compiled and mock-rendered at load time the same way player-skill `combat_damage_formulas` are
- A skill with non-empty `combat_damage_formulas` must declare at least one context that appears in some registered `CombatSystem.skill_contexts` or in a `CombatSystem.system_skills` entry; if no registered system can ever invoke its formulas, that is a hard load error
- An item with non-empty `ItemSpec.combat_damage_formulas` must have non-empty `contexts` — a hard load error otherwise (unreachable formulas)
- An item with non-empty `EquipSpec.combat_damage_formulas` must have non-empty `ItemSpec.contexts` — scoping requires at least one declared context; a hard load error otherwise
- Each skill's and item's `combat_damage_formulas` entries are compiled and mock-rendered at load time (same path as all other formula templates)
- `threshold_effects` bands are validated at load time: at least one of `min` or `max` must be set unless the band is the only entry in the list (a single-band entry with neither bound is a catch-all and is valid); all effects within a band must be valid player-state effects; `stat_change target='enemy'` and `stat_set target='enemy'` are permitted inside `threshold_effects` bands (full combat context including `enemy_stats` is in scope when bands fire); a `threshold_effects` list with more than one unbounded catch-all band (neither `min` nor `max`) is a hard load error (only the first such band would ever fire)

#### Combat Items

Items participate in combat in two orthogonal ways. A throwable grenade is a consumable active-use item in choice mode — selecting it from the menu fires its formulas and decrements the stack. A sword contributes passive equip formulas automatically every round in auto mode, without consuming a turn.

```yaml
# Grenade — throwable, stackable, consumed on use; deals massive flat damage and ignites the enemy.
# Appears in the choice-mode combat menu for any combat system whose skill_contexts
# includes "combat". No equip spec: it is used, not worn.
apiVersion: oscilla/v1
kind: Item
metadata:
  name: frag-grenade
spec:
  displayName: "Frag Grenade"
  description: "Pull the pin and throw. Single use."
  category: throwable
  contexts: ["combat"]
  stackable: true
  consumed_on_use: true
  # use_effects fire first, then combat_damage_formulas apply damage.
  # Here the grenade both debuffs the enemy (burn) and deals immediate damage.
  use_effects:
    - type: apply_buff
      buff_ref: burn
      target: enemy # enemy catches fire — per-turn burn damage via buff's per_turn_effects
  combat_damage_formulas:
    - target_stat: hp
      display: "HP"
      # Flat 40 damage, unmitigated — grenades bypass defense entirely.
      formula: "{{ 40 }}"
```

```yaml
# Iron Sword — equippable, non-stackable. Contributes a passive damage formula
# every round in auto mode for any combat system whose skill_contexts includes "combat".
# The player does not spend a choice-mode action to "use" it — it simply fires.
apiVersion: oscilla/v1
kind: Item
metadata:
  name: iron-sword
spec:
  displayName: "Iron Sword"
  description: "A reliable steel blade."
  category: weapon
  contexts: ["combat"] # scopes which CombatSystems receive the equip formulas
  stackable: false
  equip:
    slots: ["main_hand"]
    stat_modifiers:
      - stat: strength
        amount: 2 # +2 strength while equipped (contributes to all formula expressions)
    combat_damage_formulas:
      - target_stat: hp
        display: "HP"
        # Sword swing: strength times a d6 roll. Scales with both stat and luck.
        formula: "{{ player.stats['strength'] * roll(3) }}"
```

The grenade and the sword can coexist in a choice-mode game. The sword's equip formulas fire in the auto phase regardless of what the player chooses as their action. The grenade appears as an option in the choice menu alongside skills.

Items can also be purely effect-based — no `combat_damage_formulas` at all:

```yaml
# Health Potion — pure-effect combat item; heals the player and applies a regen buff.
# No combat_damage_formulas: this item deals no damage, it only restores HP.
# Selecting it in choice mode consumes one from the stack and fires use_effects only.
apiVersion: oscilla/v1
kind: Item
metadata:
  name: health-potion
spec:
  displayName: "Health Potion"
  description: "A flask of restorative liquid. Drink to recover."
  category: consumable
  contexts: ["combat"] # available in the combat action menu
  stackable: true
  consumed_on_use: true
  use_effects:
    - type: heal
      amount: 30 # restore 30 HP immediately
    - type: apply_buff
      buff_ref: regeneration
      target: player # gain regen for 3 turns via buff's per_turn_effects
  # No combat_damage_formulas — this item is a pure healing action.
```

#### Multi-Vital Combat

Physical, Mental, and Spiritual health — defeat if any reaches 0. A game where enemies attack across multiple health dimensions, and a single move can deal split damage to more than one vital:

```yaml
# character_config.yaml — three vital stats
stats:
  - name: physical_hp
    type: int
    default: 100
  - name: mental_hp
    type: int
    default: 100
  - name: spiritual_hp
    type: int
    default: 100
  - name: strength
    type: int
    default: 10
  - name: willpower
    type: int
    default: 10
  - name: faith
    type: int
    default: 10
```

```yaml
# Enemy: Shadow Wraith — deals damage across all three health pools
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: shadow-wraith
spec:
  displayName: "Shadow Wraith"
  stats:
    physical_hp: 60
    physical_attack: 4
    mental_attack: 8
    spiritual_attack: 12
    defense: 3
```

```yaml
# CombatSystem: three player defeat conditions; enemy has one
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: tripartite-combat
spec:
  # Player loses if ANY of the three pools hits 0 — expressed as a standard any/character_stat condition.
  player_defeat_condition:
    type: any
    conditions:
      - type: character_stat
        name: physical_hp
        lte: 0
      - type: character_stat
        name: mental_hp
        lte: 0
      - type: character_stat
        name: spiritual_hp
        lte: 0
  # The wraith collapses when its Stability (physical_hp) is exhausted.
  enemy_defeat_condition:
    type: enemy_stat
    name: physical_hp
    lte: 0
  player_damage_formulas:
    - target_stat: physical_hp
      display: "Body"
      formula: "{{ max(0, player.stats['strength'] - enemy_stats['defense']) }}"
  # All three enemy formulas fire each turn, in order, before the defeat condition is evaluated.
  enemy_damage_formulas:
    - target_stat: physical_hp
      display: "Body"
      formula: "{{ max(0, enemy_stats['physical_attack'] - player.stats['strength'] // 5) }}"
    - target_stat: mental_hp
      display: "Mind"
      formula: "{{ max(0, enemy_stats['mental_attack'] - player.stats['willpower'] // 5) }}"
    - target_stat: spiritual_hp
      display: "Soul"
      formula: "{{ max(0, enemy_stats['spiritual_attack'] - player.stats['faith'] // 5) }}"
```

In `"choice"` mode a skill can deal split damage to multiple enemy vitals in a single turn. A weapon-class skill might hit the body; a psychic strike hits both body and mind:

```yaml
# Skill: Psychic Slash — deals physical AND mental damage in one move
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: psychic-slash
spec:
  displayName: "Psychic Slash"
  contexts: ["combat"]
  combat_damage_formulas:
    - target_stat: physical_hp
      formula: "{{ max(0, player.stats['strength'] - enemy_stats['defense']) }}"
    - target_stat: mental_hp
      # mental_defense is optional — .get() so enemies without it take full willpower-scaled damage
      formula: "{{ max(0, player.stats['willpower'] * 2 - enemy_stats.get('mental_defense', 0)) }}"
```

#### Rock-Paper-Scissors Combat

The player picks a throw each round; the outcome is win / tie / lose. This is the canonical example for the `"simultaneous"` turn order and `resolution_formulas`. The player commits their choice via skill `use_effects`; the enemy commits a random throw via `enemy_damage_formulas`; then `resolution_formulas` compare both committed choices and apply damage. Neither side sees a defeat check until after the comparison — mutual defeat is impossible in RPS (ties deal 0 damage to both sides) but the `"simultaneous"` mode handles it cleanly regardless. First side to run out of lives loses.

The clean design (no per-skill damage formulas, no ordering dependency):

```yaml
# character_config.yaml — throws_won is a persistent global tracker;
# lives, player_choice, and enemy_choice are combat-internal stats on the CombatSystem.
stats:
  - name: throws_won # cosmetic tracker — persists across encounters
    type: int
    default: 0
```

```yaml
# Enemy: The Challenger
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: the-challenger
spec:
  displayName: "The Challenger"
  stats:
    lives: 3
```

```yaml
# CombatSystem
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: rps-combat
spec:
  player_defeat_condition:
    type: combat_stat
    name: player_lives
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    name: lives
    lte: 0
  player_turn_mode: "choice"
  # Both phases complete before any defeat is checked.
  turn_order: "simultaneous"
  # Combat-internal stats — scoped to this encounter; discarded when combat ends.
  combat_stats:
    - name: player_lives
      default: 3
    - name: player_choice
      default: 0 # 1=Rock, 2=Paper, 3=Scissors; 0 = no throw yet
    - name: enemy_choice
      default: 0
  skill_contexts: ["rps"]
  system_skills:
    - skill: throw-rock
    - skill: throw-paper
    - skill: throw-scissors
  # Enemy phase: commit a random throw to combat_stats['enemy_choice'].
  # Delta-encode: formula result is subtracted from current, so emit (current - new) to land on new.
  enemy_damage_formulas:
    - target_stat: enemy_choice
      target: combat
      formula: "{{ combat_stats['enemy_choice'] - roll(1, 3) }}"
  # Resolution formulas fire after both choices are committed.
  # Modular arithmetic: (p - e + 3) % 3 == 1 means p beats e.
  resolution_formulas:
    # Reduce player lives by 1 if the enemy's throw beats the player's.
    - target_stat: player_lives
      target: combat
      display: "Your Lives"
      formula: >-
        {% set p = combat_stats['player_choice'] %}
        {% set e = combat_stats['enemy_choice'] %}
        {{ 1 if (e - p + 3) % 3 == 1 else 0 }}
    # Reduce enemy lives by 1 if the player's throw beats the enemy's.
    - target_stat: lives
      display: "Challenger Lives"
      formula: >-
        {% set p = combat_stats['player_choice'] %}
        {% set e = combat_stats['enemy_choice'] %}
        {{ 1 if (p - e + 3) % 3 == 1 else 0 }}
  on_combat_victory:
    - type: stat_change
      stat: throws_won
      amount: 1
```

```yaml
# Skills — one per throw. Each commits player_choice to combat_stats via use_effects.
# No combat_damage_formulas — resolution is entirely in the CombatSystem's resolution_formulas.
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: throw-rock
spec:
  displayName: "Rock ✊"
  contexts: ["rps"]
  use_effects:
    - type: stat_set
      stat: player_choice
      target: combat
      value: 1 # Rock = 1

---
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: throw-paper
spec:
  displayName: "Paper ✋"
  contexts: ["rps"]
  use_effects:
    - type: stat_set
      stat: player_choice
      target: combat
      value: 2 # Paper = 2

---
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: throw-scissors
spec:
  displayName: "Scissors ✌️"
  contexts: ["rps"]
  use_effects:
    - type: stat_set
      stat: player_choice
      target: combat
      value: 3 # Scissors = 3
```

> **Design note:** `player_lives` is a `combat_stat` rather than a global character stat — the player's life count is scoped to the encounter and discarded when combat ends. The `enemy_defeat_condition` uses `enemy_stat` (targeting `lives` from `enemy.spec.stats`) while `player_defeat_condition` uses `combat_stat` (targeting `player_lives`). The modular arithmetic `(p - e + 3) % 3 == 1` evaluates to `True` exactly when `p` beats `e` in Rock-Paper-Scissors: Rock(1) beats Scissors(3) because `(1-3+3)%3 = 1%3 = 1`; Paper(2) beats Rock(1) because `(2-1+3)%3 = 4%3 = 1`; Scissors(3) beats Paper(2) because `(3-2+3)%3 = 4%3 = 1`. Ties and losing throws produce 0 and apply no damage.

### EnemySpec Schema

```yaml
# Before
spec:
  displayName: "Iron Golem"
  hp: 9999
  attack: 50
  defense: 10
  xp_reward: 1000
  loot: [...]

# After
spec:
  displayName: "Iron Golem"
  stats:
    hp: 9999
    attack: 50
    defense: 10
  on_defeat_effects:
    - type: stat_change
      stat: xp
      amount: 1000
  loot: [...]
```

`on_defeat_effects` runs before the `on_win` branch effects, after loot drops — same dispatch as any `List[Effect]`. Any effect type is valid here: `stat_change`, `milestone_grant`, `item_grant`, `emit_trigger`, etc.

### CombatStep Extension

```yaml
steps:
  - type: combat
    enemy: iron-golem
    # combat_system omitted → falls back to game default
    on_win: [...]

  - type: combat
    enemy: final-boss
    combat_system: boss-combat # explicit per-step system override
    on_win: [...]

  - type: combat
    enemy: shadow-dragon
    # Use the default combat system, but this boss always acts first.
    combat_overrides:
      turn_order: "enemy_first"
    on_win: [...]

  - type: combat
    enemy: ancient-oracle
    # Default system, but initiative is determined by wisdom rather than the default formula.
    combat_overrides:
      turn_order: "initiative"
      player_initiative_formula: "{{ player.stats['wisdom'] }}"
      enemy_initiative_formula: "{{ enemy_stats['cunning'] }}"
      initiative_tie: "random"
    on_win: [...]
```

`CombatStep` gains two fields:

```python
combat_system: str | None = Field(
    default=None,
    description="Name of the CombatSystem manifest to use. Falls back to game default if omitted.",
)
combat_overrides: CombatStepOverrides | None = Field(
    default=None,
    description=(
        "Optional per-step overrides applied on top of the resolved CombatSystemSpec. "
        "Any field set here replaces the corresponding field from the base system for this "
        "encounter only. Useful for boss-specific initiative rules, defeat conditions, or "
        "damage formulas without authoring a full separate CombatSystem manifest."
    ),
)
```

`CombatStepOverrides` mirrors `CombatSystemSpec` with every field optional:

```python
class CombatStepOverrides(BaseModel):
    player_defeat_condition: Condition | None = None
    enemy_defeat_condition: Condition | None = None
    player_damage_formulas: List[DamageFormulaEntry] | None = None
    enemy_damage_formulas: List[DamageFormulaEntry] | None = None
    player_turn_mode: Literal["auto", "choice"] | None = None
    turn_order: Literal["player_first", "enemy_first", "initiative", "simultaneous"] | None = None
    player_initiative_formula: str | None = None
    enemy_initiative_formula: str | None = None
    initiative_tie: Literal["player_first", "enemy_first", "random"] | None = None
    simultaneous_defeat_result: Literal["player_wins", "enemy_wins", "both_lose"] | None = None
    skill_contexts: List[str] | None = None
    system_skills: List[SystemSkillEntry] | None = None
    on_combat_start: List[Effect] | None = None
    on_combat_end: List[Effect] | None = None
    on_combat_victory: List[Effect] | None = None
    on_combat_defeat: List[Effect] | None = None
    on_round_end: List[Effect] | None = None
    combat_stats: List[CombatStatEntry] | None = None
    resolution_formulas: List[DamageFormulaEntry] | None = None
```

Merge semantics: the effective spec for a combat step is the base `CombatSystemSpec` with any non-`None` `CombatStepOverrides` fields applied on top. The merged result is validated as a whole — the same rules as `CombatSystemSpec` apply (e.g. `turn_order: "initiative"` requires both initiative formulas; if only one is overridden and the other comes from the base system, the combined result is valid).

Resolution order: `step.combat_system` → `game.default_combat_system` (explicit) → single registered system (auto-default) → hard load-time error.

### Auto-Default Logic

Implemented in `ContentRegistry` post-load:

```
if game.spec.default_combat_system is not None:
    validate it exists in registry.combat_systems

elif len(registry.combat_systems) == 1:
    game.spec.default_combat_system = only key  # mutated at load time

# else: no default — any CombatStep without explicit combat_system = load error
```

This means a game with exactly one `CombatSystem` and no adventures containing `type: combat` will not error. The check is deferred to per-`CombatStep` validation during adventure loading.

### Enemy Stats Persistence

`step_state` is widened to `Dict[str, Any]` in-memory (`character.py` type annotation). The DB column is already `JSON` (`Any`), so this is purely a Python type annotation change with no migration.

Enemy state is saved under a single dict key:

```python
step_state["enemy_stats"] = dict(ctx.enemy_stats)   # persisted each round
```

On resume, `ctx.enemy_stats` is initialized from `step_state["enemy_stats"]` if present, otherwise from `enemy.spec.stats`.

The `"enemy_hp"` key (legacy) is dropped. Any save in-flight during the migration window will resume with full enemy HP (lost round state is acceptable; the encounter re-starts from the spec). No migration script is required — JSON columns tolerate both key shapes.

### stat_change target='enemy' Fix

Currently `stat_change target='enemy'` ignores the `stat` field and always mutates `combat.enemy_hp`. After this change:

```python
case StatChangeEffect(stat=stat, amount=amount, target="enemy"):
    if combat is None:
        logger.warning(...)
        return
    if stat not in combat.enemy_stats:
        logger.warning("stat_change target='enemy': stat %r not in enemy_stats — skipping.", stat)
        return
    combat.enemy_stats[stat] = max(0, combat.enemy_stats[stat] + amount)
```

Authors using `stat_change target='enemy'` with no `stat` field (relying on the old implicit behavior) must add `stat: <vital_stat>` explicitly. This is caught at load time via Pydantic validation — `stat` is a required field on `StatChangeEffect`.

### heal target='enemy' Deprecation

At load time (semantic validator), any `HealEffect` with `target: enemy` emits:

```
DeprecationWarning: heal target='enemy' is deprecated. Use stat_change target='enemy' stat: <vital_stat> instead.
```

The effect still executes at runtime (targeting the stat named `hp` in `enemy_stats` for backward compatibility — the old `enemy_hp` scalar mapped directly to that key) so existing content is not immediately broken. If no `hp` key exists in `enemy_stats`, the effect is skipped with a warning. The `HealEffect` player path is untouched.

### Template Context Changes

`CombatContextView` (the frozen dataclass exposed as `combat` in templates):

```python
# Before
@dataclass(frozen=True)
class CombatContextView:
    enemy_hp: int
    enemy_name: str
    turn: int

# After
@dataclass(frozen=True)
class CombatContextView:
    enemy_stats: Dict[str, int]
    enemy_name: str
    turn: int
```

`combat.enemy_hp` is removed. Authors must update templates:

```
{{ combat.enemy_hp }}  →  {{ combat.enemy_stats['hp'] }}
```

The mock context used for load-time validation (`_MockCombatContext`) is updated to carry a dict with all enemy stat names populated from the content package's enemy manifests.

Formula templates (damage formulas in `CombatSystemSpec`) have their own context distinct from step templates:

```python
@dataclass(frozen=True)
class CombatFormulaContext:
    # PlayerContext built with effective stats: base stats + derived shadows
    # + active equipment stat_modifiers. Equipment properties (e.g. a weapon's
    # elemental bonus stat) are therefore visible in damage formulas.
    player: PlayerContext
    enemy_stats: Dict[str, int]   # enemy's current stat values
    combat_stats: Dict[str, int]  # ephemeral combat-internal stats (from CombatSystemSpec.combat_stats)
    turn_number: int
```

The distinction from adventure-step `PlayerContext` is deliberate: combat damage formulas must reflect the player's equipped loadout, so `player.stats['fire_bonus']` returns the effective value (including any weapon bonuses) rather than the base-only value.

### enemy_action_phase() Extract

The current `_enemy_skill_phase()` function is renamed `enemy_action_phase()` and promoted to the enemy-turn dispatch hook:

```python
async def enemy_action_phase(
    enemy: EnemyManifest,
    ctx: CombatContext,
    player: CharacterState,
    registry: ContentRegistry,
    tui: UICallbacks,
) -> None:
    """Execute the enemy's turn action(s).

    Currently: periodic skill auto-fire (use_every_n_turns).
    Future: Decision Tree AI slots in here — if enemy.spec.ai is present,
    dispatch to it; otherwise fall through to the skill list.
    """
    # ... current periodic skill logic, unchanged ...
```

The Decision Tree AI change will add `ai: EnemyAISpec | None = None` to `EnemySpec` and extend this function's dispatch — no combat loop surgery required.

### Turn Order / Initiative

`CombatSystemSpec` gains three optional fields:

```python
turn_order: Literal["player_first", "enemy_first", "initiative", "simultaneous"] = Field(
    default="player_first",
    description=(
        "Controls which side acts first each round. "
        "'player_first' (default): player always acts first. "
        "'enemy_first': enemy always acts first. "
        "'initiative': both sides evaluate their respective initiative formulas each round; "
        "the higher result acts first. "
        "'simultaneous': both actor phases always complete with no mid-round defeat check; "
        "player phase fires use_effects only (no damage formulas); "
        "defeat conditions are evaluated once after all phases and resolution_formulas complete; "
        "mutual defeat is possible — outcome governed by simultaneous_defeat_result."
    ),
)
player_initiative_formula: str | None = Field(
    default=None,
    description=(
        "Required when turn_order is 'initiative'. "
        "Jinja2 template rendered in CombatFormulaContext; must return int. "
        "Higher value acts first."
    ),
)
enemy_initiative_formula: str | None = Field(
    default=None,
    description=(
        "Required when turn_order is 'initiative'. "
        "Jinja2 template rendered in CombatFormulaContext; must return int."
    ),
)
initiative_tie: Literal["player_first", "enemy_first", "random"] = Field(
    default="player_first",
    description=(
        "When turn_order is 'initiative' and both sides roll equal values, "
        "this field determines who acts first. "
        "'player_first' (default): player wins ties. "
        "'enemy_first': enemy wins ties. "
        "'random': a coin flip decides — each tied round is independently random."
    ),
)
simultaneous_defeat_result: Literal["player_wins", "enemy_wins", "both_lose"] = Field(
    default="player_wins",
    description=(
        "When turn_order is 'simultaneous' and both defeat conditions are satisfied in the "
        "same round, this field governs the outcome. "
        "'player_wins' (default): player victory takes precedence. "
        "'enemy_wins': enemy victory takes precedence. "
        "'both_lose': neither side is victorious — the combat step is treated as a defeat."
    ),
)
resolution_formulas: List[DamageFormulaEntry] = Field(
    default_factory=list,
    description=(
        "Ordered list of damage formulas that fire once per round after all actor phases "
        "have completed, before defeat conditions are evaluated. "
        "Fires in all turn_order modes. In sequential modes, fires only if no mid-round "
        "defeat occurred. In 'simultaneous' mode, always fires. "
        "Each entry uses the same DamageFormulaEntry shape as player_damage_formulas / "
        "enemy_damage_formulas; target defaults to 'enemy'. "
        "Entries apply in order; earlier entries update combat_stats visible to later entries. "
        "An empty list is the default (no-op)."
    ),
)
```

**Validation:**

- `turn_order == "initiative"` requires both `player_initiative_formula` and `enemy_initiative_formula` — hard load error if either is absent
- `turn_order != "initiative"` and either initiative formula is set — hard load error (unreachable configuration)
- Initiative formulas are compiled and mock-rendered at load time (same path as damage formulas)
- The defeat check short-circuits the round: if the first actor satisfies the opposing defeat condition, the second actor's phase does not execute

**Per-round re-evaluation:** Initiative formulas are rendered fresh each round. This supports both models naturally:

- A formula returning `player.stats['initiative']` (a stat that never changes) produces fixed ordering for the full fight
- A formula using `roll()` produces a new contest every round

**Example — flat initiative stat** (enemy with higher initiative value always goes first):

```yaml
# character_config.yaml
stats:
  - name: initiative
    type: int
    default: 5 # player base initiative
```

```yaml
# Enemy with higher initiative — acts before the player each round
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: quick-fox
spec:
  displayName: "Quick Fox"
  stats:
    hp: 40
    attack: 8
    defense: 2
    initiative: 8 # 8 > player's 5, so the fox acts first
```

```yaml
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: initiative-combat
spec:
  player_defeat_condition:
    type: character_stat
    name: hp
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    name: hp
    lte: 0
  turn_order: "initiative"
  player_initiative_formula: "{{ player.stats['initiative'] }}"
  enemy_initiative_formula: "{{ enemy_stats['initiative'] }}"
  initiative_tie: "player_first" # player wins ties
  player_damage_formulas:
    - target_stat: hp
      display: "HP"
      formula: "{{ max(0, player.stats['strength'] - enemy_stats['defense']) }}"
  enemy_damage_formulas:
    - target_stat: hp
      display: "HP"
      formula: "{{ max(0, enemy_stats['attack'] - player.stats['defense']) }}"
```

**Example — perception-based dice roll** (each side rolls a number of d6s equal to their perception stat; highest total goes first, re-rolled every round):

```yaml
# character_config.yaml
stats:
  - name: perception
    type: int
    default: 3 # roll 3d6 for initiative
```

```yaml
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: perception-initiative-combat
spec:
  player_defeat_condition:
    type: character_stat
    name: hp
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    name: hp
    lte: 0
  turn_order: "initiative"
  # roll(count, sides): player with perception=3 rolls 3d6; enemy with perception=2 rolls 2d6.
  # Higher total acts first. Re-rolled fresh each round.
  player_initiative_formula: "{{ roll(player.stats['perception'], 6) }}"
  enemy_initiative_formula: "{{ roll(enemy_stats['perception'], 6) }}"
  # Omitting initiative_tie — defaults to "player_first"
  player_damage_formulas:
    - target_stat: hp
      display: "HP"
      formula: "{{ max(0, player.stats['strength'] - enemy_stats['defense']) }}"
  enemy_damage_formulas:
    - target_stat: hp
      display: "HP"
      formula: "{{ max(0, enemy_stats['attack'] - player.stats['defense']) }}"
```

Because `turn_number` is also available in `CombatFormulaContext`, authors can express patterns like "enemy acts first on odd turns" via the formula directly — no new mode is needed.

### Resolution Formulas

`resolution_formulas: List[DamageFormulaEntry]` is an optional field on `CombatSystemSpec` that fires once per round after all actor phases have completed, before defeat conditions are evaluated.

**Ordering contract:**

1. Player action phase — skill `use_effects` commit intent to `combat_stats`; player damage formulas fire in sequential modes (skipped in `"simultaneous"` mode)
2. Enemy action phase — `enemy_damage_formulas` execute (commit enemy intent to `combat_stats` and/or apply direct damage)
3. `resolution_formulas` fire — all `combat_stats` are fully committed; `CombatFormulaContext` has complete visibility into both sides' state
4. Defeat conditions are checked

In sequential modes (`"player_first"`, `"enemy_first"`, `"initiative"`), `resolution_formulas` only fire if no mid-round defeat occurred. In `"simultaneous"` mode, `resolution_formulas` always fire because actor phases never check defeat mid-round.

**Why this is universal, not just for `"simultaneous"` mode:** Any formula that needs to see the completed round state benefits from `resolution_formulas`. Examples: an end-of-round area damage pulse that applies after both sides have acted; a comparison formula that reads both `combat_stats['player_last_action']` and `combat_stats['enemy_last_action']`; a combo-tracking formula that checks what both sides did this round before applying bonus effects.

**Intent-declaration pattern:** The idiomatic use of `"simultaneous"` mode is for systems where skills are declarations of intent rather than sources of damage. The skill's `use_effects` commit the player's choice into `combat_stats`; enemy formulas commit the enemy's choice; `resolution_formulas` compare the two and apply outcomes. Skills in this pattern have no `combat_damage_formulas` — they are pure-effect moves whose outcomes are determined by the system.

```yaml
# Typical "simultaneous" + resolution_formulas structure:

# Skills: declare intent only (no combat_damage_formulas)
spec:
  use_effects:
    - type: stat_set
      stat: player_choice
      target: combat
      value: 1 # encoding: 1=Rock, 2=Paper, 3=Scissors, etc.
  # combat_damage_formulas: []  ← intentionally absent

# Enemy formulas: commit enemy intent to combat_stats
enemy_damage_formulas:
  - target_stat: enemy_choice
    target: combat
    formula: "{{ combat_stats['enemy_choice'] - roll(3) }}" # delta-encode random draw

# Resolution formulas: compare committed state and apply outcomes
resolution_formulas:
  - target_stat: player_lives
    target: combat
    # Positive result (1) = reduce player lives by 1; 0 = no change
    formula: >-
      {% set p = combat_stats['player_choice'] %}
      {% set e = combat_stats['enemy_choice'] %}
      {{ 1 if (e - p + 3) % 3 == 1 else 0 }}
  - target_stat: enemy_lives
    target: combat
    formula: >-
      {% set p = combat_stats['player_choice'] %}
      {% set e = combat_stats['enemy_choice'] %}
      {{ 1 if (p - e + 3) % 3 == 1 else 0 }}
```

**State-sharing across entries:** `resolution_formulas` entries are applied in order and each entry's result immediately updates `combat_stats`. A later entry can read a `combat_stat` that was mutated by an earlier entry in the same pass. This enables a "set then read" pattern without requiring a separate round:

```yaml
resolution_formulas:
  # Entry 1: compute player draw from strategy, store in combat_stat
  - target_stat: player_draw
    target: combat
    formula: >-
      {% set new_draw = roll(1, 8) if combat_stats['player_strategy'] == 1 else roll(5, 13) %}
      {{ combat_stats['player_draw'] - new_draw }}
  # Entry 2: read player_draw (just set) and compare with enemy_draw
  - target_stat: player_chips
    target: combat
    formula: "{{ 1 if combat_stats['enemy_draw'] > combat_stats['player_draw'] else 0 }}"
  - target_stat: enemy_chips
    target: combat
    formula: "{{ 1 if combat_stats['player_draw'] > combat_stats['enemy_draw'] else 0 }}"
```

**Load-time validation:**

- `resolution_formulas` with `target_stat: null` and no `threshold_effects` is a hard load error (inert entry)
- Formula strings in `resolution_formulas` are compiled and mock-rendered at load time alongside `player_damage_formulas` and `enemy_damage_formulas`
- The `target` field defaults to `"enemy"` (same as other formula entries); `"player"`, `"enemy"`, and `"combat"` are all valid
- `resolution_formulas` are valid in `CombatStepOverrides`; they replace the base system's list entirely when overridden (not merged element-by-element)

### player_action_phase() Extract

A new `player_action_phase()` function is introduced as the player-turn dispatch hook, symmetric with `enemy_action_phase()`:

```python
async def player_action_phase(
    combat_system: CombatSystemManifest,
    ctx: CombatContext,
    player: CharacterState,
    registry: ContentRegistry,
    tui: UICallbacks,
) -> None:
    """Execute the player's turn action.

    In "auto" mode: iterates player_damage_formulas; for each entry renders
    the formula in CombatFormulaContext and applies the result to
    enemy_stats[entry.target_stat]. Defeat check runs after all entries have
    applied — the enemy is defeated if any enemy vital reaches 0.

    In "choice" mode: presents a menu of available combat-context skills and
    combat-context items from inventory. If a skill is selected, fires
    skill.use_effects then iterates skill.combat_damage_formulas applying
    each to enemy_stats[entry.target_stat]. If an item is selected, fires
    item.use_effects then iterates item.combat_damage_formulas, then
    consumes/decrements the item. Defeat check runs after all formulas have
    applied regardless of what was selected.

    Future: additional player_turn_mode values can slot in here without
    modifying the combat loop — e.g., "card-draw" with an interactive draw
    mechanic, or "hybrid" (auto-attack + optional skill selection).
    """
```

The combat loop calls `player_action_phase()` unconditionally each round; the mode dispatch is entirely internal to the function. This keeps the loop clean and makes future mode additions a single-function concern.

### SkillSpec: combat_damage_formula

`SkillSpec` gains one optional field:

```python
combat_damage_formulas: List[DamageFormulaEntry] = Field(
    default_factory=list,
    description=(
        "Damage formulas rendered in CombatFormulaContext when this skill is used as a move "
        "in a 'choice'-mode combat. Each entry targets one enemy vital stat. A skill with "
        "multiple entries deals split damage to multiple enemy vitals in a single turn. "
        "An empty list means no direct damage (pure-effect move). "
        "Valid only for skills with context 'combat'. Each formula is compiled and mock-rendered at load time."
    ),
)
```

This field is ignored when a skill is used outside `"choice"` mode (e.g., as an optional interrupt in `"auto"` mode — the existing behavior). A skill with an empty `combat_damage_formulas` list used in `"choice"` mode is a pure-effect move: its `use_effects` fire and no damage is applied to the enemy. This is intentional — a move like a heal or a buff application has no damage component.

The formula is rendered in the same `CombatFormulaContext` as system-level damage formulas (effective stats included — see Template Context Changes):

```python
@dataclass(frozen=True)
class CombatFormulaContext:
    player: PlayerContext         # effective stats — includes equipment stat_modifiers
    enemy_stats: Dict[str, int]
    combat_stats: Dict[str, int]  # ephemeral combat-internal stats (from CombatSystemSpec.combat_stats)
    turn_number: int
```

Load-time validation: if `combat_damage_formulas` is non-empty on a skill whose `contexts` does not intersect with any registered `CombatSystem.skill_contexts`, a hard load error is raised (the formulas can never fire).

### ContentRegistry Changes

```python
class ContentRegistry:
    ...
    combat_systems: Dict[str, CombatSystemManifest]
    ...

    def resolve_combat_system(self, name: str | None) -> CombatSystemManifest:
        """Resolve combat system by name or game default. Raises ContentLoadError if unresolvable."""
        key = name or self.game.spec.default_combat_system
        if key is None or key not in self.combat_systems:
            raise ContentLoadError(f"No combat system resolvable for name={name!r}")
        return self.combat_systems[key]
```

### Additional Formula Globals

Beyond `rollpool`, the following globals are added to `SAFE_GLOBALS` to address common authoring patterns identified from cross-system compatibility analysis:

**`rollsum(n, sides) -> int`** — Roll `n` uniform dice of `sides` sides and return the sum. Implemented as `sum(random.randint(1, sides) for _ in range(n))`. Same sandboxing rules as `roll`. `ValueError` on `n < 1` or `sides < 1`.

**`keephigh(n, sides, k) -> int`** — Roll `n` uniform dice of `sides` sides and return the sum of the highest `k`. Useful for same-size-pool keep-highest mechanics. `ValueError` on `k > n`, `n < 1`, or `sides < 1`. For mixed die sizes (e.g. Cortex Prime's attribute + skill + specialty), bind each roll to a `{% set %}` variable and drop the minimum via `min()`.

**`clamp(x, lo, hi) -> int`** — Return `max(lo, min(hi, x))`. Provided as a readable alternative to nested `max`/`min` calls for bounded values (e.g. escalation die cap: `clamp(combat_stats['escalation'], 0, 6)`).

### Formula Set-Blocks

Formula strings may contain Jinja2 `{% set %}` declarations before the final `{{ result }}` expression. Each `{% set name = expression %}` binds `name` to the result of evaluating `expression` once; subsequent references to `name` within the same formula string use the bound value — the expression is not re-evaluated.

This solves the double-evaluation correctness problem that arises when a formula must reference the same computed value (e.g. a single die roll) in multiple positions:

```
{# Bad — rolls d100 twice; the guard and the calculation may use different values: #}
{{ max(0, player.stats['weapon_skill'] - roll(100)) if (player.stats['weapon_skill'] - roll(100)) > 0 else 0 }}

{# Good — roll once, bind it, reference it twice: #}
{% set wsk_roll = roll(100) %}
{{ max(0, player.stats['weapon_skill'] - wsk_roll) if (player.stats['weapon_skill'] - wsk_roll) > 0 else 0 }}
```

`{% set %}` generalizes beyond dice: any computed sub-expression that is needed more than once — a damage threshold, an intermediate stat calculation, a clamped counter — can be bound once and used freely. The Cortex Prime "sum of two highest of three mixed-size dice" pattern becomes straightforward:

```
{% set ra = roll(player.stats['attr_die']) %}
{% set rb = roll(player.stats['skill_die']) %}
{% set rc = roll(player.stats['spec_die']) %}
{{ ra + rb + rc - min(ra, min(rb, rc)) - enemy_stats['resistance_die'] }}
```

`{% set %}` blocks and the final `{{ }}` expression are all validated and mock-rendered at load time. Variables are local to the formula string; they do not persist across formula entries or rounds. The output of the template is the rendered value of the final `{{ }}` expression and must evaluate to an integer; any `{% set %}` blocks that do not contribute to the output expression are a hard load error (they would be entirely inert).

### target_stat: null and Dynamic stat_change.value

Two companion additions unlock "tier selector" formula patterns where the formula result is not itself a damage amount.

**`DamageFormulaEntry.target_stat: None`** — When `target_stat` is `None` (YAML `null`), the formula is a "threshold-only" entry: its integer result triggers `threshold_effects` band matching but is not applied as stat damage. A `null` entry with an empty `threshold_effects` list is a hard load error (it would be entirely inert).

This solves the semantic mismatch in PbtA-style systems: a Hack and Slash move roll of 8 should not deal 8 HP damage — the roll selects a tier, and the tier determines what happens. With `target_stat: null`, the formula is a pure trigger:

```yaml
- target_stat: null # roll selects tier; no raw damage from the formula integer
  formula: "{{ roll(6) + roll(6) + player.stats['str_mod'] }}"
  threshold_effects:
    - max: 6
      effects:
        - type: stat_change
          stat: stress
          value: 3 # static int: player takes 3 stress on a miss
    - min: 7
      max: 9
      effects:
        - type: stat_change
          stat: hp
          target: enemy
          value: "{{ roll(player.stats['damage_die']) }}" # dynamic: weapon die damage
        - type: stat_change
          stat: stress
          value: 1 # static: 1 stress as the cost
    - min: 10
      effects:
        - type: stat_change
          stat: hp
          target: enemy
          value: "{{ roll(player.stats['damage_die']) }}" # clean hit: weapon die only
```

**`stat_change.value: int | str` inside `threshold_effects` bands** — Within a `ThresholdEffectBand.effects` list, `stat_change.value` may be either a static `int` or a Jinja2 formula string. The string is rendered in the same `CombatFormulaContext` as the parent formula and must evaluate to an `int`. Validated and mock-rendered at load time alongside the parent formula. This is **not** valid outside `threshold_effects` bands; using a formula string for `value` in a lifecycle hook or `use_effects` list is a hard load error.

The rationale for restricting formula-valued `stat_change` to threshold bands: lifecycle hooks (`on_combat_start`, `on_round_end`) and `use_effects` run in action-dispatch context, where a Jinja2 formula string without a damage formula parent would require a separate render pipeline. `threshold_effects` already has that pipeline since the parent formula's context is in scope.

## Risks / Trade-offs

**Breaking content changes are unavoidable.** Enemy manifests must be migrated. Template expressions using `combat.enemy_hp` must be updated. Adventures in games that use combat must have a `CombatSystem` registered. These are all intentional correctness fixes — games without the exact stat names `strength`/`dexterity`/`hp` are currently silently broken, so the migration is fixing existing brokenness, not introducing new incompatibility.

**In-flight saves lose enemy HP on resume.** Any character mid-combat during the deployment window will resume with the enemy at full HP. This is acceptable given the engine has no v1 release yet and the alternative (a migration script over JSON blobs) introduces more risk than the broken-combat window.

**Formula templates introduce a new validation surface.** A damage formula that references an enemy stat not present in a given enemy's `stats` dict will not be caught at load time (the mock context uses the full stat list from all enemies). This produces a `KeyError` at runtime if an enemy is missing a stat that the formula depends on. The semantic validator **must** verify that every enemy registered for a given `CombatSystem` carries all stat names referenced in that system's damage formulas. A missing stat on any enemy is a hard load-time error.

**`combat.enemy_hp` removal is an author-breaking template change.** Testlandia will be fully migrated as part of this change. Other content packages (none exist yet) would need to migrate their own templates.

## Testing Philosophy

Tests live in `tests/engine/test_combat_system.py`. No test references the `content/` directory — all fixtures are constructed directly as Pydantic models or inline Python dicts passed to the loader pipeline.

**Tier 1 — unit tests on defeat condition evaluation** (`test_evaluate_enemy_stat_condition_*`):

These tests call `evaluate()` directly with an `EnemyStatCondition` leaf, confirming it reads from the `enemy_stats` parameter and composes correctly with logical operators.

```python
def test_evaluate_enemy_stat_condition_true() -> None:
    """EnemyStatCondition evaluates True when the enemy stat satisfies the comparator."""
    condition = EnemyStatCondition(type="enemy_stat", name="hp", lte=0)
    player = make_character_state()
    assert evaluate(condition, player, registry, enemy_stats={"hp": 0}) is True

def test_evaluate_enemy_stat_condition_false() -> None:
    """EnemyStatCondition evaluates False when the stat does not satisfy the comparator."""
    condition = EnemyStatCondition(type="enemy_stat", name="hp", lte=0)
    player = make_character_state()
    assert evaluate(condition, player, registry, enemy_stats={"hp": 50}) is False

def test_evaluate_enemy_stat_condition_outside_combat_logs_warning() -> None:
    """EnemyStatCondition returns False and logs a warning when enemy_stats is None."""
    condition = EnemyStatCondition(type="enemy_stat", name="hp", lte=0)
    player = make_character_state()
    assert evaluate(condition, player, registry, enemy_stats=None) is False

def test_evaluate_enemy_stat_condition_in_any_combinator() -> None:
    """EnemyStatCondition composes correctly inside an any/all tree."""
    condition = AnyCondition(type="any", conditions=[
        EnemyStatCondition(type="enemy_stat", name="physical_hp", lte=0),
        EnemyStatCondition(type="enemy_stat", name="mental_hp", lte=0),
    ])
    player = make_character_state()
    assert evaluate(condition, player, registry, enemy_stats={"physical_hp": 0, "mental_hp": 50}) is True
    assert evaluate(condition, player, registry, enemy_stats={"physical_hp": 10, "mental_hp": 10}) is False
```

**Tier 2 — unit tests on turn order resolution** (`test_resolve_turn_order_*`):

These tests call `resolve_turn_order()` directly with a `CombatSystemSpec` and a `CombatFormulaContext`, asserting the correct `(first_actor, second_actor)` tuple is returned.

```python
def test_turn_order_player_first() -> None:
    """player_first always returns (player, enemy) regardless of stats."""

def test_turn_order_enemy_first() -> None:
    """enemy_first always returns (enemy, player) regardless of stats."""

def test_turn_order_initiative_player_wins() -> None:
    """initiative returns (player, enemy) when player formula yields higher value."""

def test_turn_order_initiative_enemy_wins() -> None:
    """initiative returns (enemy, player) when enemy formula yields higher value."""

def test_turn_order_initiative_tie_player_first() -> None:
    """initiative with initiative_tie='player_first' gives player priority on equal rolls."""

def test_turn_order_initiative_tie_enemy_first() -> None:
    """initiative with initiative_tie='enemy_first' gives enemy priority on equal rolls."""

def test_turn_order_initiative_tie_random_is_nondeterministic() -> None:
    """initiative with initiative_tie='random' produces both outcomes across many calls."""
```

**Tier 3 — unit tests on `CombatStepOverrides` merge** (`test_combat_step_overrides_*`):

These tests exercise `merge_overrides(base_spec, overrides)` — the function that produces an effective `CombatSystemSpec` for a step — without touching the combat loop.

```python
def test_overrides_none_returns_base_unchanged() -> None:
    """Passing overrides=None returns the base spec unmodified."""

def test_overrides_partial_replaces_only_set_fields() -> None:
    """Only non-None override fields are applied; base fields without overrides are preserved."""

def test_overrides_turn_order_initiative_valid_when_both_formulas_present() -> None:
    """Merged spec with turn_order='initiative' and both formulas is valid."""

def test_overrides_turn_order_initiative_missing_formula_raises() -> None:
    """Merged spec with turn_order='initiative' but only one formula is a load-time error."""
```

**Tier 4 — combat loop integration tests** (`test_combat_loop_*`):

These tests call `run_combat()` end-to-end via the fixture pipeline. All fixture manifests use `test-` prefixed names and live in `tests/fixtures/content/combat-system/`. The `mock_tui` fixture is required for all pipeline tests.

```python
def test_combat_loop_player_wins_auto_mode() -> None:
    """Player defeats enemy via auto-mode damage formulas; on_win branch executes."""

def test_combat_loop_player_loses_auto_mode() -> None:
    """Enemy defeats player via auto-mode formulas; on_defeat branch executes."""

def test_combat_loop_enemy_stats_persisted_across_rounds() -> None:
    """enemy_stats dict is written to step_state each round; resume restores it correctly."""

def test_combat_loop_enemy_first_turn_order() -> None:
    """With turn_order='enemy_first', enemy damage formula fires before player action."""

def test_combat_loop_initiative_short_circuits_on_defeat() -> None:
    """When the first actor defeats the opponent, the second actor's phase is skipped."""

def test_combat_loop_stat_change_target_enemy_uses_stat_name() -> None:
    """stat_change target='enemy' stat: 'hp' decrements enemy_stats['hp'] by amount."""

def test_combat_loop_stat_change_target_enemy_missing_stat_skips() -> None:
    """stat_change target='enemy' with an unknown stat logs a warning and does not error."""

def test_combat_loop_heal_target_enemy_deprecated_still_executes() -> None:
    """heal target='enemy' emits a deprecation warning but still applies to enemy_stats['hp']."""

def test_combat_loop_choice_mode_skill_selected() -> None:
    """In choice mode, selected skill's use_effects and combat_damage_formulas both fire."""

def test_combat_loop_choice_mode_item_selected_and_consumed() -> None:
    """In choice mode, selected consumable item's use_effects fire and stack is decremented."""

def test_combat_loop_equip_formulas_fire_in_auto_mode() -> None:
    """Equipped item combat_damage_formulas contribute to player attack in auto mode."""

def test_combat_loop_step_overrides_applied() -> None:
    """combat_overrides on a CombatStep replace base system fields for that encounter only."""
```

**Load-time validation tests** (`test_combat_system_validation_*`):

```python
def test_load_error_missing_player_defeat_condition() -> None:
    """CombatSystem without player_defeat_condition is a hard load error."""

def test_load_error_missing_enemy_defeat_condition() -> None:
    """CombatSystem without enemy_defeat_condition is a hard load error."""

def test_load_error_choice_mode_with_player_damage_formulas() -> None:
    """player_turn_mode='choice' + non-empty player_damage_formulas is a hard load error."""

def test_load_error_initiative_missing_formula() -> None:
    """turn_order='initiative' without both initiative formulas is a hard load error."""

def test_load_error_initiative_formula_on_non_initiative_system() -> None:
    """Initiative formula set when turn_order != 'initiative' is a hard load error."""

def test_load_error_enemy_missing_stat_referenced_in_formula() -> None:
    """Enemy lacking a stat referenced in a non-.get() formula is a hard load error."""

def test_load_error_no_combat_system_with_combat_step() -> None:
    """A combat step with no resolvable CombatSystem is a hard load error."""

def test_load_error_skill_combat_formulas_no_matching_context() -> None:
    """combat_damage_formulas on a skill with no matching skill_contexts is a hard load error."""
```

## Documentation Plan

### New Files

| File                                              | Audience        | Content                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docs/authors/combat-systems.md`                  | Content authors | New document covering the `CombatSystem` manifest kind end-to-end: manifest structure, all spec fields (`player_defeat_condition`, `enemy_defeat_condition`, `player_damage_formulas`, `enemy_damage_formulas`, `player_turn_mode`, `turn_order`, initiative fields, `skill_contexts`), the `DamageFormulaEntry` shape, `CombatFormulaContext` variables, HUD display via `display:`, the `auto` vs `choice` turn mode distinction, load-time validation rules, and a full reference table                                                                                                                                                                                                                                                             |
| `docs/authors/cookbook/combat-system-patterns.md` | Content authors | New cookbook page with five ready-to-adapt patterns: (1) **Classic RPG** — standard strength-vs-defense auto mode with a single HP vital, (2) **Move Selection** — Pokémon-style choice mode with a skill roster and resource costs, (3) **Elemental Affinity** — weapon bonus stat multiplied by enemy vulnerability stat via `.get()`, (4) **Multi-Vital** — three health pools where losing any one triggers defeat, skill with split-damage formulas, (5) **Rock-Paper-Scissors** — pure `enemy_stat` mutation encoding a random throw each round; also covers per-step overrides (boss with `enemy_first` turn order, boss with custom initiative formulas). Each pattern is a complete set of manifests that can be dropped into a game package. |

### Updated Files

| Document                             | Audience                 | Changes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ------------------------------------ | ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/authors/enemies.md`            | Content authors          | Replace the **Combat Stats** section (currently describes `hp`, `attack`, `defense`, `xp_reward` as universal fields) with a **`stats` Dict** section explaining that `stats` is a free-form dict keyed by whatever stat names the game's `CombatSystem` uses; add a migration note showing Before/After for the `hp`/`attack`/`defense`/`xp_reward` → `stats` + `on_defeat_effects` shape; update the manifest fields reference table; add new **`on_defeat_effects`** section explaining that reward effects (XP, items, milestones, triggers) go here instead of hardcoded `xp_reward` |
| `docs/authors/skills.md`             | Content authors          | New **Combat Moves** section: explains `combat_damage_formulas` on `SkillSpec`, the `DamageFormulaEntry` shape (`target_stat`, `formula`, `display`), the `CombatFormulaContext` variables (`player`, `enemy_stats`, `turn_number`), and the rule that `contexts` must include a string matching the active `CombatSystem.skill_contexts`; copy-paste examples for a damage move, a split-damage move, and a pure-effect move; update `SkillSpec` fields table to reflect `contexts` as arbitrary strings                                                                                 |
| `docs/authors/items.md`              | Content authors          | New **Combat Items** section: explains `ItemSpec.contexts` for active combat actions (choice mode), `ItemSpec.combat_damage_formulas`, and `EquipSpec.combat_damage_formulas` for passive equip contributions (auto mode); shows grenade (active), sword (passive equip), and health potion (pure-effect, no formulas) examples                                                                                                                                                                                                                                                           |
| `docs/authors/conditions.md`         | Content authors          | New **`enemy_stat` condition** section: documents the new leaf type, its `name` and comparator fields, notes it is only valid inside `CombatSystem` defeat conditions and evaluates to `false` with a warning elsewhere, shows a multi-vital `any` example                                                                                                                                                                                                                                                                                                                                |
| `docs/authors/adventures.md`         | Content authors          | Update the **`combat` step** reference table: add `combat_system` (optional, name of `CombatSystem` manifest) and `combat_overrides` (optional, `CombatStepOverrides` fields) entries with descriptions; add worked examples for per-step system override and per-step `combat_overrides`                                                                                                                                                                                                                                                                                                 |
| `docs/authors/game-configuration.md` | Content authors          | New **`default_combat_system`** field documented in the `game.yaml` fields table; note on auto-default promotion when exactly one system is registered; add `CombatSystem` to the manifest kinds overview                                                                                                                                                                                                                                                                                                                                                                                 |
| `docs/dev/game-engine.md`            | Developers               | Update the **Combat** section (§Combat, currently ~line 309): replace the hardcoded-stat description with the `CombatSystem`-delegated architecture; document `CombatContext.enemy_stats: Dict[str, int]`, `CombatFormulaContext`, `player_action_phase()`, `enemy_action_phase()`, `resolve_turn_order()`, `merge_overrides()`, and the `EnemyStatCondition` hook in `evaluate()`; note the `combat.enemy_hp` → `combat.enemy_stats['hp']` template migration                                                                                                                            |
| `docs/system-overview.md`            | Contributors / AI agents | Update the **Combat** subsection to reference `CombatSystem` manifest as the combat arithmetic authority; add `CombatSystem` to the manifest kinds table; note that `enemy_stat` conditions are valid only inside combat defeat conditions                                                                                                                                                                                                                                                                                                                                                |

## Examples Catalog

Concrete multi-manifest examples live in the `examples/` directory alongside this design. Each file contains all manifests needed to exercise the pattern (CombatSystem, Enemies, Skills, Items as required), separated by YAML `---` document dividers. These are intended for documentation, load-time validation testing, and engine smoke tests.

### Fits Well

These examples exercise the core combat model with no approximation or engine gaps.

| File                                                                    | System                   | Key features demonstrated                                                                                                  |
| ----------------------------------------------------------------------- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| [dnd5e-attack-roll.yaml](examples/dnd5e-attack-roll.yaml)               | D&D 5e Attack Roll       | Conditional gated damage (d20 + bonus vs AC); weapon die on hit                                                            |
| [13th-age-escalation-die.yaml](examples/13th-age-escalation-die.yaml)   | 13th Age Escalation Die  | `combat_stats` counter; `on_round_end` increment; escalation-boosted formula; `system_skills` with `combat_stat` condition |
| [call-of-cthulhu-sanity.yaml](examples/call-of-cthulhu-sanity.yaml)     | Call of Cthulhu Sanity   | Multi-vital `any` defeat condition; `on_combat_start` sanity drain; multi-formula enemy turn targeting different stats     |
| [morale-system.yaml](examples/morale-system.yaml)                       | Morale System            | Enemy defeat by non-HP stat; player formula targeting enemy morale                                                         |
| [warhammer-fantasy-battle.yaml](examples/warhammer-fantasy-battle.yaml) | Warhammer Fantasy Battle | Two-stage gated damage (to-hit then to-wound); inline ternary wound table                                                  |
| [pbta-tiered-outcomes.yaml](examples/pbta-tiered-outcomes.yaml)         | PbtA Dungeon World       | `target_stat: null` threshold-only formula; dynamic `stat_change.value` per tier; 2d6+stat move; choice mode               |
| [blades-in-the-dark.yaml](examples/blades-in-the-dark.yaml)             | Blades in the Dark       | `rollpool()` for dice-pool success counting; `threshold_effects` miss/partial/full tiers; choice mode                      |

### Possible but Awkward

These examples work but require non-obvious author patterns to encode the mechanic. Comments in each file describe the gap and the workaround.

| File                                                                              | System                    | Gap                                                | Workaround                                                                                                                                                                                      |
| --------------------------------------------------------------------------------- | ------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [dnd5e-action-economy.yaml](examples/dnd5e-action-economy.yaml)                   | D&D 5e Action Economy     | Single-action-per-phase (no Action + Bonus Action) | Compound skills merge both phases; bonus-action-only path still available as a choice                                                                                                           |
| [savage-worlds-wild-die.yaml](examples/savage-worlds-wild-die.yaml)               | Savage Worlds Wild Die    | Raise cascade and die-stepping require care        | `max(roll(trait), roll(6))` for the wild die; threshold_effects for one-raise tier                                                                                                              |
| [warhammer-frpg-opposed-rolls.yaml](examples/warhammer-frpg-opposed-rolls.yaml)   | WFRP Opposed Rolls        | No simultaneous resolution primitive               | `combat_stat` stores first-actor's roll; second formula reads and compares                                                                                                                      |
| [ironsworn-progress-clocks.yaml](examples/ironsworn-progress-clocks.yaml)         | Ironsworn Progress Clocks | No clock/segmented display hint for frontend       | `combat_stat` clock counter; enemy_defeat_condition on `combat_stat ≥ max`; display gap noted                                                                                                   |
| [burning-wheel-scripted-combat.yaml](examples/burning-wheel-scripted-combat.yaml) | Burning Wheel Fight!      | Sealed hidden-choice scripting phase               | `turn_order: "simultaneous"` + `resolution_formulas` gives correct ordering (both commit before resolution); player sees their own choice; enemy choice is random (not adversarially strategic) |

### Breaks the Model — Approximation Only

These examples reveal fundamental limits of the scalar formula model. Each file is a best-effort approximation and includes detailed comments on what cannot be represented. They are useful as regression targets for engine boundary behavior and as documentation of known limitations.

| File                                                                | System             | Fundamental gap                                         | Approximation used                                                                                                                     |
| ------------------------------------------------------------------- | ------------------ | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| [vampire-the-masquerade.yaml](examples/vampire-the-masquerade.yaml) | VtM V5 Hunger Dice | No provenance-aware dice pool                           | Split `regular_pool` and `hunger` rollpool() calls; Bestial Failure / Messy Critical approximated by total success count               |
| [cortex-prime.yaml](examples/cortex-prime.yaml)                     | Cortex Prime       | No dynamic pool assembly phase before the formula fires | Fixed stat-per-Trait-Set pool; `{% set %}` bindings for correct "sum of two highest" with mixed die sizes; Plot Points and SFX omitted |
