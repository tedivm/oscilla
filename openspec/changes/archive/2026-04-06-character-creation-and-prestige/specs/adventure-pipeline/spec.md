## ADDED Requirements

### Requirement: PrestigeEffect in the effect union

The effect union SHALL include a `prestige` effect type represented by `PrestigeEffect(type: Literal["prestige"])`. When dispatched by `run_effect()`:

1. If `registry.game.spec.prestige` is `None`, the handler SHALL log an error, display an error message via `tui.show_text()`, and return without modifying player state.
2. Otherwise the handler SHALL execute the full prestige pipeline as defined in the prestige-system spec: run `pre_prestige_effects`, snapshot carry values, reset in-memory character state to config defaults, apply carry-forward, increment `prestige_count`, run `post_prestige_effects`, and set `player.prestige_pending`.

Steps that appear after a `prestige` effect in the same adventure SHALL execute normally using the reset in-memory state. The DB transition is deferred to `adventure_end`.

#### Scenario: Prestige effect resets state in-memory

- **WHEN** a `type: prestige` effect step is dispatched for a player at level 5
- **THEN** after the handler returns, `player.level == 1` and `player.prestige_count` is one greater than before

#### Scenario: Prestige effect sets prestige_pending

- **WHEN** a `type: prestige` effect fires with a valid prestige config
- **THEN** `player.prestige_pending is not None` after the handler returns

#### Scenario: Prestige effect without prestige config is a no-op

- **WHEN** a `type: prestige` effect fires and `registry.game.spec.prestige is None`
- **THEN** player state is unchanged and `player.prestige_pending` remains `None`

#### Scenario: Steps after prestige see reset state

- **WHEN** an adventure has a `prestige` effect step followed by a `narrative` step whose text references `{{ player.prestige_count }}`
- **THEN** the narrative renders with the new (incremented) prestige_count value

### Requirement: PrestigeEffect requires game.yaml prestige block — hard error when absent

At content load time, the engine SHALL inspect every adventure manifest for `PrestigeEffect` steps. If any such step is found and the game's `prestige:` block is absent, a `LoadError` SHALL be appended for that adventure and the content load SHALL fail with `ContentLoadError`. The `type: prestige` effect is only valid in packages that declare a `prestige:` block in `game.yaml`.

#### Scenario: Hard load error for unconfigured prestige effect

- **WHEN** an adventure manifest contains `type: prestige` and `game.yaml` has no `prestige:` block
- **THEN** `ContentLoadError` is raised and the content package fails to load

#### Scenario: No error when prestige block is declared

- **WHEN** an adventure manifest contains `type: prestige` and `game.yaml` declares a `prestige:` block
- **THEN** the content loads without error
