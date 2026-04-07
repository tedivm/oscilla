## ADDED Requirements

### Requirement: on_character_create is documented as a first-class authoring tool

`docs/authors/adventures.md` SHALL include a dedicated section on `on_character_create` covering: how to declare it in `game.yaml` under `trigger_adventures`, when it fires (immediately after character creation, before the world map appears), the fact that the adventure runs like any other — with choice steps, narrative steps, stat changes, and pronoun selection — and that omitting the wiring means creation is silent. A complete example adventure demonstrating pronoun selection and a backstory stat bonus SHALL be included.

#### Scenario: Author can find on_character_create documentation

- **WHEN** an author reads `docs/authors/adventures.md`
- **THEN** they find a section explaining `on_character_create` with a working example adventure YAML

#### Scenario: Pronoun selection example is present

- **WHEN** the character-creation documentation section is rendered
- **THEN** it contains a concrete adventure manifest snippet showing a `set_pronouns` choice step

### Requirement: Testlandia demonstrates on_character_create end-to-end

The testlandia content package SHALL include a wired `on_character_create` adventure that demonstrates: pronoun selection via a `set_pronouns` effect, a backstory stat choice, and a closing narrative step that uses a pronouns template tag and a `{{ player.stats. }}` expression. The `game.yaml` SHALL wire `trigger_adventures: {on_character_create: [character-creation]}`.

#### Scenario: Testlandia character-creation adventure passes content validation

- **WHEN** `oscilla content test` is run against the testlandia package
- **THEN** the `character-creation` adventure validates without errors

#### Scenario: Testlandia character-creation adventure loads in the test suite

- **WHEN** the test suite runs `test_cli_content.py` against testlandia
- **THEN** the `character-creation` adventure is present in the loaded registry with at least 3 steps
