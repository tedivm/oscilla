## Why

Adventures are currently player-driven: the player navigates to a location and a weighted-random adventure from the pool is selected. There is no mechanism for the engine to automatically fire an adventure in response to a lifecycle event — character creation, leveling up, defeat, a stat crossing a threshold, or a custom event emitted by content. This forces authors to work around the limitation with location-gated one-shots, gives no natural hook for character creation flows, and cannot model "after-death" scenes without complex content tricks.

## What Changes

- `game.yaml` gains a `triggers` block and a `trigger_adventures` block that together wire lifecycle events to ordered lists of adventures.
- Five built-in trigger types are recognized by the engine: `on_character_create`, `on_level_up`, `on_game_rejoin`, `on_stat_threshold`, and `on_outcome_<name>` (one per valid outcome name — built-in or custom).
- A new `emit_trigger` effect allows any adventure step to fire a named custom trigger declared in `game.yaml`.
- `CharacterState` gains a `pending_triggers` FIFO queue. When a detection point fires, the trigger name is appended to the queue. After each adventure completes (and on session start for `on_character_create` / `on_game_rejoin`), the game loop drains the queue by running each registered adventure in declaration order.
- The trigger queue is persisted to the database so queued triggers survive session disconnects.
- The existing condition system (`requires`) applies to triggered adventures exactly as it does to pool adventures — a triggered adventure that does not meet its conditions is skipped.
- Region/location-scoped triggers are explicitly out of scope for v1; all triggers declared in `game.yaml` apply globally.

## Capabilities

### New Capabilities

- `triggered-adventures`: The trigger system, including `game.yaml` schema additions (`triggers` + `trigger_adventures`), the FIFO queue on `CharacterState`, queue persistence, drain logic in `GameSession`, detection points for each trigger type, and the `emit_trigger` effect.

### Modified Capabilities

- `adventure-pipeline`: The `AdventurePipeline` exposes a way for triggered adventures to be run by the session loop using the same mechanism as pool adventures — no new pipeline kind needed, but the session drain logic must be able to call `run_adventure` for triggered entries.
- `player-state`: `CharacterState` gains `pending_triggers: List[str]` persisted alongside other character state fields.
- `game-session`: `GameSession` gains `drain_trigger_queue()` called at defined session lifecycle points.

## Impact

- `oscilla/engine/models/game.py` — `GameSpec` gains `triggers` and `trigger_adventures` fields
- `oscilla/engine/character.py` — `CharacterState` gains `pending_triggers: List[str]`
- `oscilla/engine/session.py` — `GameSession` gains `drain_trigger_queue()` and detection point calls
- `oscilla/engine/steps/effects.py` — new `emit_trigger` effect handler
- `oscilla/engine/models/effects.py` — new `EmitTriggerEffect` type
- `oscilla/engine/registry.py` — trigger index built at content load time
- `oscilla/engine/loader.py` — validation of `trigger_adventures` keys against known outcomes and custom trigger names
- `oscilla/services/character.py` — `pending_triggers` persistence
- `db/versions/` — migration creating `character_iteration_pending_triggers` table
- `docs/authors/game-configuration.md` — document `triggers` and `trigger_adventures` blocks
- `docs/authors/effects.md` — document `emit_trigger` effect
- `docs/dev/game-engine.md` — document trigger queue lifecycle and detection points
- `content/testlandia/` — new triggered adventure manifests demonstrating all trigger types

## Testlandia QA Content

The following testlandia content will be added to allow manual QA of all trigger types:

- **`on_character_create`**: A one-shot adventure `test-character-intro` that fires on new character creation, presents a choice to pick a starting bonus (stat boost A or B), and confirms the choice takes effect.
- **`on_level_up`**: A repeatable adventure `test-level-up-scene` that fires each time the player levels up, displaying the new level and granting a small stat bonus.
- **`on_outcome_defeated`**: A one-shot adventure `test-defeat-scene` that fires after any defeat, displaying a narrative recovery scene.
- **`on_stat_threshold`**: A one-shot adventure `test-threshold-scene` that fires when a tracked testlandia stat crosses a defined threshold, confirming the trigger fires exactly once.
- **`emit_trigger`** / custom trigger: An existing testlandia adventure gains an `emit_trigger` effect for a new custom trigger `test-custom-event`, wired to adventure `test-custom-trigger-scene` that confirms receipt.
- **`on_game_rejoin`**: A `test-rejoin-scene` wired to the `on_game_rejoin` trigger with a short absence threshold (configurable in testlandia `game.yaml`) to make it easy to test manually.
