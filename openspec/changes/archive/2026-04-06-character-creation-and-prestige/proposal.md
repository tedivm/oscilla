## Why

The triggered adventures system introduced `on_character_create`, `on_stat_threshold`, and `emit_trigger` — exactly the hooks needed for character creation flows and prestige resets — but the two features remain unwired at the authoring level. This change activates both: first by documenting and demonstrating `on_character_create` as a first-class authoring tool, then by adding the `prestige` effect and the supporting `game.yaml` configuration that turns iteration resets into a fully authored game mechanic.

A secondary motivation is a naming inconsistency introduced before either feature was used: `PrestigeCountCondition` uses `type: "iteration"` in YAML but the spec and all documentation call it `prestige_count`. Fixing this now, before any content packages write prestige conditions, is low cost and high clarity.

## What Changes

**Phase 1 — Character Creation Flow**

- Fix naming bug: `PrestigeCountCondition.type` YAML key changes from `"iteration"` to `"prestige_count"`. `CharacterState.iteration` field is renamed to `prestige_count`. All serialization, persistence, and condition evaluation is updated to match.
- Document `on_character_create` as a content authoring tool in `docs/authors/adventures.md` and the triggered-adventures author documentation.
- Add `SetNameEffect` (`type: set_name`) to the Effect union. When dispatched, it prompts the player for a name via `tui.input_text()` and updates `CharacterState.name`. `_create_new_character()` is updated to use a unique placeholder name (e.g. `f"new-{uuid4()}"`) instead of blocking on a TUI prompt, allowing the name-collection step to live inside the character-creation adventure like pronoun selection.
- `_persist_diff` gains a name-change detection path: when `state.name` differs from the last-saved name, a new `rename_character()` service call updates `CharacterRecord.name` in the DB while enforcing the unique constraint.
- Add `CharacterCreationDefaults` block to `GameSpec` (declared in `game.yaml` under `character_creation:`). Authors can set `default_name` (a fixed protagonist name that bypasses the `SetNameEffect` prompt) and `default_pronouns` (an initial pronoun set key that skips the need for a `set_pronouns` step). This enables biographic games where the protagonist is pre-defined and no player selection is needed.
- Add testlandia `character-creation` adventure that demonstrates: name input, pronoun selection, backstory stat choice, and opening narrative.

**Phase 2 — Prestige System**

- Add `prestige` block to `GameSpec` in `game.yaml`: declares `carry_stats`, `carry_skills`, `pre_prestige_effects`, and `post_prestige_effects`.
- Add `PrestigeEffect` (`type: prestige`) to the Effect union. When dispatched, it applies `pre_prestige_effects`, resets character state to config defaults, carries forward declared stats and skills, increments `prestige_count`, then applies `post_prestige_effects`.
- The actual DB iteration transition (closing the old `character_iterations` row, opening a new one) is deferred to `adventure_end` persist via an ephemeral `prestige_pending` field on `CharacterState`, preserving in-adventure continuity — steps after the prestige effect see the reset state immediately.
- `prestige_character()` service function is updated to accept carry-forward data.
- Add `prestige_count` to the template context so authors can reference `{{ player.prestige_count }}` in narrative text.
- Condition evaluator `prestige_count` predicate is already spec'd and implemented (once the naming bug is fixed).
- Add testlandia content: stat threshold at level 5 fires a prestige adventure, carrying `legacy_power` stat forward, with post-prestige content gated by `prestige_count: {gte: 1}`.

**Out of scope (added to roadmap):**

- Cross-iteration conditions (e.g., "milestone ever reached in any past iteration") — requires a new query surface over `character_iterations` history.
- Cross-iteration template expressions (e.g., `{{ player.past_iterations | length }}`).
- Cross-iteration effects (e.g., carry milestones, aggregate stats from previous runs).

## Capabilities

### New Capabilities

- `prestige-system`: The `prestige` block in `game.yaml`, the `PrestigeEffect`, and the in-session prestige execution path including carry-forward for stats and skills.

### Modified Capabilities

- `condition-evaluator`: Fix `prestige_count` YAML type key (was `"iteration"`). Requirement wording updated.
- `player-state`: Rename `iteration` field to `prestige_count` on `CharacterState` and update all serialization.
- `player-persistence`: Update `prestige_character()` signature; update `_persist_diff` to handle `prestige_pending` transition at `adventure_end` and to detect name changes, calling `rename_character()` when needed.
- `adventure-pipeline`: `PrestigeEffect` and `SetNameEffect` added to the Effect union and dispatched through `run_effect()`.
- `game-session`: `_create_new_character()` uses a placeholder name (or game-declared default name) and skips the TUI name prompt; `rename_character()` service function added to `services/character.py`.
- `triggered-adventures`: Document `on_character_create` usage pattern.
- `game-configuration`: `GameSpec` gains `character_creation: CharacterCreationDefaults | None`; `new_character()` reads `default_pronouns` from this block to initialize `CharacterState.pronouns`.

## Impact

- **Breaking (internal only, no existing content packages use prestige):** `PrestigeCountCondition.type` YAML key changes from `"iteration"` to `"prestige_count"`. Any test or content using `type: iteration` must be updated.
- `CharacterState.iteration` → `CharacterState.prestige_count` rename touches: `character.py`, `session.py`, `conditions.py`, serialization paths, and all tests referencing `.iteration`.
- `game.yaml` gains an optional `prestige:` top-level block. Games without it behave identically.
- `prestige_character()` in `services/character.py` gains a `carry_forward` parameter (optional, defaults to no carry-forward — backward-compatible).
- `_create_new_character()` in `session.py` no longer blocks on a TUI name prompt; it uses a game-declared default name or a unique placeholder so character creation starts immediately and name collection happens inside the creation adventure.
- `CharacterRecord.name` is now mutable post-creation via `rename_character()`. The unique constraint `(user_id, game_name, name)` is enforced at rename time.
- `game.yaml` gains an optional `character_creation:` block with `default_name` and `default_pronouns`. Games without it default to UUID placeholder names and `they/them` pronouns as before.
- Testlandia `game.yaml` and `character_config.yaml` are updated to define the `legacy_power` stat, stat threshold trigger, and prestige block.

## Testlandia Updates

**Phase 1 — character-creation adventure:**

- New file: `content/testlandia/adventures/character-creation.yaml`
  - Triggers on `on_character_create`
  - Step 1 (new characters only): `type: set_name` effect prompts the player for their name
  - Step 2 (new characters only): choice for pronoun set (they/them, she/her, he/him)
  - Step 3 (new characters only): choice for backstory (`cunning +1` or reputation/backstory)
  - Returning players (prestige re-entry) see a brief legacy acknowledgment instead
  - Closing narrative step uses `{they}` pronouns and `{{ player.stats.cunning }}` template

**Phase 2 — prestige content:**

- Update `content/testlandia/game.yaml`:
  - Add stat threshold trigger: `level 5 → "max-level-reached"`
  - Wire `trigger_adventures: {max-level-reached: [prestige-ceremony]}`
  - Add `prestige:` block with `carry_stats: [legacy_power]`, `pre_prestige_effects: [{type: stat_change, stat: legacy_power, amount: 1}]`
- Update `content/testlandia/character_config.yaml`:
  - Add `legacy_power` stat (int, default 0, hidden)
- New file: `content/testlandia/adventures/prestige-ceremony.yaml`
  - Narrative step acknowledging the character's journey
  - `pre_prestige_effects` grants `legacy_power +1` (handled by game.yaml, not inline)
  - `type: prestige` effect
  - Post-prestige narrative step using `{{ player.prestige_count }}`
- Update existing testlandia region/location to gate one adventure behind `prestige_count: {gte: 1}`
