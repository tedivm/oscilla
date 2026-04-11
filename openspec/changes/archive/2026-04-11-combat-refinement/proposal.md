# Proposal: Combat Refinement

## Why

Buffs currently have no mechanism to prevent weaker duplicates from stacking when a stronger version is already active, and they are strictly ephemeral — discarded at combat end — which prevents authors from writing status effects that carry through a full adventure or survive across multiple encounters. Both gaps limit combat expressiveness without requiring changes to unrelated engine systems.

## What Changes

- **New**: `exclusion_group` and `priority` fields on `BuffSpec` — when a buff is applied, any existing active effect in the same group with equal or higher priority blocks the new application.
- **New**: `BuffDuration` model replaces `BuffSpec.duration_turns: int` — a single structured duration object that controls both combat-turn lifespan and optional cross-combat persistence using the same tick/second/game-tick vocabulary the rest of the engine already uses.
- **New**: `CharacterState.active_buffs` — a list of stored buff entries tracking persistent and adventure-scoped buffs between combat encounters; persisted to the database.
- **New**: DB migration adding `character_iteration_active_buffs` table.
- **New**: `DispelEffect` gains a `permanent` flag — when true, the dispel removes a stored buff from `CharacterState` entirely, not just from the current `CombatContext`.
- **BREAKING**: `BuffSpec.duration_turns: int` replaced by `BuffSpec.duration: BuffDuration`. Any existing content with `duration_turns:` must be updated to `duration: {turns: N}`.

## Capabilities

### New Capabilities

- `buff-blocking`: Exclusion groups and priority fields on `BuffSpec` that prevent lower-priority buffs in the same group from being applied while a higher-priority instance is already active.
- `buff-persistence`: Extension to the buff lifecycle that allows buffs to survive combat end, persist across multiple encounters within an adventure, or remain active across adventures until a Cooldown-style duration expires.

### Modified Capabilities

- `combat-skills`: `BuffSpec.duration_turns` replaced by `BuffSpec.duration: BuffDuration`; `DispelEffect` gains `permanent: bool = False`.

## Impact

- `oscilla/engine/models/buff.py` — `BuffSpec`, `ActiveCombatEffect` (via `combat_context.py`)
- `oscilla/engine/combat_context.py` — `ActiveCombatEffect` gains `exclusion_group`, `priority`, and `is_persistent` flag
- `oscilla/engine/steps/effects.py` — `apply_buff` handler gains exclusion check; `dispel` handler gains permanent removal path
- `oscilla/engine/steps/combat.py` — `run_combat()` entry loads `active_buffs` from `CharacterState`; combat exit writes back updated remaining turns for persistent effects
- `oscilla/engine/character.py` — `CharacterState` gains `active_buffs: List[StoredBuff]`; `to_dict`/`from_dict` updated; adventure-end sweep added
- `oscilla/services/character.py` — `save_character` / `load_character` handle new `active_buffs` table
- `db/versions/` — new Alembic migration for `character_iteration_active_buffs` table
- `docs/authors/skills.md` — `BuffSpec` fields table updated; new sections for blocking and persistence
- `docs/authors/effects.md` — `apply_buff` and `dispel` entries updated
