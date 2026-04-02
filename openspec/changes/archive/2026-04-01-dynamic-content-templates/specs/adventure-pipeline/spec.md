## ADDED Requirements

### Requirement: AdventurePipeline constructs ExpressionContext before executing steps

Before executing any step, `AdventurePipeline` SHALL construct an `ExpressionContext` from the current `CharacterState`. The context SHALL be passed to all step handlers and to `_run_effects()`. The context SHALL be reconstructed whenever player state changes between steps so that templates always see current values.

#### Scenario: Context is fresh when a step runs after a stat change

- **WHEN** step N applies a `stat_change` and step N+1 contains `{{ player.stats['gold'] }}`
- **THEN** step N+1's template sees the updated gold value, not the pre-step-N value

---

### Requirement: NarrativeStep text field supports template strings

When a `NarrativeStep.text` is a template string (contains `{{`, `{%`, or a pronoun placeholder), the pipeline SHALL render it through the `GameTemplateEngine` before passing to the TUI. Plain strings SHALL be passed directly without engine overhead.

#### Scenario: Template text is rendered before display

- **WHEN** a `NarrativeStep` has `text: "Welcome, {{ player.name }}."` and the player's name is `"Jordan"`
- **THEN** the TUI receives the string `"Welcome, Jordan."` — not the raw template

#### Scenario: Plain text is not modified

- **WHEN** a `NarrativeStep` has `text: "You enter the tavern."` (no template syntax)
- **THEN** the TUI receives exactly `"You enter the tavern."`

---

### Requirement: Effect numeric fields accept template strings that resolve to integers

`xp_grant.amount`, `stat_change.amount`, and `item_drop.count` SHALL accept either a literal integer or a template string. When the field is a template string, the effect dispatcher SHALL render it through `GameTemplateEngine.render_int()` before applying the effect. The rendered value MUST be a non-fractional integer; a render result that cannot be parsed as `int` SHALL raise a `TemplateRuntimeError`.

#### Scenario: Template amount renders to correct integer

- **WHEN** `xp_grant { amount: "{{ player.level * 50 }}" }` is applied for a level-3 player
- **THEN** the player gains 150 XP

#### Scenario: Non-integer template amount raises TemplateRuntimeError

- **WHEN** a template `amount` resolves to `"fifteen"` at runtime
- **THEN** a `TemplateRuntimeError` is raised with the resolved value and template ID in the message

#### Scenario: roll() in amount produces value in expected range

- **WHEN** `stat_change { stat: gold, amount: "{{ roll(5, 15) }}" }` is applied
- **THEN** `gold` increases by an integer between 5 and 15 inclusive
