# Skill Revoke

## Purpose

The `skill_revoke` effect permanently removes a learned skill from a character's `known_skills`. It is the counterpart to `skill_grant` and is most commonly used in archetype `lose_effects` blocks to take back skills that were granted when an archetype was applied.

---

## Requirements

### Requirement: skill_revoke effect type

The `skill_revoke` effect SHALL remove a named skill from `CharacterState.known_skills`. If the skill is not present in `known_skills`, the effect SHALL be a no-op (no error). The `skill_revoke` effect is valid in any effect context: adventure steps, archetype `lose_effects`, quest `fail_effects`, or any other location where effects are accepted.

Fields:

- `type: "skill_revoke"` (discriminator)
- `skill` (string, required): skill manifest name to remove.

#### Scenario: skill_revoke removes a known skill

- **WHEN** a `skill_revoke: {skill: basic-combat}` effect is dispatched for a character who has `"basic-combat"` in `known_skills`
- **THEN** `"basic-combat"` is removed from `CharacterState.known_skills`

#### Scenario: skill_revoke is a no-op when skill is not known

- **WHEN** a `skill_revoke: {skill: basic-combat}` effect is dispatched for a character who does not have `"basic-combat"` in `known_skills`
- **THEN** `CharacterState.known_skills` is unchanged and no error is raised

#### Scenario: skill_revoke in archetype lose_effects fires on archetype removal

- **WHEN** an `archetype_remove: {name: warrior}` effect is dispatched for a character holding `"warrior"`, and the `warrior` archetype's `lose_effects` contains `skill_revoke: {skill: basic-combat}`, and the character has `"basic-combat"` in `known_skills`
- **THEN** `"basic-combat"` is removed from `CharacterState.known_skills` as part of the archetype removal

#### Scenario: skill_revoke does not affect passively-granted skills

- **WHEN** a `skill_revoke: {skill: tracking}` effect is dispatched for a character who does not have `"tracking"` in `known_skills` but has it available via a passive effect
- **THEN** `known_skills` is unchanged (passive skill grants are not in `known_skills`); the skill remains available from the passive source
