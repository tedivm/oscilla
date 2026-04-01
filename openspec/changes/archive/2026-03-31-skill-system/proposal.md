## Why

The engine currently has no mechanism for characters (or enemies) to perform active abilities beyond basic attacks. This blocks a wide class of game designs — magic systems, martial arts, psionics, sci-fi tech abilities, and any other system where characters learn and activate named capabilities with costs, conditions, and effects. A flexible skill system is prerequisite to building expressive, genre-spanning content packages.

## What Changes

- Introduce a new `Skill` manifest kind with full spec support: display name, category, activation contexts, resource cost, cooldown, and use effects.
- Introduce a new `Buff` manifest kind for timed combat effects: per-turn tick effects, passive combat modifiers (`damage_reduction`, `damage_amplify`, `damage_reflect`, `damage_vulnerability`), duration, and optional named variables for parameterization.
- Add `ApplyBuffEffect` (`apply_buff`) as the single mechanism for granting timed combat buffs from skills, items, adventures, or enemies.
- Add `SkillGrantEffect` to the existing effect union so adventures and items can teach skills to players.
- Add a `target` field (`"player"` | `"enemy"`) to `StatChangeEffect`, `StatSetEffect`, and `HealEffect` so effects can be directed at enemies during combat.
- Add `SkillCondition` to the condition union with a `mode` field (`"available"` | `"learned"`) to gate content on skill ownership.
- Extend `CharacterState` with `known_skills: Set[str]`, `skill_cooldowns: Dict[str, int]`, and `available_skills(registry)` computed method.
- Extend `CharacterConfig` with `skill_resources` (binding resource names to stats) and optional `skill_category_rules` (cross-category restriction governance).
- Extend `ItemSpec` with `grants_skills_equipped` and `grants_skills_held` lists so equipment and inventory items can grant ephemeral skills.
- Extend `EnemySpec` with a fixed `skills` list and initial `skill_resources` values; enemies use skills without an acquisition system.
- Add a `CombatContext` ephemeral dataclass (never serialized) that holds live enemy HP, active periodic effects, skill use tracking, and turn counter; pass it through the combat loop and effect dispatcher.
- Add an Actions screen to the TUI for invoking skills with `context: overworld` outside of combat.
- Update the combat loop to present a "Use Skill" action alongside Attack and Flee.
- Update persistence (serialization/deserialization) for `known_skills` and `skill_cooldowns`.

## Capabilities

### New Capabilities

- `skill-system`: The core `Skill` manifest, `SkillSpec` model, content registry loading, `SkillGrantEffect`, `SkillCondition` (with `mode`), `CharacterState` skill tracking, `available_skills()`, and adventure-scope cooldown persistence.
- `buff-system`: The `Buff` manifest, `BuffSpec` model (with `variables` for parameterization), `CombatModifier` discriminated union, `ApplyBuffEffect` and `DispelEffect` in the effect union, and `ActiveCombatEffect` in `CombatContext`.
- `combat-skills`: `CombatContext` dataclass, integration of player skill use into the combat turn loop (Use Skill action), per-turn buff ticking, turn-scope cooldown tracking, passive modifier arithmetic (`_apply_damage_amplify`, `_apply_incoming_modifiers`, `_apply_reflect`), and enemy skill use (simple timer-based dispatch, no AI yet).
- `item-skill-grants`: `grants_skills_equipped` and `grants_skills_held` fields on `ItemSpec`; `available_skills()` includes item-granted skills when registry is provided.
- `actions-screen`: New TUI Actions screen listing and invoking overworld-context skills, showing resource costs and cooldown state.

### Modified Capabilities

- `adventure-pipeline`: `run_effect()` gains an optional `CombatContext` parameter; effects with `target: "enemy"` route through it. `SkillGrantEffect` added to the effect union.
- `condition-evaluator`: `SkillCondition` added to the condition union; `evaluate()` gains the new case.
- `item-system`: `ItemSpec` extended with `grants_skills_equipped` and `grants_skills_held`; `CharacterState.available_skills()` consults equipped and held items.
- `player-state`: `CharacterState` extended with `known_skills`, `skill_cooldowns`, and `available_skills()`; persistence updated.

## Impact

- **Engine models**: New `oscilla/engine/models/skill.py` and `oscilla/engine/models/buff.py`; changes to `adventure.py` (effect union, `ApplyBuffEffect`, `DispelEffect`, target field), `base.py` (condition union), `character_config.py` (skill resources/rules), `item.py` (`BuffGrant` model, buff and skill grants), `enemy.py` (skills field).
- **Character engine**: `oscilla/engine/character.py` gains `known_skills`, `skill_cooldowns`, `available_skills()`, and serialization updates.
- **Conditions**: `oscilla/engine/conditions.py` gains `SkillCondition` case; requires registry for `mode: available` evaluation.
- **Effect dispatcher**: `oscilla/engine/steps/effects.py` gains `SkillGrantEffect` handler and `target` routing via `CombatContext`.
- **Combat step**: `oscilla/engine/steps/combat.py` restructured around `CombatContext`; adds skill menu, periodic effect tick, and basic enemy skill use.
- **TUI**: `oscilla/engine/tui.py` gains Actions screen entry point and skill display callbacks.
- **Registry**: `oscilla/engine/registry.py` gains `skills: KindRegistry[SkillManifest]` and `buffs: KindRegistry[BuffManifest]` collections.
- **Content registry**: `oscilla/engine/loader.py` gains `Skill` manifest loading and cross-reference validation (skill refs in items, enemies, effects).
- **Database**: `known_skills` and `skill_cooldowns` added to the character persistence schema (new migration).
- **No new external dependencies** expected.
