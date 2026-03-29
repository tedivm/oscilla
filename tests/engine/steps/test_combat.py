"""Tests for combat step handler."""

from __future__ import annotations

from oscilla.engine.models.adventure import CombatStep, OutcomeBranch
from oscilla.engine.models.base import Metadata
from oscilla.engine.models.enemy import EnemyManifest, EnemySpec
from oscilla.engine.pipeline import AdventureOutcome
from oscilla.engine.character import AdventurePosition, CharacterState
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.steps.combat import run_combat
from tests.engine.conftest import MockTUI


def create_test_combat_registry() -> ContentRegistry:
    """Create a registry with test enemy for combat testing."""
    registry = ContentRegistry()

    # Add weak enemy for testing
    weak_enemy = EnemyManifest(
        apiVersion="game/v1",
        kind="Enemy",
        metadata=Metadata(name="weak-enemy"),
        spec=EnemySpec(displayName="Weak Enemy", hp=5, attack=2, defense=0, xp_reward=10),
    )
    registry.enemies.register(weak_enemy)

    # Add strong enemy for testing defeat
    strong_enemy = EnemyManifest(
        apiVersion="game/v1",
        kind="Enemy",
        metadata=Metadata(name="strong-enemy"),
        spec=EnemySpec(displayName="Strong Enemy", hp=100, attack=50, defense=0, xp_reward=50),
    )
    registry.enemies.register(strong_enemy)

    return registry


async def test_combat_win_scenario(base_player: CharacterState) -> None:
    """Test winning a combat scenario."""
    registry = create_test_combat_registry()
    mock_tui = MockTUI(menu_responses=[1])  # Always attack

    # Set up high strength to defeat weak enemy quickly
    base_player.stats["strength"] = 20
    base_player.hp = 100
    base_player.max_hp = 100

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
    base_player.hp = 10
    base_player.max_hp = 10

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
    assert base_player.hp == 0


async def test_combat_stat_handling_non_numeric(base_player: CharacterState) -> None:
    """Test combat with non-numeric stats falls back to defaults."""
    registry = create_test_combat_registry()
    mock_tui = MockTUI(menu_responses=[1])  # Attack

    # Set non-numeric stats
    base_player.stats["strength"] = "strong"  # Non-numeric
    base_player.stats["dexterity"] = "agile"  # Non-numeric
    base_player.hp = 100

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

    # Set up active adventure with existing enemy HP
    base_player.active_adventure = AdventurePosition(
        adventure_ref="test",
        step_index=0,
        step_state={"enemy_hp": 2},  # Enemy previously damaged
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
    # Enemy HP should still be 2 in step state (unchanged because we fled immediately)
    assert base_player.active_adventure.step_state["enemy_hp"] == 2


async def test_combat_damage_calculation_with_defense(base_player: CharacterState) -> None:
    """Test damage calculation respects enemy defense (player deals 0 damage when strength < defense)."""
    registry = ContentRegistry()

    # Enemy with defense (15) higher than player strength (10), so player deals no damage.
    # High attack (20) so the enemy kills the player in one counter-attack.
    high_def_enemy = EnemyManifest(
        apiVersion="game/v1",
        kind="Enemy",
        metadata=Metadata(name="armored-enemy"),
        spec=EnemySpec(displayName="Armored Enemy", hp=100, attack=20, defense=15, xp_reward=10),
    )
    registry.enemies.register(high_def_enemy)

    mock_tui = MockTUI(menu_responses=[1])  # Attack once, then the enemy counter-attack kills the player

    base_player.stats["strength"] = 10  # 10 - 15 defense = 0 damage (clamped to 0)
    base_player.hp = 5  # Low enough that enemy counter-attack (20 - dex_mitigation) kills in one hit

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

    # Enemy survives because player dealt 0 damage; player dies from the counter-attack.
    assert result == AdventureOutcome.DEFEATED
    assert base_player.hp == 0


async def test_combat_dexterity_damage_mitigation(base_player: CharacterState) -> None:
    """Test dexterity provides damage mitigation."""
    registry = create_test_combat_registry()
    mock_tui = MockTUI(menu_responses=[1, 2])  # Attack then flee

    # High dexterity for mitigation testing
    base_player.stats["strength"] = 1  # Low damage to enemy
    base_player.stats["dexterity"] = 25  # 25 // 5 = 5 mitigation
    base_player.hp = 100
    base_player.max_hp = 100

    step = CombatStep(
        type="combat",
        enemy="weak-enemy",  # 2 attack - 5 mitigation = 0 damage (max with 0)
        on_win=OutcomeBranch(effects=[], steps=[], goto=None),
        on_defeat=OutcomeBranch(effects=[], steps=[], goto=None),
        on_flee=OutcomeBranch(effects=[], steps=[], goto=None),
    )

    async def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        return AdventureOutcome.FLED

    result = await run_combat(
        step=step, player=base_player, registry=registry, tui=mock_tui, run_outcome_branch=mock_run_outcome_branch
    )

    # Player should take no damage due to high dexterity
    assert base_player.hp == 100
    assert result == AdventureOutcome.FLED
