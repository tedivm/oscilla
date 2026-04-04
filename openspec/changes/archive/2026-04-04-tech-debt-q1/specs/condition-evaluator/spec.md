## REMOVED Requirements

### Requirement: Condition shorthand syntax

The condition evaluator SHALL no longer accept bare-key shorthand syntax (e.g. `{level: 3}`, `{milestone: "found-key"}`). All condition dicts MUST contain an explicit `type:` discriminator field.

**Reason:** Two syntaxes for the same construct create inconsistency across documentation, surprise for authors switching between manifest files, and ongoing maintenance burden on the normalizer. The shorthand was a convenience added before a stable authoring convention was established.

**Migration:** Replace all bare-key conditions with the explicit `type:`-tagged form:

- `{level: 3}` → `{type: level, value: 3}`
- `{milestone: "found-key"}` → `{type: milestone, name: "found-key"}`
- `{class: warrior}` → `{type: class, name: warrior}`
- For `character_stat`, `iteration`, `enemies_defeated`, `locations_visited`, `adventures_completed`, `skill`: add `type:` as an explicit field alongside the existing sub-dict keys.

A bare-key condition will produce a `LoadError` (hard error) — the content package will not load.

#### Scenario: Bare-key condition is a hard error

- **WHEN** a manifest contains a condition dict without a `type:` key (e.g. `unlock: {level: 3}`)
- **THEN** the content loader raises a `LoadError` with a message about the missing discriminator field, and the content package fails to load entirely

#### Scenario: Explicit condition still loads correctly

- **WHEN** a manifest contains a condition dict with an explicit `type:` key (e.g. `unlock: {type: level, value: 3}`)
- **THEN** the content loader accepts it as before with no change in behavior
