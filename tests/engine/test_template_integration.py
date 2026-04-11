"""Integration tests for the dynamic-content-templates system.

Tests cover:
- Loading the template-system fixture set (valid templates pass validation).
- Narrative templates render player.name and player.stats correctly.
- XP-grant template (roll) produces a value within the specified range.
- Stat-change template resolves to the player's current stat value.
- Invalid template strings are rejected at load time with ContentLoadError.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from oscilla.engine.loader import ContentLoadError, load_from_disk
from oscilla.engine.pipeline import AdventurePipeline
from tests.engine.conftest import MockTUI

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.registry import ContentRegistry

FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"


# ---------------------------------------------------------------------------
# Registry and player fixtures scoped to this module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def template_registry() -> "ContentRegistry":
    registry, _warnings = load_from_disk(FIXTURES / "template-system")
    return registry


@pytest.fixture
def template_player(template_registry: "ContentRegistry") -> "CharacterState":
    from oscilla.engine.character import CharacterState

    assert template_registry.game is not None
    assert template_registry.character_config is not None
    return CharacterState.new_character(
        name="Tester",
        game_manifest=template_registry.game,
        character_config=template_registry.character_config,
    )


# ---------------------------------------------------------------------------
# Task 13.2 — fixture loads without error
# ---------------------------------------------------------------------------


def test_template_system_loads_without_error(template_registry: "ContentRegistry") -> None:
    """The template-system fixture set loads cleanly — all templates are valid."""
    assert template_registry.game is not None
    assert template_registry.character_config is not None


def test_template_system_has_narrative_adventure(template_registry: "ContentRegistry") -> None:
    adv = template_registry.adventures.get("test-template-narrative")
    assert adv is not None


# ---------------------------------------------------------------------------
# Task 13.3 — narrative text template renders player name and stat
# ---------------------------------------------------------------------------


async def test_narrative_template_renders_player_name(
    template_registry: "ContentRegistry",
    template_player: "CharacterState",
) -> None:
    """Narrative text containing {{ player.name }} is rendered with the real player name."""
    tui = MockTUI()
    pipeline = AdventurePipeline(registry=template_registry, player=template_player, tui=tui)
    await pipeline.run("test-template-narrative")
    # The adventure text is: "Hello, {{ player.name }}! You have {{ player.stats.strength }} strength."
    assert any("Tester" in t for t in tui.texts), f"Expected 'Tester' in texts: {tui.texts}"


async def test_narrative_template_renders_strength_stat(
    template_registry: "ContentRegistry",
    template_player: "CharacterState",
) -> None:
    """Narrative text containing {{ player.stats.strength }} renders the character's strength value."""
    tui = MockTUI()
    pipeline = AdventurePipeline(registry=template_registry, player=template_player, tui=tui)
    await pipeline.run("test-template-narrative")
    # strength defaults to 10 in test-character-config
    assert any("10" in t for t in tui.texts), f"Expected '10' in texts: {tui.texts}"


# ---------------------------------------------------------------------------
# Task 13.4 — XP roll template produces a value within range
# ---------------------------------------------------------------------------


async def test_xp_roll_template_within_range(
    template_registry: "ContentRegistry",
    template_player: "CharacterState",
) -> None:
    """XP grant using {{ roll(5, 15) }} awards between 5 and 15 XP."""
    tui = MockTUI()
    pipeline = AdventurePipeline(registry=template_registry, player=template_player, tui=tui)
    await pipeline.run("test-template-xp-roll")
    xp = template_player.stats.get("xp", 0)
    assert 5 <= xp <= 15, f"xp={xp} is not in [5, 15]"


# ---------------------------------------------------------------------------
# Task 13.5 — stat-change template resolves to current stat value
# ---------------------------------------------------------------------------


async def test_stat_change_template_applies_correct_delta(
    template_registry: "ContentRegistry",
    template_player: "CharacterState",
) -> None:
    """Stat change using {{ player.stats.luck }} adds the player's luck to strength.

    Initial strength=10, luck=5, so strength should be 15 after the adventure.
    """
    tui = MockTUI()
    pipeline = AdventurePipeline(registry=template_registry, player=template_player, tui=tui)
    await pipeline.run("test-template-stat-change")
    assert template_player.stats["strength"] == 15, f"Expected strength=15, got {template_player.stats['strength']}"


# ---------------------------------------------------------------------------
# Task 13.5 — invalid template raises ContentLoadError at load time
# ---------------------------------------------------------------------------


def test_invalid_template_raises_content_load_error(tmp_path: Path) -> None:
    """An adventure with an invalid Jinja2 template is rejected at load time."""
    import shutil

    shutil.copytree(FIXTURES / "template-system", tmp_path / "bad-template")
    content_dir = tmp_path / "bad-template"

    # Replace the narrative adventure with one containing a syntax-invalid template.
    (content_dir / "test-template-narrative.yaml").write_text(
        """\
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: test-template-narrative
spec:
  displayName: "Bad Template Narrative"
  description: "Adventure with a broken template expression."
  steps:
    - type: narrative
      text: "Hello, {{ player.name | unknown_filter }}!"
      effects: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ContentLoadError):
        load_from_disk(content_dir)
