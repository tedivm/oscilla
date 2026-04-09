## REMOVED Requirements

### Requirement: xp_grant effect

**Reason:** `xp_grant` was a special-cased effect solely because it needed to call `add_xp()`, which handled level detection, `max_hp` mutation, and `on_level_up` enqueue. All of that machinery is removed. XP is now an ordinary stat. `stat_change` on the `xp` stat produces the same result as `xp_grant` did, with threshold triggers fired by the standard `on_stat_threshold` mechanism.

**Migration:** Replace all `xp_grant { amount: N }` effects with `stat_change { stat: xp, amount: N }` (or whatever name you declared for your XP stat in `character_config.yaml`).

---

## MODIFIED Requirements

### Requirement: stat_change effect applies a numeric delta to a player stat

The `stat_change` adventure effect SHALL modify a named stat by a signed integer amount. The `stat` field SHALL reference a stored (non-derived) stat name declared in `CharacterConfig`. **Targeting a derived stat is a content load error.** The `amount` field SHALL be a non-zero integer **or a Jinja2 template string that resolves to a non-zero integer at runtime**. The effect SHALL be validated at content load time: the referenced stat MUST exist in `CharacterConfig`, its declared type MUST be `int`, and it MUST NOT be a derived stat. A `stat_change` targeting a `bool` stat SHALL be a content load error.

If applying the delta would produce a value outside the stat's effective bounds (see stat-bounds spec), the result SHALL be clamped, a WARNING logged, and the player notified via the TUI. The amount type is `int | str` — float amounts and non-integer template results are not accepted.

When `amount` is a template string, the template SHALL be precompiled and mock-rendered at content load time. A template that fails mock render SHALL be a content load error. At runtime, the template SHALL be rendered to produce a string, then coerced to `int`; a render result that cannot be coerced SHALL raise a `TemplateRuntimeError`.

After `stat_change` applies its delta to the stored stat, the engine SHALL call `_recompute_derived_stats()` and `_fire_threshold_triggers()` for the modified stored stat.

#### Scenario: Positive delta increases int stat

- **WHEN** `stat_change { stat: strength, amount: 2 }` is applied to a player with `strength: 10`
- **THEN** `player.stats["strength"]` equals `12`

#### Scenario: Negative delta decreases int stat

- **WHEN** `stat_change { stat: speed, amount: -1 }` is applied to a player with `speed: 5`
- **THEN** `player.stats["speed"]` equals `4`

#### Scenario: Targeting a bool stat is a load error

- **WHEN** a manifest declares `stat_change { stat: is_blessed, amount: 1 }` and `is_blessed` is a `bool` stat
- **THEN** the content loader raises a `LoadError` identifying the adventure manifest and the invalid stat type

#### Scenario: Targeting a derived stat is a load error

- **WHEN** a manifest declares `stat_change { stat: level, amount: 1 }` and `level` is a derived stat
- **THEN** the content loader raises a `LoadError` identifying the adventure, step, and derived stat name

#### Scenario: Targeting an unknown stat is a load error

- **WHEN** a manifest declares `stat_change { stat: nonexistent, amount: 1 }`
- **THEN** the content loader raises a `LoadError` identifying the adventure manifest and the unknown stat name

#### Scenario: Float amount is rejected at load time

- **WHEN** a manifest declares `stat_change { stat: speed, amount: 0.5 }` and `speed` is an `int` stat
- **THEN** the content loader raises a `LoadError` identifying the invalid float amount

#### Scenario: Template amount applies correct delta

- **WHEN** `stat_change { stat: gold, amount: "{{ roll(1, 10) }}" }` is applied
- **THEN** `gold` increases by an integer between 1 and 10 inclusive

#### Scenario: Template amount that renders to non-integer raises TemplateRuntimeError

- **WHEN** a `stat_change` template resolves to `"foo"` at runtime
- **THEN** a `TemplateRuntimeError` is raised

#### Scenario: stat_change on xp stat triggers derived level re-evaluation

- **WHEN** `stat_change { stat: xp, amount: 500 }` is applied and `level` is a derived stat based on `xp`
- **THEN** `player._derived_shadows["level"]` is updated to reflect the new computed level after the effect

---

### Requirement: stat_set effect assigns an absolute value to a player stat

The `stat_set` adventure effect SHALL set a named stat to an explicit value. The `stat` field SHALL reference a stored (non-derived) stat name declared in `CharacterConfig`. **Targeting a derived stat is a content load error.** The `value` field SHALL be validated at content load time for type compatibility with the stat's declared type: `int` stats require an integer value **or a template string that resolves to an integer**; `bool` stats require a boolean value **or a template string that resolves to a boolean**. An incompatible value SHALL be a content load error.

If the new value would fall outside the stat's effective bounds, the result SHALL be clamped, a WARNING logged, and the player notified via the TUI.

After `stat_set` applies its value, the engine SHALL call `_recompute_derived_stats()` and `_fire_threshold_triggers()` for the modified stored stat.

#### Scenario: Setting an int stat to a specific value

- **WHEN** `stat_set { stat: strength, value: 15 }` is applied to a player with any `strength` value
- **THEN** `player.stats["strength"]` equals `15`

#### Scenario: Setting a bool stat toggles its value

- **WHEN** `stat_set { stat: is_blessed, value: true }` is applied
- **THEN** `player.stats["is_blessed"]` is `True`

#### Scenario: Targeting a derived stat is a load error

- **WHEN** a manifest declares `stat_set { stat: constitution_bonus, value: 5 }` and `constitution_bonus` is a derived stat
- **THEN** the content loader raises a `LoadError` identifying the adventure, step, and derived stat name

#### Scenario: Float value for int stat is a load error

- **WHEN** a manifest declares `stat_set { stat: strength, value: 1.5 }` and `strength` is an `int` stat
- **THEN** the content loader raises a `LoadError` identifying the incompatible value type

#### Scenario: String value for int stat (non-template) is a load error

- **WHEN** a manifest declares `stat_set { stat: strength, value: "hello" }` and `"hello"` contains no template syntax
- **THEN** the content loader raises a `LoadError` identifying the incompatible value type

#### Scenario: Template string for int stat is accepted and precompiled

- **WHEN** a manifest declares `stat_set { stat: strength, value: "{{ player.stats['xp'] // 10 }}" }` and `strength` is an `int` stat
- **THEN** the content loader compiles and mock-renders the template without error

#### Scenario: Template string for bool stat that resolves to non-bool raises TemplateRuntimeError

- **WHEN** a `stat_set` template for a `bool` stat resolves to `"fifteen"` at runtime
- **THEN** a `TemplateRuntimeError` is raised
