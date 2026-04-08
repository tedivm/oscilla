## ADDED Requirements

### Requirement: Time constant identifiers available in all template contexts

The following integer constants SHALL be available in all template evaluation contexts (`SAFE_GLOBALS`):

| Identifier           | Value  | Meaning                      |
| -------------------- | ------ | ---------------------------- |
| `SECONDS_PER_MINUTE` | 60     | Seconds in one minute        |
| `SECONDS_PER_HOUR`   | 3600   | Seconds in one hour          |
| `SECONDS_PER_DAY`    | 86400  | Seconds in one day           |
| `SECONDS_PER_WEEK`   | 604800 | Seconds in one week (7 days) |

These constants SHALL be usable in any template expression including cooldown fields, narrative text, stat-check expressions, and effect amounts.

They SHALL be included in the mock context used at load-time template validation so that manifests using them do not produce false load errors.

#### Scenario: SECONDS_PER_DAY resolves in a cooldown expression

- **WHEN** `cooldown: {seconds: "{{ SECONDS_PER_DAY }}"}` is evaluated
- **THEN** it resolves to 86400

#### Scenario: Constants can be composed in arithmetic

- **WHEN** a skill or adventure uses `cooldown: {seconds: "{{ SECONDS_PER_HOUR * 6 }}"}`
- **THEN** the resolved value is 21600

#### Scenario: Constants available in narrative text

- **WHEN** a narrative step text is `"You must wait {{ SECONDS_PER_DAY // 3600 }} hours."`
- **THEN** it renders as "You must wait 24 hours."

#### Scenario: Constants do not cause load-time validation errors

- **WHEN** a manifest template uses `SECONDS_PER_WEEK` or any other time constant
- **THEN** the load-time mock render succeeds without raising a TemplateValidationError
