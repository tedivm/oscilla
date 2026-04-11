"""Unit tests for the pronoun system — PronounSet data, CharacterState integration, template rendering."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.loader import ContentLoadError, load_from_disk
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.templates import (
    DEFAULT_PRONOUN_SET,
    PRONOUN_SETS,
    ExpressionContext,
    GameTemplateEngine,
    PlayerContext,
    PlayerMilestoneView,
    PlayerPronounView,
)

# ---------------------------------------------------------------------------
# Built-in pronoun set integrity
# ---------------------------------------------------------------------------


def test_they_them_fields() -> None:
    ps = PRONOUN_SETS["they_them"]
    assert ps.subject == "they"
    assert ps.object == "them"
    assert ps.possessive == "their"
    assert ps.possessive_standalone == "theirs"
    assert ps.reflexive == "themselves"
    assert ps.uses_plural_verbs is True


def test_she_her_fields() -> None:
    ps = PRONOUN_SETS["she_her"]
    assert ps.subject == "she"
    assert ps.object == "her"
    assert ps.possessive == "her"
    assert ps.possessive_standalone == "hers"
    assert ps.reflexive == "herself"
    assert ps.uses_plural_verbs is False


def test_he_him_fields() -> None:
    ps = PRONOUN_SETS["he_him"]
    assert ps.subject == "he"
    assert ps.object == "him"
    assert ps.possessive == "his"
    assert ps.possessive_standalone == "his"
    assert ps.reflexive == "himself"
    assert ps.uses_plural_verbs is False


def test_default_is_they_them() -> None:
    assert DEFAULT_PRONOUN_SET is PRONOUN_SETS["they_them"]


# ---------------------------------------------------------------------------
# CharacterState pronoun integration
# ---------------------------------------------------------------------------


def test_new_character_defaults_to_they_them(base_player: CharacterState) -> None:
    assert base_player.pronouns == PRONOUN_SETS["they_them"]


def test_to_dict_serialises_pronoun_set_key(base_player: CharacterState) -> None:
    data = base_player.to_dict()
    assert "pronoun_set" in data
    assert data["pronoun_set"] == "they_them"


def test_from_dict_restores_she_her(base_player: CharacterState, minimal_registry: ContentRegistry) -> None:
    assert minimal_registry.character_config is not None
    data = base_player.to_dict()
    data["pronoun_set"] = "she_her"
    restored = CharacterState.from_dict(
        data=data,
        character_config=minimal_registry.character_config,
        registry=minimal_registry,
    )
    assert restored.pronouns == PRONOUN_SETS["she_her"]


def test_from_dict_unknown_key_falls_back_to_they_them(
    base_player: CharacterState, minimal_registry: ContentRegistry, caplog: pytest.LogCaptureFixture
) -> None:
    assert minimal_registry.character_config is not None
    data = base_player.to_dict()
    data["pronoun_set"] = "ze_zir"  # unknown key
    with caplog.at_level(logging.WARNING, logger="oscilla.engine.character"):
        restored = CharacterState.from_dict(
            data=data,
            character_config=minimal_registry.character_config,
            registry=minimal_registry,
        )
    assert restored.pronouns == PRONOUN_SETS["they_them"]
    assert "ze_zir" in caplog.text


# ---------------------------------------------------------------------------
# Pronoun rendering via GameTemplateEngine
# ---------------------------------------------------------------------------


def _make_ctx_for_set(pronoun_key: str) -> ExpressionContext:
    ps = PRONOUN_SETS[pronoun_key]
    view = PlayerPronounView.from_set(ps)
    player = PlayerContext(
        name="Hero",
        prestige_count=0,
        stats={},
        milestones=PlayerMilestoneView(_milestones=set()),
        pronouns=view,
    )
    return ExpressionContext(player=player)


def _render(template_str: str, pronoun_key: str) -> str:
    engine = GameTemplateEngine(stat_names=[])
    ctx = _make_ctx_for_set(pronoun_key)
    engine.precompile_and_validate(template_str, f"test-{pronoun_key}", "adventure")
    return engine.render(f"test-{pronoun_key}", ctx)


# they_them rendering
def test_they_subject_they() -> None:
    assert _render("{they}", "they_them") == "they"


def test_they_subject_They_capitalised() -> None:
    assert _render("{They}", "they_them") == "They"


def test_they_subject_THEY_upper() -> None:
    assert _render("{THEY}", "they_them") == "THEY"


def test_they_object() -> None:
    assert _render("{them}", "they_them") == "them"


def test_they_possessive() -> None:
    assert _render("{their}", "they_them") == "their"


def test_they_is_verb() -> None:
    # they_them uses plural verbs → "are"
    assert _render("{is}", "they_them") == "are"


def test_they_are_verb() -> None:
    assert _render("{are}", "they_them") == "are"


def test_they_was_verb() -> None:
    assert _render("{was}", "they_them") == "were"


def test_they_has_verb() -> None:
    assert _render("{has}", "they_them") == "have"


# she_her rendering
def test_she_subject() -> None:
    assert _render("{they}", "she_her") == "she"


def test_she_object() -> None:
    assert _render("{them}", "she_her") == "her"


def test_she_is_verb() -> None:
    # she_her uses singular verbs → "is"
    assert _render("{is}", "she_her") == "is"


# he_him rendering
def test_he_subject() -> None:
    assert _render("{they}", "he_him") == "he"


def test_he_object() -> None:
    assert _render("{them}", "he_him") == "him"


def test_he_has_verb() -> None:
    assert _render("{has}", "he_him") == "has"


# ---------------------------------------------------------------------------
# Custom pronoun set name conflict — Task 12.4
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"


def test_conflicting_extra_pronoun_set_name_raises_content_load_error(tmp_path: Path) -> None:
    """A CharacterConfig with extra_pronoun_sets using a built-in name raises ContentLoadError."""
    # Copy the template-system fixtures as the base directory.
    shutil.copytree(FIXTURES / "template-system", tmp_path / "conflicting-pronouns")
    content_dir = tmp_path / "conflicting-pronouns"

    # Overwrite the character config with a conflicting extra_pronoun_sets name.
    (content_dir / "test-character-config.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test-character-config
spec:
  public_stats:
    - name: strength
      type: int
      default: 10
      description: "Physical power"
    - name: luck
      type: int
      default: 5
      description: "Fortune stat for template roll tests"
    - name: xp
      type: int
      default: 0
      bounds:
        min: 0
      description: "Experience points"
  hidden_stats: []
  extra_pronoun_sets:
    - name: they_them
      display_name: "They/Them (duplicate)"
      subject: they
      object: them
      possessive: their
      possessive_standalone: theirs
      reflexive: themselves
      uses_plural_verbs: true
""",
        encoding="utf-8",
    )

    with pytest.raises(ContentLoadError, match="they_them"):
        load_from_disk(content_dir)
