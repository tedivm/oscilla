## MODIFIED Requirements

### Requirement: TUICallbacks protocol is renamed to UICallbacks

The `TUICallbacks` Protocol class in `oscilla/engine/pipeline.py` SHALL be renamed to `UICallbacks`. All type hint references across the engine SHALL be updated. The rename is mechanical — no method signatures change.

Files affected:

- `oscilla/engine/pipeline.py` — Protocol class definition and `AdventurePipeline.__init__` parameter
- `oscilla/engine/steps/choice.py`, `steps/combat.py`, `steps/effects.py`, `steps/narrative.py`, `steps/passive.py` — import and `tui:` parameter annotations
- `oscilla/engine/quest_engine.py` — import and `tui:` parameter annotations
- `oscilla/engine/session.py` — import in TYPE_CHECKING block
- `oscilla/engine/actions.py` — import in TYPE_CHECKING block
- `tests/engine/conftest.py` — `MockTUI` docstring reference

No method signatures on `UICallbacks` change. The rename is verified by `make mypy_check` returning zero errors after the change.

#### Scenario: No TUICallbacks references remain in non-archive source files

- **WHEN** `make mypy_check` is run after the rename
- **THEN** zero type errors are reported
- **AND** no `.py` file outside `openspec/changes/archive/` contains the string `TUICallbacks`

#### Scenario: Existing TUI and engine tests pass after rename

- **WHEN** `make pytest` is run after the rename
- **THEN** all engine and TUI tests continue to pass with zero failures
