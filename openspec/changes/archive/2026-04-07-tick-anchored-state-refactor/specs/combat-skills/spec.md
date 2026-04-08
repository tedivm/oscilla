## MODIFIED Requirements

### Requirement: Player skill use in combat

The combat turn loop SHALL present a dynamic menu: `["Attack", ...skills..., "Flee"]`. Skills appear between Attack and Flee, one entry per skill ref in `player.available_skills(registry)` where the skill's `contexts` includes `"combat"`. Selecting a skill action SHALL invoke `_use_skill_in_combat()`.

`_use_skill_in_combat()` SHALL validate the following in order before applying any effects:

1. Turn-scope cooldown not active.
2. Adventure-scope cooldown not active.
3. Resource cost is affordable.
4. `requires` condition is satisfied (if declared).

If any check fails, the TUI SHALL display an appropriate message and the function SHALL return False without consuming any resources or advancing cooldowns.

If all checks pass:

1. Resource is deducted from `player.stats`.
2. Cooldown is recorded:
   - Turn-scope: tracked in `CombatContext.skill_uses_this_combat` (turn number at use).
   - Adventure-scope: `skill_tick_expiry` and `skill_real_expiry` on CharacterState are set to `internal_ticks + required_ticks` and `time.time() + required_seconds` respectively.
3. `use_effects` are dispatched via `run_effect()`.

Adventure-scope cooldown is active when `internal_ticks < skill_tick_expiry[ref]` OR `time.time() < skill_real_expiry[ref]`.

#### Scenario: Player selects skill action

- **WHEN** a player with the "fireball" skill in their available_skills selects "Skill: Fireball" from the combat menu
- **THEN** fireball's use_effects are dispatched and any resource cost is deducted

#### Scenario: Skill blocked by insufficient resource

- **WHEN** a skill costs 10 mana and the player has 5 mana
- **THEN** the TUI shows a "Not enough mana" message and no effects fire

#### Scenario: Turn-scope cooldown blocks reuse

- **WHEN** a skill with `cooldown: {scope: turn, turns: 3}` was last used on turn 1
- **THEN** attempting to use it again on turn 2 or 3 shows a cooldown message
- **THEN** the skill fires normally on turn 4

#### Scenario: Adventure-scope tick cooldown blocks reuse

- **WHEN** a skill with `cooldown: {ticks: 3}` is used at `internal_ticks == 10`
- **THEN** `skill_tick_expiry[skill_ref] == 13`
- **THEN** the skill cannot be used again while `internal_ticks < 13`

#### Scenario: Adventure-scope ticks cooldown expires after advancement

- **WHEN** a skill with `cooldown: {ticks: 3}` was used and `internal_ticks` has advanced to 13 or beyond
- **THEN** the skill is available for use again

#### Scenario: No skills available, menu shows only Attack and Flee

- **WHEN** the player has no skills with `contexts: [combat]`
- **THEN** the combat menu contains exactly `["Attack", "Flee"]` with no skill entries

---

## REMOVED Requirements

### Requirement: Adventure-scope cooldown uses player.skill_cooldowns countdown

**Reason:** `skill_cooldowns` stored a countdown (adventures remaining) that required `tick_skill_cooldowns()` to be called at adventure start to decrement. This method was never called, making adventure-scoped skill cooldowns non-functional. The countdown model is replaced by absolute expiry timestamps (`skill_tick_expiry`, `skill_real_expiry`) that require no ceremony.

**Migration:** `player.skill_cooldowns[skill_ref] = spec.cooldown.count` → `player.skill_tick_expiry[skill_ref] = player.internal_ticks + resolved_ticks`.

### Requirement: SkillCooldown schema with scope and count fields

**Reason:** `SkillCooldown(scope: "turn"|"adventure", count: int)` is replaced by the shared `Cooldown` model (see unified-cooldown-schema spec). This provides consistency with adventure cooldowns and enables multi-constraint cooldowns and template expressions.

**Migration:**

- `cooldown: {scope: adventure, count: N}` → `cooldown: {ticks: N}`
- `cooldown: {scope: turn, count: N}` → `cooldown: {scope: turn, turns: N}`
