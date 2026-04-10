## ADDED Requirements

### Requirement: archetype_add effect type

The `archetype_add` effect SHALL add a named archetype to `CharacterState.archetypes` (recording the current `internal_ticks` and wall-clock timestamp as a `GrantRecord`) and dispatch the archetype's `gain_effects`. It SHALL be idempotent by default: if the archetype is already held, neither the record update nor `gain_effects` dispatch occurs unless `force: true`.

Fields:

- `type: "archetype_add"` (discriminator)
- `name` (string, required): archetype manifest name to add.
- `force` (bool, optional, default `false`): when `true`, dispatches `gain_effects` and updates `archetypes` even if the archetype is already held.

#### Scenario: archetype_add adds archetype to character state

- **WHEN** an `archetype_add: {name: warrior}` effect is dispatched for a character who does not hold `"warrior"`
- **THEN** `"warrior"` is added to `CharacterState.archetypes`
- **AND** the `warrior` archetype's `gain_effects` are dispatched

#### Scenario: archetype_add is idempotent by default

- **WHEN** an `archetype_add: {name: warrior}` effect is dispatched for a character who already holds `"warrior"` and `force` is false (default)
- **THEN** `"warrior"` remains in `CharacterState.archetypes` and `gain_effects` are NOT dispatched again

#### Scenario: archetype_add with force=true re-dispatches gain_effects

- **WHEN** an `archetype_add: {name: warrior, force: true}` effect is dispatched for a character who already holds `"warrior"`
- **THEN** `"warrior"` remains in `CharacterState.archetypes` and `gain_effects` ARE dispatched again

---

### Requirement: archetype_remove effect type

The `archetype_remove` effect SHALL remove a named archetype from `CharacterState.archetypes` and dispatch the archetype's `lose_effects`. It SHALL be idempotent by default: if the archetype is not held, neither the record removal nor `lose_effects` dispatch occurs unless `force: true`.

Fields:

- `type: "archetype_remove"` (discriminator)
- `name` (string, required): archetype manifest name to remove.
- `force` (bool, optional, default `false`): when `true`, dispatches `lose_effects` even if the archetype is not currently held.

#### Scenario: archetype_remove removes archetype from character state

- **WHEN** an `archetype_remove: {name: warrior}` effect is dispatched for a character who holds `"warrior"`
- **THEN** `"warrior"` is removed from `CharacterState.archetypes`
- **AND** the `warrior` archetype's `lose_effects` are dispatched

#### Scenario: archetype_remove is idempotent by default

- **WHEN** an `archetype_remove: {name: warrior}` effect is dispatched for a character who does not hold `"warrior"` and `force` is false (default)
- **THEN** `CharacterState.archetypes` is unchanged and `lose_effects` are NOT dispatched

#### Scenario: archetype_remove with force=true dispatches lose_effects even when not held

- **WHEN** an `archetype_remove: {name: warrior, force: true}` effect is dispatched for a character who does not hold `"warrior"`
- **THEN** `lose_effects` ARE dispatched and `CharacterState.archetypes` remains unchanged (pop on a missing key is a no-op)
