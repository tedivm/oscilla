## ADDED Requirements

### Requirement: Template strings are valid values in string-typed manifest fields

Any manifest field with a declared type of `str` SHALL accept Jinja2 template syntax as its value. The loader SHALL detect template strings by the presence of `{{`, `{%`, or a pronoun/verb placeholder pattern (`{word}` where `word` is a known pronoun or verb). Detected template strings SHALL be preprocessed (pronoun placeholder substitution), compiled into a `jinja2.Template`, and stored in the `GameTemplateEngine` cache keyed by a stable template identifier path. Template compilation and mock-render validation SHALL occur as part of `load()` after all existing parse and cross-reference validations pass.

#### Scenario: Template string in NarrativeStep text field is accepted

- **WHEN** an `Adventure` manifest has `text: "{{ player.name }} received the reward."`
- **THEN** `load()` compiles the template and stores it without error

#### Scenario: Template string with unknown player property fails load

- **WHEN** an `Adventure` manifest has `text: "{{ player.notarealfield }}"`
- **THEN** `load()` raises a `ContentLoadError` before returning the registry

---

### Requirement: CharacterConfig manifest may declare additional pronoun sets

The `CharacterConfig` manifest SHALL accept an optional `extra_pronoun_sets` list. Each entry SHALL be validated for required fields (`name`, `display_name`, all five pronoun form strings, `uses_plural_verbs`). A `name` that conflicts with a built-in set (`they_them`, `she_her`, `he_him`) SHALL be a content load error.

#### Scenario: Valid extra pronoun set in CharacterConfig loads without error

- **WHEN** `CharacterConfig` declares `extra_pronoun_sets: [{name: xe_xir, ...}]` with all required fields
- **THEN** `load()` completes without error

#### Scenario: Extra pronoun set with conflict name is a load error

- **WHEN** `CharacterConfig` declares `extra_pronoun_sets: [{name: she_her, ...}]`
- **THEN** `load()` raises a `ContentLoadError` identifying the conflict

---

### Requirement: Template validation errors are reported as ContentLoadErrors

`TemplateValidationError`s SHALL be collected and raised as a `ContentLoadError` with the same formatting and structure as schema and reference validation errors. The error message SHALL include the template identifier path (e.g. `adventure-name:step[0].text`) and a human-readable description of the failure.

#### Scenario: Multiple template errors are reported together

- **WHEN** a game package has three adventures each with one invalid template
- **THEN** `load()` raises a single `ContentLoadError` listing all three template errors

#### Scenario: oscilla validate reports template errors

- **WHEN** `oscilla validate --game mygame` is run on a package with template errors
- **THEN** the command exits with a non-zero code and prints each template error with its path
