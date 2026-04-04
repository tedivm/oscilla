## ADDED Requirements

### Requirement: Pipeline executes passive steps

The adventure pipeline SHALL support `type: passive` steps. When a passive step is encountered during adventure execution, the pipeline SHALL call `run_passive()`, which evaluates the bypass condition (if any), shows the appropriate text, and applies effects. The passive step's outcome is always `completed` — it does not terminate the adventure unless an `end_adventure` effect is included in its effects list.
