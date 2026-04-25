## MODIFIED Requirements

### Requirement: Combat context view

The `CombatContextView` dataclass exposed as `combat` in templates SHALL carry `enemy_stats: Dict[str, int]` (keyed by the stat names declared in the enemy manifest), `combat_stats: Dict[str, int]` (ephemeral system-internal stats), `enemy_name: str`, and `turn: int`. The legacy `enemy_hp: int` field is removed. This is a breaking change for any template using `{{ combat.enemy_hp }}`; authors must migrate to `{{ combat.enemy_stats['hp'] }}` (or whichever stat name their game uses).

#### Scenario: Template accesses enemy stat via dict key

- **WHEN** a narrative template uses `{{ combat.enemy_stats['hp'] }}` inside a combat context
- **THEN** it renders the current value of the enemy's `hp` stat

#### Scenario: Template accesses combat stat via dict key

- **WHEN** a template uses `{{ combat.combat_stats['escalation'] }}` inside a combat context
- **THEN** it renders the current value of the `escalation` combat stat

#### Scenario: Legacy enemy_hp reference raises UndefinedError at load time

- **WHEN** a template uses `{{ combat.enemy_hp }}` and the context_type is `"combat"`
- **THEN** the load-time mock render raises `UndefinedError` and the validator emits a hard error

---

### Requirement: Skills operate via context strings in combat

Skills are eligible in a combat system's choice-mode menu when the skill's `contexts` list intersects the system's `skill_contexts` list. The `contexts` field is an open `List[str]`; the value `"overworld"` remains reserved for overworld availability.

#### Scenario: Skill eligible when contexts intersect system skill_contexts

- **WHEN** a skill declares `contexts: ["melee"]` and the active combat system declares `skill_contexts: ["melee"]`
- **THEN** that skill is eligible in the combat system's choice-mode menu

#### Scenario: Skill with only "overworld" context never appears in combat

- **WHEN** a skill declares `contexts: ["overworld"]`
- **THEN** it never appears in any combat system's action menu regardless of `skill_contexts`

## REMOVED Requirements

### Requirement: Combat context view (old)

The legacy `CombatContextView` with `enemy_hp: int` is replaced by the updated `CombatContextView` with `enemy_stats: Dict[str, int]` and `combat_stats: Dict[str, int]`.
