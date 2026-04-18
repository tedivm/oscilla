# Custom Condition Evaluator

## Purpose

Extends the condition evaluator to resolve `CustomConditionRef` leaves by looking up the named `CustomCondition` manifest in the `ContentRegistry` and recursively evaluating its inner condition.

---

## Requirements

### Requirement: `evaluate()` resolves `CustomConditionRef` via the registry

When the condition evaluator encounters a `CustomConditionRef`, it SHALL:

1. Check that `registry` is not `None`. If it is, emit a warning and return `False`.
2. Look up the `name` in `registry.custom_conditions`. If not found, emit a warning and return `False`.
3. If found, recursively call `evaluate(manifest.spec.condition, player, registry=registry)` and return its result.

The `CustomConditionRef` arm SHALL appear before any wildcard/else arm in the evaluator.

#### Scenario: registry is None — warning and False

- **WHEN** `evaluate(CustomConditionRef(name="my-gate"), player, registry=None)` is called
- **THEN** a warning is logged indicating the custom condition could not be resolved, and the result is `False`

#### Scenario: unknown name — warning and False

- **WHEN** `evaluate(CustomConditionRef(name="nonexistent"), player, registry=registry)` is called and `"nonexistent"` is not in `registry.custom_conditions`
- **THEN** a warning is logged and the result is `False`

#### Scenario: resolved condition is evaluated recursively

- **WHEN** `evaluate(CustomConditionRef(name="gate-level-5"), player, registry=registry)` is called and `"gate-level-5"` resolves to a `CustomCondition` whose `condition` is `level: 5`, and the player is at level 6
- **THEN** the result is `True`

#### Scenario: resolved condition evaluates to False

- **WHEN** `evaluate(CustomConditionRef(name="gate-level-5"), player, registry=registry)` is called and the player is at level 3
- **THEN** the result is `False`

#### Scenario: nested CustomConditionRef chain evaluates correctly

- **WHEN** `"outer"` resolves to a `CustomCondition` that contains `CustomConditionRef(name="inner")`, and `"inner"` resolves to `level: 5`, and the player is at level 5
- **THEN** `evaluate(CustomConditionRef(name="outer"), player, registry=registry)` returns `True`
