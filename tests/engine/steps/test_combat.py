"""Tests for combat step handler."""

from __future__ import annotations

from oscilla.engine.character import AdventurePosition, CharacterState
from oscilla.engine.models.adventure import CombatStep, OutcomeBranch, StatChangeEffect
from oscilla.engine.models.base import CharacterStatCondition, EnemyStatCondition, Metadata
from oscilla.engine.models.combat_system import (
    CombatSystemManifest,
    CombatSystemSpec,
    DamageFormulaEntry,
    SystemSkillEntry,
)
from oscilla.engine.models.enemy import EnemyManifest, EnemySpec
from oscilla.engine.models.skill import SkillManifest, SkillSpec
from oscilla.engine.pipeline import AdventureOutcome
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.steps.combat import run_combat
from tests.engine.conftest import MockTUI

# Shared defeat conditions used across test registries.
_PLAYER_DEFEAT = CharacterStatCondition(type="character_stat", name="hp", lte=0)
_ENEMY_DEFEAT = EnemyStatCondition(type="enemy_stat", stat="hp", lte=0)


def _register_basic_attack_skill(registry: ContentRegistry) -> None:
    """Register a 'basic-attack' skill that deals 10 fixed damage to the enemy."""
    skill = SkillManifest(
        apiVersion="oscilla/v1",
        kind="Skill",
        metadata=Metadata(name="basic-attack"),
        spec=SkillSpec(
            displayName="Attack",
            contexts=["combat"],
            use_effects=[StatChangeEffect(type="stat_change", target="enemy", stat="hp", amount=-10)],
        ),
    )
    registry.skills.register(skill)


def _register_choice_combat_system(registry: ContentRegistry) -> None:
    """Register a choice-mode CombatSystem that uses 'basic-attack' and enemy attack stat."""
    system = CombatSystemManifest(
        apiVersion="oscilla/v1",
        kind="CombatSystem",
        metadata=Metadata(name="standard-combat"),
        spec=CombatSystemSpec(
            player_turn_mode="choice",
            skill_contexts=["combat"],
            system_skills=[SystemSkillEntry(skill="basic-attack")],
            enemy_damage_formulas=[
                DamageFormulaEntry(
                    target_stat="hp",
                    target="player",
                    formula="{{ enemy_stats.get('attack', 0) * -1 }}",
                )
            ],
            player_defeat_condition=_PLAYER_DEFEAT,
            enemy_defeat_condition=_ENEMY_DEFEAT,
        ),
    )
    registry.combat_systems.register(system)


def create_test_combat_registry() -> ContentRegistry:
    """Create a registry with test enemies and a choice-mode CombatSystem.

    Menu layout (choice mode):
      1. [System] Attack  — basic-attack skill, deals 10 fixed damage to enemy hp
      2. Flee
    """
    registry = ContentRegistry()
    _register_basic_attack_skill(registry)
    _register_choice_combat_system(registry)

    # Weak enemy: 5 hp, 2 attack.
    registry.enemies.register(
        EnemyManifest(
            apiVersion="oscilla/v1",
            kind="Enemy",
            metadata=Metadata(name="weak-enemy"),
            spec=EnemySpec(displayName="Weak Enemy", stats={"hp": 5, "attack": 2}),
        )
    )
    # Strong enemy: 100 hp, 50 attack (enough to kill player in one hit).
    registry.enemies.register(
        EnemyManifest(
            apiVersion="oscilla/v1",
            kind="Enemy",
            metadata=Metadata(name="strong-enemy"),
            spec=EnemySpec(displayName="Strong Enemy", stats={"hp": 100, "attack": 50}),
        )
    )
    return registry


def create_auto_combat_registry(
    enemies: list[EnemyManifest],
    player_formula: str,
    enemy_formula: str,
) -> ContentRegistry:
    """Create a registry with an auto-mode CombatSystem driven by explicit Jinja2 formulas."""
    registry = ContentRegistry()
    for enemy in enemies:
        registry.enemies.register(enemy)
    system = CombatSystemManifest(
        apiVersion="oscilla/v1",
        kind="CombatSystem",
        metadata=Metadata(name="auto-combat"),
        spec=CombatSystemSpec(
            player_turn_mode="auto",
            player_damage_formulas=[DamageFormulaEntry(target_stat="hp", target="enemy", formula=player_formula)],
            enemy_damage_formulas=[DamageFormulaEntry(target_stat="hp", target="player", formula=enemy_formula)],
            player_defeat_condition=_PLAYER_DEFEAT,
            enemy_defeat_condition=_ENEMY_DEFEAT,
        ),
    )
    registry.combat_systems.register(system)
    return registry


async def test_combat_win_scenario(base_player: CharacterState) -> None:
    """Test winning a combat scenario."""
    registry = create_test_combat_registry()
    mock_tui = MockTUI(menu_responses=[1])  # Always attack

    # Set up high strength to defeat weak enemy quickly
    base_player.stats["strength"] = 20
    base_player.stats["hp"] = 100
    base_player.stats["max_hp"] = 100

    step = CombatStep(
        type="combat",
        enemy="weak-enemy",
        on_win=OutcomeBranch(effects=[], steps=[], goto=None),
        on_defeat=OutcomeBranch(effects=[], steps=[], goto=None),
        on_flee=OutcomeBranch(effects=[], steps=[], goto=None),
    )

    outcome_calls = []

    async def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        outcome_calls.append(("branch", branch))
        return AdventureOutcome.COMPLETED

    result = await run_combat(
        step=step, player=base_player, registry=registry, tui=mock_tui, run_outcome_branch=mock_run_outcome_branch
    )

    assert result == AdventureOutcome.COMPLETED
    assert len(outcome_calls) == 1
    assert outcome_calls[0][1] == step.on_win
    assert base_player.statistics.enemies_defeated.get("weak-enemy", 0) == 1


async def test_combat_flee_scenario(base_player: CharacterState) -> None:
    """Test fleeing from combat."""
    registry = create_test_combat_registry()
    mock_tui = MockTUI(menu_responses=[2])  # Choose flee

    step = CombatStep(
        type="combat",
        enemy="weak-enemy",
        on_win=OutcomeBranch(effects=[], steps=[], goto=None),
        on_defeat=OutcomeBranch(effects=[], steps=[], goto=None),
        on_flee=OutcomeBranch(effects=[], steps=[], goto=None),
    )

    outcome_calls = []

    async def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        outcome_calls.append(branch)
        return AdventureOutcome.FLED

    result = await run_combat(
        step=step, player=base_player, registry=registry, tui=mock_tui, run_outcome_branch=mock_run_outcome_branch
    )

    assert result == AdventureOutcome.FLED
    assert len(outcome_calls) == 1
    assert outcome_calls[0] == step.on_flee
    assert base_player.statistics.enemies_defeated.get("weak-enemy", 0) == 0  # No kill recorded


async def test_combat_defeat_scenario(base_player: CharacterState) -> None:
    """Test player defeat in combat."""
    registry = create_test_combat_registry()
    mock_tui = MockTUI(menu_responses=[1, 1, 1])  # Keep attacking

    # Set up weak player vs strong enemy
    base_player.stats["strength"] = 1  # Very low damage
    base_player.stats["dexterity"] = 1  # Very low mitigation
    base_player.stats["hp"] = 10
    base_player.stats["max_hp"] = 10

    step = CombatStep(
        type="combat",
        enemy="strong-enemy",
        on_win=OutcomeBranch(effects=[], steps=[], goto=None),
        on_defeat=OutcomeBranch(effects=[], steps=[], goto=None),
        on_flee=OutcomeBranch(effects=[], steps=[], goto=None),
    )

    outcome_calls = []

    async def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        outcome_calls.append(branch)
        return AdventureOutcome.DEFEATED

    result = await run_combat(
        step=step, player=base_player, registry=registry, tui=mock_tui, run_outcome_branch=mock_run_outcome_branch
    )

    assert result == AdventureOutcome.DEFEATED
    assert len(outcome_calls) == 1
    assert outcome_calls[0] == step.on_defeat
    # HP goes negative because the enemy attack formula is not clamped — check <= 0.
    assert (base_player.stats.get("hp") or 0) <= 0


async def test_combat_stat_handling_non_numeric(base_player: CharacterState) -> None:
    """Test combat with non-numeric stats falls back to defaults."""
    registry = create_test_combat_registry()
    mock_tui = MockTUI(menu_responses=[1])  # Attack

    # Set non-numeric stats
    base_player.stats["strength"] = "strong"  # type: ignore[assignment]  # Non-numeric
    base_player.stats["dexterity"] = "agile"  # type: ignore[assignment]  # Non-numeric
    base_player.stats["hp"] = 100

    step = CombatStep(
        type="combat",
        enemy="weak-enemy",
        on_win=OutcomeBranch(effects=[], steps=[], goto=None),
        on_defeat=OutcomeBranch(effects=[], steps=[], goto=None),
        on_flee=OutcomeBranch(effects=[], steps=[], goto=None),
    )

    outcome_calls = []

    async def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        outcome_calls.append(branch)
        return AdventureOutcome.COMPLETED

    result = await run_combat(
        step=step, player=base_player, registry=registry, tui=mock_tui, run_outcome_branch=mock_run_outcome_branch
    )

    # Should complete without error, using default values
    assert result == AdventureOutcome.COMPLETED


async def test_combat_enemy_hp_persistence_fresh_start(base_player: CharacterState) -> None:
    """Test enemy HP starts fresh when no prior step state."""
    registry = create_test_combat_registry()
    mock_tui = MockTUI(menu_responses=[2])  # Flee immediately

    # No active adventure
    base_player.active_adventure = None

    step = CombatStep(
        type="combat",
        enemy="weak-enemy",
        on_win=OutcomeBranch(effects=[], steps=[], goto=None),
        on_defeat=OutcomeBranch(effects=[], steps=[], goto=None),
        on_flee=OutcomeBranch(effects=[], steps=[], goto=None),
    )

    async def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        return AdventureOutcome.FLED

    result = await run_combat(
        step=step, player=base_player, registry=registry, tui=mock_tui, run_outcome_branch=mock_run_outcome_branch
    )

    assert result == AdventureOutcome.FLED


async def test_combat_enemy_hp_persistence_restored_state(base_player: CharacterState) -> None:
    """Test enemy HP is restored from step state."""
    registry = create_test_combat_registry()
    mock_tui = MockTUI(menu_responses=[2])  # Flee

    # Set up active adventure with existing enemy stats (new format).
    base_player.active_adventure = AdventurePosition(
        adventure_ref="test",
        step_index=0,
        step_state={"enemy_stats": {"hp": 2}},  # Enemy previously damaged
    )

    step = CombatStep(
        type="combat",
        enemy="weak-enemy",  # Normally has 5 HP
        on_win=OutcomeBranch(effects=[], steps=[], goto=None),
        on_defeat=OutcomeBranch(effects=[], steps=[], goto=None),
        on_flee=OutcomeBranch(effects=[], steps=[], goto=None),
    )

    async def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        return AdventureOutcome.FLED

    result = await run_combat(
        step=step, player=base_player, registry=registry, tui=mock_tui, run_outcome_branch=mock_run_outcome_branch
    )

    assert result == AdventureOutcome.FLED
    # Enemy stats should still show hp=2 (unchanged because we fled before any round completes).
    assert base_player.active_adventure.step_state["enemy_stats"]["hp"] == 2


async def test_combat_damage_calculation_with_defense(base_player: CharacterState) -> None:
    """Test formula-based damage: player deals 0 when strength < enemy defense."""
    # Player formula: max(0, strength - defense) * -1  →  0 damage when strength < defense.
    # Enemy formula: attack * -1  →  kills player with hp=5 in one hit.
    armored_enemy = EnemyManifest(
        apiVersion="oscilla/v1",
        kind="Enemy",
        metadata=Metadata(name="armored-enemy"),
        spec=EnemySpec(displayName="Armored Enemy", stats={"hp": 100, "attack": 20, "defense": 15}),
    )
    registry = create_auto_combat_registry(
        enemies=[armored_enemy],
        player_formula="{{ max(0, player.get('strength', 0) - enemy_stats.get('defense', 0)) * -1 }}",
        enemy_formula="{{ max(0, enemy_stats.get('attack', 0)) * -1 }}",
    )

    mock_tui = MockTUI()  # No menu in auto mode.

    base_player.stats["strength"] = 10  # 10 - 15 defense = 0 → no damage to enemy
    base_player.stats["hp"] = 5  # 5 - 20 enemy attack = -15 → defeated in round 1

    step = CombatStep(
        type="combat",
        enemy="armored-enemy",
        on_win=OutcomeBranch(effects=[], steps=[], goto=None),
        on_defeat=OutcomeBranch(effects=[], steps=[], goto=None),
        on_flee=OutcomeBranch(effects=[], steps=[], goto=None),
    )

    async def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        return AdventureOutcome.DEFEATED

    result = await run_combat(
        step=step,
        player=base_player,
        registry=registry,
        tui=mock_tui,
        run_outcome_branch=mock_run_outcome_branch,
    )

    # Enemy survives (player dealt 0 damage); player dies from the counter-attack.
    assert result == AdventureOutcome.DEFEATED
    assert (base_player.stats.get("hp") or 0) <= 0


async def test_combat_dexterity_damage_mitigation(base_player: CharacterState) -> None:
    """Test formula-based mitigation: high dexterity reduces enemy damage to zero."""
    # Player formula: strength * -1  →  1 damage/round to enemy hp=5.
    # Enemy formula: max(0, attack - dexterity//5) * -1  →  0 with dexterity=25.
    registry = create_auto_combat_registry(
        enemies=[
            EnemyManifest(
                apiVersion="oscilla/v1",
                kind="Enemy",
                metadata=Metadata(name="weak-enemy"),
                spec=EnemySpec(displayName="Weak Enemy", stats={"hp": 5, "attack": 2}),
            )
        ],
        player_formula="{{ player.get('strength', 0) * -1 }}",
        enemy_formula="{{ max(0, enemy_stats.get('attack', 0) - player.get('dexterity', 0) // 5) * -1 }}",
    )
    mock_tui = MockTUI()  # No menu in auto mode.

    base_player.stats["strength"] = 1  # 1 damage/round to enemy (hp=5 → defeated in 5 rounds)
    base_player.stats["dexterity"] = 25  # 25 // 5 = 5 mitigation; max(0, 2-5) = 0 incoming damage
    base_player.stats["hp"] = 100
    base_player.stats["max_hp"] = 100

    step = CombatStep(
        type="combat",
        enemy="weak-enemy",
        on_win=OutcomeBranch(effects=[], steps=[], goto=None),
        on_defeat=OutcomeBranch(effects=[], steps=[], goto=None),
        on_flee=OutcomeBranch(effects=[], steps=[], goto=None),
    )

    async def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        return AdventureOutcome.COMPLETED

    result = await run_combat(
        step=step, player=base_player, registry=registry, tui=mock_tui, run_outcome_branch=mock_run_outcome_branch
    )

    # Player took no damage (dexterity fully mitigated the 2-attack enemy).
    assert base_player.stats.get("hp") == 100
    assert result == AdventureOutcome.COMPLETED
