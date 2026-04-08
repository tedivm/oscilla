## ADDED Requirements

### Requirement: `MilestoneRecord` model captures both time tracks at grant time

A `MilestoneRecord` Pydantic model SHALL be defined in `oscilla/engine/models/base.py` with two fields:

- `tick: int` — the `internal_ticks` value at the moment the milestone was granted.
- `timestamp: int` — the Unix timestamp (seconds, from `int(time.time())`) at the moment the milestone was granted.

### Requirement: Milestones field stores `MilestoneRecord` values

The `milestones` field on `CharacterState` SHALL be `Dict[str, MilestoneRecord]` where the key is the milestone name. `grant_milestone(name)` SHALL create a `MilestoneRecord` capturing `self.internal_ticks` and `int(time.time())` at call time. If the milestone is already held, the call SHALL be a no-op (the original record is preserved).

The `has_milestone(name)` API SHALL remain unchanged: it SHALL return True when the milestone name is a key in the dict.

Serialization SHALL produce `{"milestones": {name: {"tick": N, "timestamp": N}, ...}}` — a nested JSON object, not a list.

Deserialization SHALL support three formats for backward compatibility, all with a per-entry log warning when migrating:

1. **Old list format** `["name-a", "name-b"]` → `MilestoneRecord(tick=0, timestamp=0)` per entry. Tick=0 and timestamp=0 are the sentinels meaning "granted before tracking was introduced."
2. **Intermediate int-dict format** `{"name-a": 42}` → `MilestoneRecord(tick=42, timestamp=0)` per entry. Handles saves from a deployment using the `Dict[str, int]` design before `MilestoneRecord` was introduced.
3. **Current nested dict format** `{"name-a": {"tick": 42, "timestamp": 1744000000}}` → parsed directly as `MilestoneRecord`.

#### Scenario: Granting a milestone records both tick and timestamp

- **WHEN** `state.internal_ticks == 42` and `grant_milestone("joined-guild")` is called
- **THEN** `state.milestones["joined-guild"].tick == 42`
- **THEN** `state.milestones["joined-guild"].timestamp > 0` (a real Unix timestamp was recorded)

#### Scenario: Re-granting a milestone is a no-op

- **WHEN** `grant_milestone("joined-guild")` is called when `state.milestones["joined-guild"].tick == 10`
- **THEN** both `.tick` and `.timestamp` remain unchanged — the original record is not overwritten

#### Scenario: has_milestone works with MilestoneRecord storage

- **WHEN** `state.milestones == {"joined-guild": MilestoneRecord(tick=42, timestamp=...)}` and `has_milestone("joined-guild")` is called
- **THEN** it returns True

#### Scenario: Old list format is migrated on load

- **WHEN** `from_dict` receives `{"milestones": ["milestone-a", "milestone-b"], ...}`
- **THEN** `state.milestones["milestone-a"] == MilestoneRecord(tick=0, timestamp=0)` after deserialization
- **THEN** a warning is logged per migrated milestone entry

#### Scenario: Intermediate int-dict format is migrated on load

- **WHEN** `from_dict` receives `{"milestones": {"veteran": 100}, ...}` (int value, not dict)
- **THEN** `state.milestones["veteran"] == MilestoneRecord(tick=100, timestamp=0)` after deserialization
- **THEN** a warning is logged per migrated milestone entry

#### Scenario: New nested dict format loads correctly

- **WHEN** `from_dict` receives `{"milestones": {"veteran": {"tick": 100, "timestamp": 1744000000}}, ...}`
- **THEN** `state.milestones["veteran"] == MilestoneRecord(tick=100, timestamp=1744000000)` after deserialization

#### Scenario: Serialized milestones are a nested JSON object

- **WHEN** `state.to_dict()` is called on a player with milestones
- **THEN** the `"milestones"` key maps to `{name: {"tick": N, "timestamp": N}}`, not a list
