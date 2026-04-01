## ADDED Requirements

### Requirement: TUICallbacks protocol exposes skill menu callback

The `TUICallbacks` protocol SHALL declare a `show_skill_menu(skills: List[Dict[str, Any]]) -> int | None` async method. Each dict in the list SHALL contain:

- `name: str` — skill display name.
- `description: str` — skill description text.
- `cost_label: str | None` — human-readable cost string (e.g. `"10 mana"`), or None.
- `cooldown_label: str | None` — human-readable cooldown info, or None.
- `available: bool` — True if the skill can currently be used (resources available, cooldown clear).

The method SHALL return the 0-based index of the selected skill, or `None` if the player dismisses the screen without selecting.

#### Scenario: Protocol declares show_skill_menu

- **WHEN** a class implements `TUICallbacks`
- **THEN** it MAY declare `show_skill_menu` and the type system accepts it

#### Scenario: MockTUI records skill menu calls

- **WHEN** `show_skill_menu()` is called on MockTUI with a preconfigured response
- **THEN** the call is recorded in `tui.skill_menus` and the preconfigured index is returned

---

### Requirement: Actions screen lists and invokes overworld skills

The engine session layer SHALL expose an `open_actions_screen(player, registry, tui)` async function. This function SHALL:

1. Collect all skills in `player.available_skills(registry)` whose `contexts` includes `"overworld"`.
2. Build a list of skill dicts (name, description, cost_label, cooldown_label, available) for each skill.
3. Call `await tui.show_skill_menu(skills)`.
4. If the player selects a skill (non-None return), validate and dispatch it using the same pre-use checks as combat (resource cost, `requires` condition, adventure-scope cooldown). No CombatContext is passed.
5. If no overworld skills are available, inform the player via `show_text()` and return.

#### Scenario: Actions screen shown with overworld skills

- **WHEN** `open_actions_screen()` is called and the player has overworld-context skills
- **THEN** `tui.show_skill_menu()` is called with skill dicts for each available skill

#### Scenario: Skill used from Actions screen dispatches effects

- **WHEN** the player selects a skill in the Actions screen and all checks pass
- **THEN** the skill's `use_effects` are dispatched with `combat=None`

#### Scenario: Actions screen shows nothing when no overworld skills

- **WHEN** the player has no skills with `contexts: [overworld]`
- **THEN** `show_text()` is called with an informational message and `show_skill_menu()` is not called

#### Scenario: Actions screen blocks use if resource insufficient

- **WHEN** the player selects a skill with a resource cost they cannot afford from the Actions screen
- **THEN** the TUI shows a "Not enough <stat>" message and no effects fire

#### Scenario: Actions screen blocks use if adventure-scope cooldown active

- **WHEN** the player selects a skill that is on adventure-scope cooldown
- **THEN** the TUI shows a cooldown message and no effects fire
