# Combat System

## MODIFIED Requirements

### Requirement: Damage formula lists

A `CombatSystemSpec` SHALL declare `player_damage_formulas` and `enemy_damage_formulas` as lists of `DamageFormulaEntry` objects. Each `DamageFormulaEntry` SHALL have a Jinja2 `formula` string rendered in `CombatFormulaContext`, a `target_stat` naming the stat key to decrement, a `target` routing field (`"player"`, `"enemy"`, or `"combat"`), an optional `display` label, and an optional `threshold_effects` list. All entries in a list SHALL apply in order before defeat conditions are evaluated. A `DamageFormulaEntry` with `target_stat: null` and an empty `threshold_effects` list SHALL be a hard load error. Formulas SHALL be mock-rendered at load time to catch syntax errors.

The `CombatFormulaContext` SHALL expose:

- `player` — dict of player stats (int values)
- `enemy_stats` — dict of enemy stats (int values)
- `combat_stats` — dict of combat stats (int values)
- `turn_number` — current round number (int)
- `this` — dict of manifest properties (`Dict[str, int | float | str | bool]`) populated from the triggering manifest's `properties` (item, skill, or enemy)

#### Scenario: Player damage formula decrements enemy stat

- **WHEN** `player_damage_formulas` contains one entry with `target_stat: hp`, `target: enemy`, and `formula: "{{ player.stats['strength'] - enemy_stats['defense'] }}"`
- **THEN** each round the result is subtracted from `enemy_stats["hp"]`

#### Scenario: Multiple player damage formulas apply in order

- **WHEN** `player_damage_formulas` contains two entries targeting different enemy stats
- **THEN** both are applied sequentially in the declared order before the defeat check

#### Scenario: Threshold effects fire in matching band

- **WHEN** a formula result falls within a `ThresholdEffectBand` range and that band declares `effects`
- **THEN** the effects in that band are run after the stat decrement

#### Scenario: formula syntax error caught at load time

- **WHEN** a `DamageFormulaEntry.formula` contains invalid Jinja2 syntax
- **THEN** the content validator emits a hard error before the game starts

#### Scenario: Formula accesses this property value

- **WHEN** a damage formula `{{ this.get('damage_die', 4) + player['strength'] // 4 }}` is rendered with `this = {"damage_die": 6}` and `player["strength"] = 5`
- **THEN** the result is `7` (6 + 5 // 4 = 6 + 1 = 7)

#### Scenario: Formula uses this.get() default when properties empty

- **WHEN** a damage formula `{{ this.get('damage_die', 4) }}` is rendered with `this = {}`
- **THEN** the result is `4`
