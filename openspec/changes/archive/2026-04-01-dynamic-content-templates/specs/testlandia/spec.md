## ADDED Requirements

### Requirement: Testlandia includes a template system QA region

Testlandia SHALL contain a `template-system` region that allows a developer to manually exercise every major dynamic content template feature. The region SHALL contain the following locations and adventures:

| Location | Adventure | Feature exercised |
|---|---|---|
| `pronoun-selection` | `choose-pronouns` | Pronoun set selection (all three built-ins shown as choices) |
| `narrative-test` | `personalized-greeting` | `{{ player.name }}`, `{{ player.level }}`, `{they}`, `{their}`, `{is}` |
| `variable-rewards` | `treasure-hunt` | `roll()` in `xp_grant.amount` and `stat_change.amount`; variable reward text |
| `conditional-narrative` | `fame-check` | `{% if player.milestones.has(...) %}` branching narrative |

The region SHALL load cleanly with `oscilla validate --game testlandia` and SHALL exercise all major template features when played by a developer.

#### Scenario: Template system region loads without errors

- **WHEN** `oscilla validate --game testlandia` is run after adding the template-system region
- **THEN** the command exits with code 0

#### Scenario: Personalized greeting displays correct pronoun for she/her player

- **WHEN** a developer sets pronouns to she/her and plays `personalized-greeting`
- **THEN** the narrative text uses `"she"`, `"her"`, and `"is"` correctly

#### Scenario: Personalized greeting displays correct pronoun for they/them player

- **WHEN** a developer plays `personalized-greeting` with they/them pronouns
- **THEN** the narrative text uses `"they"`, `"their"`, and `"are"` correctly

#### Scenario: Treasure hunt grants variable XP on each play

- **WHEN** a developer plays `treasure-hunt` multiple times
- **THEN** the XP reward varies across plays (confirming `roll()` is active)

#### Scenario: Fame check branches on milestone presence

- **WHEN** a developer with the `hero-of-testlandia` milestone plays `fame-check`
- **THEN** the hero narrative branch is displayed

#### Scenario: Fame check shows default branch without milestone

- **WHEN** a developer without the `hero-of-testlandia` milestone plays `fame-check`
- **THEN** the standard narrative branch is displayed

---

### Requirement: Testlandia CharacterConfig declares they/them as default pronoun set

The Testlandia `character_config.yaml` SHALL NOT declare custom `extra_pronoun_sets` (the three built-in sets are sufficient). New Testlandia characters SHALL default to the `they_them` pronoun set.

#### Scenario: New Testlandia character has they/them pronouns by default

- **WHEN** a new character is created in Testlandia
- **THEN** `character.pronouns` is the `they_them` built-in set
