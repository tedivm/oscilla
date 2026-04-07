# Load Warnings

The `LoadWarning` system provides a middle tier between hard errors and silent
success in the content loading pipeline. This document covers when to emit
warnings, the `suggestion` field contract, and how to add new warning conditions.

---

## The `LoadWarning` Dataclass

```python
@dataclass
class LoadWarning:
    file: Path            # manifest file that triggered the warning
    message: str          # human-readable description of the problem
    suggestion: str = ""  # optional fix hint

    def __str__(self) -> str:
        """Appends the suggestion when non-empty."""
        if self.suggestion:
            return f"{self.message} — {self.suggestion}"
        return self.message
```

Warnings are collected in a `List[LoadWarning]` accumulator and returned alongside
the `ContentRegistry`:

```python
registry, warnings = load(game_path)
```

---

## When to Emit a Warning vs. Raise an Error

Use `ContentLoadError` (hard error) when the content **cannot run correctly** — for
example, a cross-reference to a non-existent item, a malformed YAML schema, or a
missing required field. Loading stops entirely.

Use `LoadWarning` when the content **will run** but something looks wrong or
suboptimal:

| Situation                                                                     | Diagnostic         |
| ----------------------------------------------------------------------------- | ------------------ |
| Missing required field or broken reference                                    | `ContentLoadError` |
| Item label not declared in `game.yaml`                                        | `LoadWarning`      |
| Passive effect condition uses `item_held_label` (registry unavailable)        | `LoadWarning`      |
| Passive effect condition uses `stat_source: effective` (registry unavailable) | `LoadWarning`      |
| Any other "suspicious but valid" content                                      | `LoadWarning`      |

The guiding principle: if a human author could plausibly intend the content and the
game will still work, emit a warning. If the content will produce incorrect behavior
or cannot be interpreted at all, raise an error.

---

## The `suggestion` Field Contract

The `suggestion` string is consumed by:

1. **Human developers** — shown after a `—` separator in CLI output
2. **AI coding tools** — reading `validate` output to auto-fix content issues

**Rules for suggestions:**

- Always start with an action verb or "Did you mean": `"Did you mean 'rare'?"`, `"Add 'legendary' to item_labels in game.yaml."`
- Keep it to one sentence.
- When a close spelling match exists (Levenshtein distance ≤ 2), use `"Did you mean 'X'?"`.
- When no close match exists but a fix is obvious, use `"Add X to <location>."`.
- Leave `suggestion=""` when no useful hint is available.

---

## Levenshtein Distance Helper

`oscilla/engine/string_utils.py` provides a two-row DP Levenshtein implementation
with no external dependencies:

```python
from oscilla.engine.string_utils import levenshtein

distance = levenshtein("legendery", "legendary")  # → 1
```

Use this when computing close-match suggestions to keep the threshold consistent
across all warning conditions.

---

## Adding New Warning Conditions

1. **Identify where to check** — warnings are accumulated inside `load()` in `loader.py`.
   Most checks happen in a dedicated `_validate_*()` helper function that returns
   `List[LoadWarning]`.

2. **Write the helper:**

   ```python
   def _validate_my_check(registry: ContentRegistry, game_path: Path) -> List[LoadWarning]:
       warnings: List[LoadWarning] = []
       for item_mf in registry.items.values():
           if something_wrong(item_mf):
               warnings.append(LoadWarning(
                   file=game_path / "items" / f"{item_mf.metadata.name}.yaml",
                   message=f"<{item_mf.metadata.name}>: description of problem",
                   suggestion="Did you mean 'correct_value'?",
               ))
       return warnings
   ```

3. **Call it from `load()`** and extend the accumulator:

   ```python
   warnings.extend(_validate_my_check(registry, game_path))
   ```

4. **Add tests** in `tests/engine/` — at minimum:
   - A fixture that triggers the warning and asserts `len(warnings) == 1`
   - A fixture that does not trigger the warning and asserts `len(warnings) == 0`
   - A test that the `suggestion` field is non-empty when a close match is expected

---

## Existing Warning Sources

| Helper                        | Trigger                                                                                                                 |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `_validate_labels()`          | Item label not declared in `game.item_labels`; close match → "Did you mean X?" suggestion                               |
| `_validate_passive_effects()` | Passive effect condition uses `item_held_label`, `any_item_equipped`, or `character_stat` with `stat_source: effective` |
