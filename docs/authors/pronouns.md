# Pronouns

Oscilla supports player-selectable pronouns. Characters can use **she/her**, **he/him**, **they/them**, or any custom pronoun set defined in your game's `CharacterConfig`. Narrative text automatically adjusts to match the player's chosen pronouns via the **pronoun placeholder** system.

## How Pronouns Work

When a player creates a character they can choose a pronoun set. The chosen set is stored on the character and persisted across sessions. Narrative templates that contain pronoun placeholders (or explicit template expressions) are rendered with that pronoun set at runtime.

## Supported Pronoun Placeholders

Use the shorthand placeholders below in any narrative `text` field. You do **not** need to write raw Jinja2 — the placeholders are cleaner and automatically handle verb agreement.

Capitalisation of the placeholder determines capitalisation of the output:

| Placeholder | Meaning | they/them | she/her | he/him |
|---|---|---|---|---|
| `{they}` | subject pronoun | they | she | he |
| `{They}` | subject, capitalized | They | She | He |
| `{THEY}` | subject, uppercase | THEY | SHE | HE |
| `{them}` | object pronoun | them | her | him |
| `{their}` | possessive adjective | their | her | his |
| `{is}` / `{are}` | linking verb | are | is | is |
| `{was}` / `{were}` | past linking verb | were | was | was |
| `{has}` / `{have}` | auxiliary verb | have | has | has |

Both `{is}` and `{are}` expand identically — write whichever form reads most naturally for the sentence.

## Example Templates

```yaml
# Simple greeting
text: "Hello! {They} {are} ready for adventure."
# they/them → "Hello! They are ready for adventure."
# she/her   → "Hello! She is ready for adventure."
# he/him    → "Hello! He is ready for adventure."

# Name + pronouns
text: "{{ player.name }} hefts {their} sword and grins."
# they/them → "Hero hefts their sword and grins."
# she/her   → "Hero hefts her sword and grins."
# he/him    → "Hero hefts his sword and grins."

# Past tense
text: "{They} {was} the last one standing."
# they/them → "They were the last one standing."
# she/her   → "She was the last one standing."
# he/him    → "He was the last one standing."
```

## Accessing Pronouns in Jinja2 Templates

If you need more control, the full pronoun set is available on the `player.pronouns` context object:

| Expression | they/them | she/her | he/him |
|---|---|---|---|
| `{{ player.pronouns.subject }}` | they | she | he |
| `{{ player.pronouns.object }}` | them | her | him |
| `{{ player.pronouns.possessive }}` | their | her | his |
| `{{ player.pronouns.possessive_standalone }}` | theirs | hers | his |
| `{{ player.pronouns.reflexive }}` | themselves | herself | himself |
| `{{ player.pronouns.uses_plural_verbs }}` | True | False | False |

## Custom Pronoun Sets

Game packages can define additional pronoun sets in their `CharacterConfig`:

```yaml
apiVersion: game/v1
kind: CharacterConfig
metadata:
  name: my-game-character
spec:
  public_stats: []
  hidden_stats: []
  extra_pronoun_sets:
    - name: ze_zir           # key used internally and in save files
      display_name: "Ze/Zir"
      subject: ze
      object: zir
      possessive: zir
      possessive_standalone: zirs
      reflexive: zirself
      uses_plural_verbs: false
```

### Rules for Custom Sets

- `name` must be unique and must **not** clash with the built-in keys (`they_them`, `she_her`, `he_him`). A clash causes a `ContentLoadError` at load time.
- `uses_plural_verbs: true` means verb placeholders produce the plural form (`are`, `were`, `have`). Set to `false` for singular forms (`is`, `was`, `has`).
- All six string fields (`subject`, `object`, `possessive`, `possessive_standalone`, `reflexive`, `display_name`) are required.

## Built-in Pronoun Sets

| Key | Display name | Subject | Object | Possessive | Reflexive | Plural verbs |
|---|---|---|---|---|---|---|
| `they_them` | They/Them | they | them | their | themselves | yes |
| `she_her` | She/Her | she | her | her | herself | no |
| `he_him` | He/Him | he | him | his | himself | no |

---

*For the full template reference, see [Content Authoring Guide](./content-authoring.md#dynamic-templates).*
