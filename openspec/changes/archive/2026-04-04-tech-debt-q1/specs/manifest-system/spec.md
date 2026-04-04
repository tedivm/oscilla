## REMOVED Requirements

### Requirement: base_adventure_count field on GameSpec

The `base_adventure_count` field SHALL be removed from `GameSpec`. Content packages that declare this field will receive a Pydantic validation error at load time if `extra = "forbid"` is configured, or it will be silently ignored if `extra = "ignore"` is in effect. Content authors must remove the field from their `game.yaml` to keep their manifests clean and avoid confusion.

**Reason:** The field was never read by any engine code. It implied a per-session adventure cap feature that does not exist and was not planned for the current roadmap. Keeping it creates a misleading promise to authors and unnecessarily inflates the `GameSpec` schema.

**Migration:** Remove `base_adventure_count:` from `game.yaml` in any content package that declares it.

#### Scenario: game.yaml without base_adventure_count loads successfully

- **WHEN** a `game.yaml` omits the `base_adventure_count` field
- **THEN** the content loads without error
