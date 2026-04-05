# In-Game Time Templates

## Purpose

Defines the `ingame_time` object exposed in the template `ExpressionContext`, providing read-only access to both tick counters, all cycle labels, and all era states for use in adventure narrative text and branch conditions.

## Requirements

### Requirement: ingame_time object is available in templates when time is configured

When a game manifest contains a `time:` block, the template `ExpressionContext` SHALL include an `ingame_time` object. When no `time:` block is configured, `ingame_time` SHALL be `None`. Templates MUST guard with `{% if ingame_time %}` before accessing `ingame_time` properties to remain compatible with games that do not use the time system.

#### Scenario: ingame_time is present when time is configured

- **WHEN** a game has a `time:` block and a template renders `{{ ingame_time.game_ticks }}`
- **THEN** the rendered output contains the current `game_ticks` value as a string

#### Scenario: ingame_time is None when time is not configured

- **WHEN** a game has no `time:` block and a template renders `{{ ingame_time }}`
- **THEN** the rendered output contains `"None"` (or the Jinja2 undefined representation)
- **THEN** no error is raised

---

### Requirement: ingame_time exposes both tick counters

The `ingame_time` object SHALL expose two integer fields:

- `ingame_time.internal_ticks` — the current value of `CharacterState.internal_ticks`
- `ingame_time.game_ticks` — the current value of `CharacterState.game_ticks`

#### Scenario: internal_ticks matches character state

- **WHEN** `internal_ticks = 42` and a template renders `{{ ingame_time.internal_ticks }}`
- **THEN** the rendered output contains `"42"`

#### Scenario: game_ticks matches character state

- **WHEN** `game_ticks = 117` and a template renders `{{ ingame_time.game_ticks }}`
- **THEN** the rendered output contains `"117"`

---

### Requirement: ingame_time exposes cycle labels by name

For each declared cycle (including aliases), `ingame_time.cycles["<name>"].label` SHALL return the current display label. `ingame_time.cycles["<name>"].position` SHALL return the 0-based position index.

#### Scenario: Cycle label is accessible by name

- **WHEN** a cycle `season` has labels `[Spring, Summer, Autumn, Winter]` and the current season is `"Summer"`
- **THEN** `{{ ingame_time.cycles['season'].label }}` renders as `"Summer"`

#### Scenario: Cycle position is accessible

- **WHEN** the current season is `"Summer"` (index 1)
- **THEN** `{{ ingame_time.cycles['season'].position }}` renders as `"1"`

#### Scenario: Alias resolves in template access

- **WHEN** the root cycle `hour` has alias `ship_hour` and the current label is `"Dawn"`
- **THEN** `{{ ingame_time.cycles['ship_hour'].label }}` renders as `"Dawn"`

#### Scenario: Cycle with default labels uses Name N format

- **WHEN** a cycle `tier` has `count: 5` and no `labels` declared, and the current position is 3
- **THEN** `{{ ingame_time.cycles['tier'].label }}` renders as `"tier 4"` (1-based)

---

### Requirement: ingame_time exposes era count and active state

For each declared era, `ingame_time.eras["<name>"].count` SHALL return the current counter value and `ingame_time.eras["<name>"].active` SHALL return a boolean.

#### Scenario: Era count is accessible

- **WHEN** era `CE` has `epoch_count: 1963` and 2 years have elapsed (730 ticks with 365 ticks/year)
- **THEN** `{{ ingame_time.eras['CE'].count }}` renders as `"1965"`

#### Scenario: Era active state is accessible

- **WHEN** era `new_age` is currently active
- **THEN** `{{ ingame_time.eras['new_age'].active }}` renders as `"True"`

#### Scenario: Conditional narrative uses era active state

- **WHEN** a template contains `{% if ingame_time.eras['new_age'].active %}It is the New Age.{% endif %}`
- **THEN** the phrase renders when the era is active and is absent when the era is inactive

---

### Requirement: Inline era format string renders using count

The era `format` field (e.g., `"{count} AC"`) is NOT directly rendered by the template engine as a function. The resolved era count is exposed via `ingame_time.eras["<name>"].count` and authors compose display text in the template itself using the format string pattern if desired.

> **Note for implementers**: This avoids a second template engine call inside the resolver. Authors write `{{ ingame_time.eras['CE'].count }} AC` directly in their adventure text rather than calling a formatter.

#### Scenario: Author renders era display in template

- **WHEN** era `CE` has `epoch_count: 1963` and 1 year has passed (`count = 1964`)
- **THEN** a template `Year {{ ingame_time.eras['CE'].count }} CE` renders as `"Year 1964 CE"`

---

### Requirement: ingame_time is read-only in templates

Templates SHALL NOT be able to mutate `ingame_time` fields. The `InGameTimeView` object SHALL be frozen or otherwise protected from template writes.

#### Scenario: Template cannot assign to ingame_time fields

- **WHEN** a template attempts `{% set ingame_time.game_ticks = 999 %}`
- **THEN** the template engine raises an error or silently ignores the assignment without modifying state
