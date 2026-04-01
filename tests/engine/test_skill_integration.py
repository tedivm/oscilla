"""Integration tests for the skill system — loader validation, run_effect dispatching,
SkillCondition evaluation, and enemy-targeting effects.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from oscilla.engine.combat_context import CombatContext
from oscilla.engine.conditions import evaluate
from oscilla.engine.loader import ContentLoadError, load
from oscilla.engine.models.adventure import ApplyBuffEffect, SkillGrantEffect, StatChangeEffect
from oscilla.engine.models.base import SkillCondition
from oscilla.engine.steps.effects import run_effect

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.registry import ContentRegistry

FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"


# ---------------------------------------------------------------------------
# Registry fixtures scoped to this module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def skill_combat_registry() -> "ContentRegistry":
    return load(FIXTURES / "skill-combat")


# ---------------------------------------------------------------------------
# Loader — valid fixture loads (13.1)
# ---------------------------------------------------------------------------


def test_skill_combat_fixture_loads(skill_combat_registry: "ContentRegistry") -> None:
    """The skill-combat fixture set loads without errors."""
    assert skill_combat_registry.game is not None
    assert skill_combat_registry.character_config is not None


def test_skill_combat_fixture_has_skills(skill_combat_registry: "ContentRegistry") -> None:
    skill = skill_combat_registry.skills.get("test-skill-fireball")
    assert skill is not None
    assert skill.spec.displayName == "Fireball"


def test_skill_combat_fixture_has_buffs(skill_combat_registry: "ContentRegistry") -> None:
    buff = skill_combat_registry.buffs.get("test-buff-dot")
    assert buff is not None
    assert buff.spec.duration_turns == 3


def test_skill_combat_fixture_has_enemies(skill_combat_registry: "ContentRegistry") -> None:
    enemy = skill_combat_registry.enemies.get("test-enemy")
    assert enemy is not None
    assert len(enemy.spec.skills) == 1
    assert enemy.spec.skills[0].skill_ref == "test-skill-poison"


# ---------------------------------------------------------------------------
# Loader — unknown skill ref rejection (13.4)
# ---------------------------------------------------------------------------


def test_loader_rejects_unknown_skill_ref_in_item(tmp_path: Path) -> None:
    """Item granting a non-existent skill is rejected at load time."""
    _write_base_manifests(tmp_path)
    (tmp_path / "bad-item.yaml").write_text(
        """\
apiVersion: game/v1
kind: Item
metadata:
  name: bad-item
spec:
  category: weapon
  displayName: "Bad Item"
  description: ""
  stackable: true
  grants_skills_equipped:
    - nonexistent-skill
""",
        encoding="utf-8",
    )
    with pytest.raises(ContentLoadError, match="nonexistent-skill"):
        load(tmp_path)


def test_loader_rejects_unknown_skill_ref_in_enemy(tmp_path: Path) -> None:
    """Enemy skill list referencing a non-existent skill is rejected."""
    _write_base_manifests(tmp_path)
    (tmp_path / "bad-enemy.yaml").write_text(
        """\
apiVersion: game/v1
kind: Enemy
metadata:
  name: bad-enemy
spec:
  displayName: "Bad Enemy"
  description: ""
  hp: 10
  attack: 3
  defense: 0
  xp_reward: 5
  loot: []
  skills:
    - skill_ref: nonexistent-skill
      use_every_n_turns: 2
""",
        encoding="utf-8",
    )
    with pytest.raises(ContentLoadError, match="nonexistent-skill"):
        load(tmp_path)


# ---------------------------------------------------------------------------
# Loader — unknown buff ref rejection (13.5)
# ---------------------------------------------------------------------------


def test_loader_rejects_apply_buff_with_unknown_buff_ref(tmp_path: Path) -> None:
    """A Skill with apply_buff pointing to a non-existent Buff is rejected."""
    _write_base_manifests(tmp_path)
    (tmp_path / "bad-skill.yaml").write_text(
        """\
apiVersion: game/v1
kind: Skill
metadata:
  name: bad-skill
spec:
  displayName: "Bad Skill"
  contexts:
    - combat
  use_effects:
    - type: apply_buff
      buff_ref: nonexistent-buff
      target: enemy
      variables: {}
""",
        encoding="utf-8",
    )
    with pytest.raises(ContentLoadError, match="nonexistent-buff"):
        load(tmp_path)


# ---------------------------------------------------------------------------
# Loader — unknown variable override key rejection (13.5a)
# ---------------------------------------------------------------------------


def test_loader_rejects_apply_buff_with_unknown_variable_key(tmp_path: Path) -> None:
    """A Skill overriding a variable key not declared in the Buff spec is rejected."""
    _write_base_manifests(tmp_path)
    (tmp_path / "test-buff-rage.yaml").write_text(
        """\
apiVersion: game/v1
kind: Buff
metadata:
  name: test-buff-rage
spec:
  displayName: "Rage"
  duration_turns: 2
  variables:
    rage_percent: 50
  modifiers:
    - type: damage_amplify
      target: player
      percent: rage_percent
""",
        encoding="utf-8",
    )
    (tmp_path / "bad-skill-var.yaml").write_text(
        """\
apiVersion: game/v1
kind: Skill
metadata:
  name: bad-skill-var
spec:
  displayName: "Bad Skill Var"
  contexts:
    - combat
  use_effects:
    - type: apply_buff
      buff_ref: test-buff-rage
      target: player
      variables:
        undeclared_key: 99
""",
        encoding="utf-8",
    )
    with pytest.raises(ContentLoadError, match="undeclared_key"):
        load(tmp_path)


# ---------------------------------------------------------------------------
# Loader — grants_buffs_equipped/held ref rejection (13.6)
# ---------------------------------------------------------------------------


def test_loader_rejects_grants_buffs_with_unknown_buff_ref(tmp_path: Path) -> None:
    """An Item with grants_buffs_equipped pointing to a non-existent Buff is rejected."""
    _write_base_manifests(tmp_path)
    (tmp_path / "bad-buffgrant-item.yaml").write_text(
        """\
apiVersion: game/v1
kind: Item
metadata:
  name: bad-buffgrant-item
spec:
  category: armor
  displayName: "Bad Grant Item"
  description: ""
  stackable: false
  grants_buffs_equipped:
    - buff_ref: nonexistent-buff
      variables: {}
""",
        encoding="utf-8",
    )
    with pytest.raises(ContentLoadError, match="nonexistent-buff"):
        load(tmp_path)


def test_loader_rejects_grants_buffs_with_unknown_variable_key(tmp_path: Path) -> None:
    """An Item with grants_buffs_equipped overriding an undeclared variable key is rejected."""
    _write_base_manifests(tmp_path)
    (tmp_path / "test-buff-shield.yaml").write_text(
        """\
apiVersion: game/v1
kind: Buff
metadata:
  name: test-buff-shield
spec:
  displayName: "Shield"
  duration_turns: 3
  variables: {}
  modifiers:
    - type: damage_reduction
      target: player
      percent: 50
""",
        encoding="utf-8",
    )
    (tmp_path / "bad-var-item.yaml").write_text(
        """\
apiVersion: game/v1
kind: Item
metadata:
  name: bad-var-item
spec:
  category: armor
  displayName: "Bad Var Item"
  description: ""
  stackable: false
  grants_buffs_equipped:
    - buff_ref: test-buff-shield
      variables:
        undeclared: 99
""",
        encoding="utf-8",
    )
    with pytest.raises(ContentLoadError, match="undeclared"):
        load(tmp_path)


# ---------------------------------------------------------------------------
# run_effect — SkillGrantEffect integration (13.1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_grant_effect_grants_skill(
    base_player: "CharacterState",
    skill_combat_registry: "ContentRegistry",
) -> None:
    from tests.engine.conftest import MockTUI

    tui = MockTUI()
    effect = SkillGrantEffect(type="skill_grant", skill="test-skill-fireball")
    await run_effect(effect=effect, player=base_player, registry=skill_combat_registry, tui=tui)
    assert "test-skill-fireball" in base_player.known_skills


@pytest.mark.asyncio
async def test_skill_grant_effect_shows_text(
    base_player: "CharacterState",
    skill_combat_registry: "ContentRegistry",
) -> None:
    from tests.engine.conftest import MockTUI

    base_player.known_skills.discard("test-skill-fireball")
    tui = MockTUI()
    effect = SkillGrantEffect(type="skill_grant", skill="test-skill-fireball")
    await run_effect(effect=effect, player=base_player, registry=skill_combat_registry, tui=tui)
    assert any("Fireball" in t for t in tui.texts)


# ---------------------------------------------------------------------------
# SkillCondition evaluation (13.1)
# ---------------------------------------------------------------------------


def test_skill_condition_mode_learned_pass(
    base_player: "CharacterState", skill_combat_registry: "ContentRegistry"
) -> None:
    base_player.known_skills.add("test-skill-fireball")
    cond = SkillCondition(type="skill", name="test-skill-fireball", mode="learned")
    assert evaluate(condition=cond, player=base_player) is True


def test_skill_condition_mode_learned_fail(
    base_player: "CharacterState", skill_combat_registry: "ContentRegistry"
) -> None:
    base_player.known_skills.discard("test-skill-unknown")
    cond = SkillCondition(type="skill", name="test-skill-unknown", mode="learned")
    assert evaluate(condition=cond, player=base_player) is False


def test_skill_condition_mode_available_with_registry(
    base_player: "CharacterState", skill_combat_registry: "ContentRegistry"
) -> None:
    base_player.known_skills.add("test-skill-fireball")
    cond = SkillCondition(type="skill", name="test-skill-fireball", mode="available")
    assert evaluate(condition=cond, player=base_player, registry=skill_combat_registry) is True


def test_skill_condition_mode_available_without_registry(
    base_player: "CharacterState",
) -> None:
    """Without registry, available mode falls back to known_skills only."""
    base_player.known_skills.add("test-skill-fallback")
    cond = SkillCondition(type="skill", name="test-skill-fallback", mode="available")
    assert evaluate(condition=cond, player=base_player) is True


# ---------------------------------------------------------------------------
# stat_change target="enemy" effect routing (13.2 / 13.3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stat_change_enemy_target_with_combat(
    base_player: "CharacterState",
    minimal_registry: "ContentRegistry",
) -> None:
    """stat_change target=enemy with CombatContext reduces enemy HP."""
    from tests.engine.conftest import MockTUI

    ctx = CombatContext(enemy_hp=20, enemy_ref="test-enemy")
    tui = MockTUI()
    effect = StatChangeEffect(type="stat_change", stat="hp", amount=-5, target="enemy")
    await run_effect(effect=effect, player=base_player, registry=minimal_registry, tui=tui, combat=ctx)
    assert ctx.enemy_hp == 15


@pytest.mark.asyncio
async def test_stat_change_enemy_target_without_combat_is_skipped(
    base_player: "CharacterState",
    minimal_registry: "ContentRegistry",
) -> None:
    """stat_change target=enemy without CombatContext is skipped (no crash)."""
    from tests.engine.conftest import MockTUI

    original_hp = base_player.hp
    tui = MockTUI()
    effect = StatChangeEffect(type="stat_change", stat="hp", amount=-5, target="enemy")
    # Should not raise; no combat context → logged warning and skip.
    await run_effect(effect=effect, player=base_player, registry=minimal_registry, tui=tui, combat=None)
    # Player HP should be unchanged.
    assert base_player.hp == original_hp


# ---------------------------------------------------------------------------
# apply_buff and dispel integration (13.1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_buff_adds_active_effect(
    base_player: "CharacterState",
    skill_combat_registry: "ContentRegistry",
) -> None:
    from tests.engine.conftest import MockTUI

    ctx = CombatContext(enemy_hp=30, enemy_ref="test-enemy")
    tui = MockTUI()
    effect = ApplyBuffEffect(type="apply_buff", buff_ref="test-buff-dot", target="enemy", variables={})
    await run_effect(effect=effect, player=base_player, registry=skill_combat_registry, tui=tui, combat=ctx)
    assert len(ctx.active_effects) == 1
    ae = ctx.active_effects[0]
    assert ae.label == "test-buff-dot"
    assert ae.target == "enemy"
    assert ae.remaining_turns == 3


@pytest.mark.asyncio
async def test_apply_buff_outside_combat_is_skipped(
    base_player: "CharacterState",
    skill_combat_registry: "ContentRegistry",
) -> None:
    from tests.engine.conftest import MockTUI

    tui = MockTUI()
    effect = ApplyBuffEffect(type="apply_buff", buff_ref="test-buff-dot", target="enemy", variables={})
    # Should not raise; just log a warning.
    await run_effect(effect=effect, player=base_player, registry=skill_combat_registry, tui=tui, combat=None)


@pytest.mark.asyncio
async def test_apply_buff_with_variable_override(
    base_player: "CharacterState",
    skill_combat_registry: "ContentRegistry",
) -> None:
    """apply_buff with variable override resolves overridden percent."""
    from tests.engine.conftest import MockTUI

    ctx = CombatContext(enemy_hp=30, enemy_ref="test-enemy")
    tui = MockTUI()
    effect = ApplyBuffEffect(
        type="apply_buff",
        buff_ref="test-buff-rage",
        target="player",
        variables={"rage_percent": 80},
    )
    await run_effect(effect=effect, player=base_player, registry=skill_combat_registry, tui=tui, combat=ctx)
    assert len(ctx.active_effects) == 1
    ae = ctx.active_effects[0]
    # Modifier percent should be resolved to 80 (override), not 50 (manifest default).
    assert ae.modifiers[0].percent == 80


# ---------------------------------------------------------------------------
# Helpers for tmp_path-based loader tests
# ---------------------------------------------------------------------------


def _write_base_manifests(tmp_path: Path) -> None:
    """Write the minimum manifests needed for a valid content directory."""
    (tmp_path / "game.yaml").write_text(
        """\
apiVersion: game/v1
kind: Game
metadata:
  name: test-game
spec:
  displayName: "Test"
  xp_thresholds: [100]
  hp_formula:
    base_hp: 20
    hp_per_level: 5
""",
        encoding="utf-8",
    )
    (tmp_path / "char-config.yaml").write_text(
        """\
apiVersion: game/v1
kind: CharacterConfig
metadata:
  name: test-config
spec:
  public_stats:
    - name: strength
      type: int
      default: 10
""",
        encoding="utf-8",
    )
    (tmp_path / "region.yaml").write_text(
        """\
apiVersion: game/v1
kind: Region
metadata:
  name: test-region
spec:
  displayName: "Test Region"
  locations:
    - test-location
""",
        encoding="utf-8",
    )
    (tmp_path / "location.yaml").write_text(
        """\
apiVersion: game/v1
kind: Location
metadata:
  name: test-location
spec:
  displayName: "Test Location"
  region: test-region
""",
        encoding="utf-8",
    )
