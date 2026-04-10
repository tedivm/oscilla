"""Tests for CharacterState — factory, inventory, milestones, equipment, serialization."""

from __future__ import annotations

import time
from uuid import UUID, uuid4

import pytest

from oscilla.engine.character import _INT64_MAX, _INT64_MIN, CharacterState, ItemInstance
from oscilla.engine.models.adventure import AdventureSpec, Cooldown
from oscilla.engine.models.base import GrantRecord
from oscilla.engine.registry import ContentRegistry


def test_new_player_defaults(base_player: CharacterState) -> None:
    assert base_player.stacks == {}
    assert base_player.instances == []
    assert base_player.milestones == {}
    assert base_player.active_adventure is None


def test_new_player_stats_from_char_config(base_player: CharacterState) -> None:
    # The minimal fixture defines strength with default 10
    assert base_player.stats["strength"] == 10


def test_grant_and_has_milestone(base_player: CharacterState) -> None:
    assert not base_player.has_milestone("test-flag")
    base_player.grant_milestone("test-flag")
    assert base_player.has_milestone("test-flag")


def test_grant_milestone_idempotent(base_player: CharacterState) -> None:
    base_player.grant_milestone("idempotent-flag")
    base_player.grant_milestone("idempotent-flag")
    # Dict deduplicates — should still only appear once
    assert base_player.has_milestone("idempotent-flag")
    assert sum(1 for m in base_player.milestones if m == "idempotent-flag") == 1


def test_add_and_remove_item(base_player: CharacterState) -> None:
    base_player.add_item(ref="potion", quantity=3)
    assert base_player.stacks["potion"] == 3
    base_player.remove_item(ref="potion", quantity=2)
    assert base_player.stacks["potion"] == 1
    base_player.remove_item(ref="potion", quantity=1)
    assert "potion" not in base_player.stacks


def test_remove_item_raises_on_insufficient(base_player: CharacterState) -> None:
    with pytest.raises(ValueError, match="Cannot remove"):
        base_player.remove_item(ref="missing-item", quantity=1)


def test_equip_item(base_player: CharacterState) -> None:
    inst = ItemInstance(instance_id=UUID("00000000-0000-0000-0000-000000000001"), item_ref="iron-sword")
    base_player.instances.append(inst)
    base_player.equip_instance(instance_id=inst.instance_id, slots=["weapon"])
    assert base_player.equipment["weapon"] == inst.instance_id
    # Instance stays in instances list — equipment dict records the slot mapping
    assert inst in base_player.instances


def test_equip_displaces_existing(base_player: CharacterState) -> None:
    inst1 = ItemInstance(instance_id=UUID("00000000-0000-0000-0000-000000000001"), item_ref="iron-sword")
    inst2 = ItemInstance(instance_id=UUID("00000000-0000-0000-0000-000000000002"), item_ref="golden-sword")
    base_player.instances.extend([inst1, inst2])
    base_player.equip_instance(instance_id=inst1.instance_id, slots=["weapon"])
    base_player.equip_instance(instance_id=inst2.instance_id, slots=["weapon"])
    assert base_player.equipment["weapon"] == inst2.instance_id
    # displaced item returned to instances
    assert inst1 in base_player.instances


def test_equip_raises_if_not_in_instances(base_player: CharacterState) -> None:
    with pytest.raises(ValueError, match="not found"):
        base_player.equip_instance(instance_id=UUID("00000000-0000-0000-0000-000000000099"), slots=["weapon"])


def test_record_tracking_methods(base_player: CharacterState) -> None:
    """Test enemy defeated, location visited, and adventure completed tracking."""
    # Test enemy defeated tracking
    base_player.statistics.record_enemy_defeated("goblin")
    base_player.statistics.record_enemy_defeated("goblin")
    base_player.statistics.record_enemy_defeated("orc")
    assert base_player.statistics.enemies_defeated["goblin"] == 2
    assert base_player.statistics.enemies_defeated["orc"] == 1

    # Test location visited tracking
    base_player.statistics.record_location_visited("forest")
    base_player.statistics.record_location_visited("forest")
    base_player.statistics.record_location_visited("cave")
    assert base_player.statistics.locations_visited["forest"] == 2
    assert base_player.statistics.locations_visited["cave"] == 1

    # Test adventure completed tracking
    base_player.statistics.record_adventure_completed("quest-1")
    base_player.statistics.record_adventure_completed("quest-1")
    base_player.statistics.record_adventure_completed("quest-2")
    assert base_player.statistics.adventures_completed["quest-1"] == 2
    assert base_player.statistics.adventures_completed["quest-2"] == 1


# ---------------------------------------------------------------------------
# CharacterState.set_stat() — INT64 clamp backstop tests
# ---------------------------------------------------------------------------


def _make_bare_player() -> CharacterState:
    return CharacterState(
        character_id=uuid4(),
        name="T",
        character_class=None,
        prestige_count=0,
        current_location=None,
        stats={"gold": 100},
    )


def test_set_stat_within_range_is_unchanged() -> None:
    player = _make_bare_player()
    player.set_stat(name="gold", value=500)
    assert player.stats["gold"] == 500


def test_set_stat_clamps_above_int64_max(caplog: pytest.LogCaptureFixture) -> None:
    player = _make_bare_player()
    over = _INT64_MAX + 1
    with caplog.at_level("WARNING"):
        player.set_stat(name="gold", value=over)
    assert player.stats["gold"] == _INT64_MAX
    assert "clamped" in caplog.text


def test_set_stat_clamps_below_int64_min(caplog: pytest.LogCaptureFixture) -> None:
    player = _make_bare_player()
    under = _INT64_MIN - 1
    with caplog.at_level("WARNING"):
        player.set_stat(name="gold", value=under)
    assert player.stats["gold"] == _INT64_MIN
    assert "clamped" in caplog.text


def test_set_stat_at_int64_boundary_is_not_clamped() -> None:
    player = _make_bare_player()
    player.set_stat(name="gold", value=_INT64_MAX)
    assert player.stats["gold"] == _INT64_MAX
    player.set_stat(name="gold", value=_INT64_MIN)
    assert player.stats["gold"] == _INT64_MIN


# ---------------------------------------------------------------------------
# CharacterState serialization — tick fields (task 10.5)
# ---------------------------------------------------------------------------


def test_ticks_round_trip(minimal_registry: ContentRegistry) -> None:
    """internal_ticks and game_ticks survive a to_dict()/from_dict() round-trip."""
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="TickTester",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    player.internal_ticks = 42
    player.game_ticks = 17
    player.era_started_at_ticks = {"ancient": 5}
    player.era_ended_at_ticks = {"ancient": 10}
    player.adventure_last_completed_at_ticks = {"quest-x": 3}

    data = player.to_dict()
    assert data["internal_ticks"] == 42
    assert data["game_ticks"] == 17

    restored = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    assert restored.internal_ticks == 42
    assert restored.game_ticks == 17
    assert restored.era_started_at_ticks == {"ancient": 5}
    assert restored.era_ended_at_ticks == {"ancient": 10}
    assert restored.adventure_last_completed_at_ticks == {"quest-x": 3}


def test_ticks_default_to_zero_when_absent(minimal_registry: ContentRegistry) -> None:
    """Deserializing an old save without tick keys produces zeros (backward compat)."""
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="OldSave",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    data = player.to_dict()
    # Simulate an old save by removing the new keys.
    data.pop("internal_ticks", None)
    data.pop("game_ticks", None)
    data.pop("era_started_at_ticks", None)
    data.pop("era_ended_at_ticks", None)
    data.pop("adventure_last_completed_at_ticks", None)

    restored = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    assert restored.internal_ticks == 0
    assert restored.game_ticks == 0
    assert restored.era_started_at_ticks == {}
    assert restored.era_ended_at_ticks == {}
    assert restored.adventure_last_completed_at_ticks == {}


def test_old_adventure_tick_key_mapped_to_new_key(minimal_registry: ContentRegistry) -> None:
    """adventure_last_completed_at_total (deprecated key) maps to adventure_last_completed_at_ticks."""
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="Migration",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    data = player.to_dict()
    # Simulate an old save using the deprecated key name.
    data.pop("adventure_last_completed_at_ticks", None)
    data["adventure_last_completed_at_total"] = {"old-quest": 7}

    restored = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    assert restored.adventure_last_completed_at_ticks == {"old-quest": 7}


def test_new_adventure_tick_key_takes_precedence(minimal_registry: ContentRegistry) -> None:
    """New key adventure_last_completed_at_ticks wins over the deprecated key when both present."""
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="Precedence",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    data = player.to_dict()
    data["adventure_last_completed_at_ticks"] = {"new-quest": 99}
    data["adventure_last_completed_at_total"] = {"old-quest": 1}

    restored = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    # new key takes precedence; old key is ignored
    assert restored.adventure_last_completed_at_ticks == {"new-quest": 99}
    assert "old-quest" not in restored.adventure_last_completed_at_ticks


# ---------------------------------------------------------------------------
# grant_milestone — tick/timestamp recording (tasks 14.1-14.2)
# ---------------------------------------------------------------------------


def test_grant_milestone_records_tick_and_timestamp(base_player: CharacterState) -> None:
    """grant_milestone() records internal_ticks and a positive timestamp."""
    base_player.internal_ticks = 7
    before = int(time.time())
    base_player.grant_milestone("joined-guild")
    after = int(time.time())

    record = base_player.milestones["joined-guild"]
    assert record.tick == 7
    assert before <= record.timestamp <= after


def test_grant_milestone_noop_if_already_held(base_player: CharacterState) -> None:
    """Re-granting a milestone must not overwrite the original GrantRecord."""
    base_player.internal_ticks = 3
    base_player.grant_milestone("joined-guild")
    original_tick = base_player.milestones["joined-guild"].tick
    original_ts = base_player.milestones["joined-guild"].timestamp

    base_player.internal_ticks = 99
    base_player.grant_milestone("joined-guild")

    record = base_player.milestones["joined-guild"]
    assert record.tick == original_tick
    assert record.timestamp == original_ts


# ---------------------------------------------------------------------------
# from_dict — milestone migration (tasks 14.3-14.4)
# ---------------------------------------------------------------------------


def test_from_dict_migrates_milestone_list(minimal_registry: ContentRegistry) -> None:
    """Old list milestone format migrates to GrantRecord(tick=0, timestamp=0)."""
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="MigList",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    data = player.to_dict()
    data["milestones"] = ["alpha", "beta"]

    restored = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    assert "alpha" in restored.milestones
    assert "beta" in restored.milestones
    assert restored.milestones["alpha"] == GrantRecord(tick=0, timestamp=0)
    assert restored.milestones["beta"] == GrantRecord(tick=0, timestamp=0)


def test_from_dict_migrates_milestone_int_dict(minimal_registry: ContentRegistry) -> None:
    """Intermediate int-dict milestone format migrates to GrantRecord(tick=N, timestamp=0)."""
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="MigInt",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    data = player.to_dict()
    data["milestones"] = {"alpha": 42, "beta": 0}

    restored = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    assert restored.milestones["alpha"] == GrantRecord(tick=42, timestamp=0)
    assert restored.milestones["beta"] == GrantRecord(tick=0, timestamp=0)


# ---------------------------------------------------------------------------
# from_dict — __game__ prefix migration (task 14.5)
# ---------------------------------------------------------------------------


def test_from_dict_migrates_game_prefix_from_at_ticks(minimal_registry: ContentRegistry) -> None:
    """__game__ prefixed entries in adventure_last_completed_at_ticks migrate to game_ticks dict."""
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="MigGame",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    data = player.to_dict()
    data["adventure_last_completed_at_ticks"] = {
        "regular-quest": 5,
        "__game__dungeon-raid": 7,
    }
    data.pop("adventure_last_completed_game_ticks", None)

    restored = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    assert restored.adventure_last_completed_at_ticks == {"regular-quest": 5}
    assert restored.adventure_last_completed_game_ticks == {"dungeon-raid": 7}


# ---------------------------------------------------------------------------
# is_adventure_eligible — ticks and seconds cooldowns (tasks 14.6-14.8)
# ---------------------------------------------------------------------------


def _make_bare_eligible_player() -> CharacterState:
    """Minimal CharacterState for is_adventure_eligible tests."""
    return CharacterState(
        character_id=uuid4(),
        name="EligTest",
        character_class=None,
        prestige_count=0,
        current_location=None,
        stats={},
    )


def test_is_adventure_eligible_ticks_cooldown_blocks_then_allows() -> None:
    """Cooldown(ticks=5) blocks until 5 more internal ticks have elapsed."""
    player = _make_bare_eligible_player()
    spec = AdventureSpec(
        displayName="Tick Cooldown",
        steps=[],
        cooldown=Cooldown(ticks=5),
        repeatable=True,
    )
    now_ts = int(time.time())

    # No prior completion — eligible
    assert player.is_adventure_eligible(adventure_ref="test-adv", spec=spec, now_ts=now_ts) is True

    # Record completion at tick 10
    player.internal_ticks = 10
    player.adventure_last_completed_at_ticks["test-adv"] = 10

    # At tick 14 (only 4 elapsed) — still blocked
    player.internal_ticks = 14
    assert player.is_adventure_eligible(adventure_ref="test-adv", spec=spec, now_ts=now_ts) is False

    # At tick 15 (exactly 5 elapsed) — now eligible
    player.internal_ticks = 15
    assert player.is_adventure_eligible(adventure_ref="test-adv", spec=spec, now_ts=now_ts) is True


def test_is_adventure_eligible_seconds_cooldown_blocks_then_allows() -> None:
    """Cooldown(seconds=3600) blocks until 3600 real seconds have elapsed."""
    player = _make_bare_eligible_player()
    spec = AdventureSpec(
        displayName="Seconds Cooldown",
        steps=[],
        cooldown=Cooldown(seconds=3600),
        repeatable=True,
    )

    base_ts = 1_700_000_000
    player.adventure_last_completed_real_ts["test-adv"] = base_ts

    # 3599 seconds later — blocked
    assert player.is_adventure_eligible(adventure_ref="test-adv", spec=spec, now_ts=base_ts + 3599) is False

    # 3600 seconds later — eligible
    assert player.is_adventure_eligible(adventure_ref="test-adv", spec=spec, now_ts=base_ts + 3600) is True


def test_is_adventure_eligible_multiple_constraints_anded() -> None:
    """Cooldown(ticks=5, seconds=3600): both constraints must pass independently."""
    player = _make_bare_eligible_player()
    spec = AdventureSpec(
        displayName="Both Cooldowns",
        steps=[],
        cooldown=Cooldown(ticks=5, seconds=3600),
        repeatable=True,
    )

    base_ts = 1_700_000_000
    player.internal_ticks = 10
    player.adventure_last_completed_at_ticks["test-adv"] = 10
    player.adventure_last_completed_real_ts["test-adv"] = base_ts

    # Ticks met (15 - 10 = 5), seconds not met (only 100s elapsed) → blocked
    player.internal_ticks = 15
    assert player.is_adventure_eligible(adventure_ref="test-adv", spec=spec, now_ts=base_ts + 100) is False

    # Seconds met, ticks not met (only 4 elapsed) → blocked
    player.internal_ticks = 14
    assert player.is_adventure_eligible(adventure_ref="test-adv", spec=spec, now_ts=base_ts + 3600) is False

    # Both met → eligible
    player.internal_ticks = 15
    assert player.is_adventure_eligible(adventure_ref="test-adv", spec=spec, now_ts=base_ts + 3600) is True


# ---------------------------------------------------------------------------
# Archetype serialization tests (task 8.2)
# ---------------------------------------------------------------------------


def test_to_dict_emits_archetypes(base_player: CharacterState) -> None:
    """to_dict() serializes archetypes as a nested tick/timestamp dict."""
    base_player.archetypes["warrior"] = GrantRecord(tick=5, timestamp=1_700_000_000)
    data = base_player.to_dict()
    assert "archetypes" in data
    assert data["archetypes"]["warrior"] == {"tick": 5, "timestamp": 1_700_000_000}


def test_from_dict_round_trips_archetypes(
    base_player: CharacterState,
    minimal_registry: ContentRegistry,
) -> None:
    """from_dict() reconstructs GrantRecord objects from the serialized form."""
    assert minimal_registry.character_config is not None
    base_player.archetypes["warrior"] = GrantRecord(tick=5, timestamp=1_700_000_000)
    data = base_player.to_dict()

    restored = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    assert "warrior" in restored.archetypes
    assert restored.archetypes["warrior"].tick == 5
    assert restored.archetypes["warrior"].timestamp == 1_700_000_000


def test_from_dict_legacy_list_migrates_to_grant_record(
    base_player: CharacterState,
    minimal_registry: ContentRegistry,
) -> None:
    """A legacy list of archetype names migrates to GrantRecord(tick=0, timestamp=0)."""
    assert minimal_registry.character_config is not None
    data = base_player.to_dict()
    data["archetypes"] = ["warrior", "mage"]

    restored = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    assert restored.archetypes["warrior"] == GrantRecord(tick=0, timestamp=0)
    assert restored.archetypes["mage"] == GrantRecord(tick=0, timestamp=0)


def test_from_dict_drops_unknown_archetypes_with_registry(
    base_player: CharacterState,
    minimal_registry: ContentRegistry,
) -> None:
    """With a registry, archetype names not in the registry are dropped (content drift)."""
    from oscilla.engine.models.archetype import ArchetypeManifest, ArchetypeSpec
    from oscilla.engine.models.base import Metadata

    assert minimal_registry.character_config is not None
    minimal_registry.archetypes.register(
        ArchetypeManifest(
            apiVersion="oscilla/v1",
            kind="Archetype",
            metadata=Metadata(name="warrior"),
            spec=ArchetypeSpec(displayName="Warrior"),
        )
    )

    data = base_player.to_dict()
    data["archetypes"] = {
        "warrior": {"tick": 1, "timestamp": 100},
        "ghost": {"tick": 2, "timestamp": 200},  # not in registry
    }

    restored = CharacterState.from_dict(
        data=data,
        character_config=minimal_registry.character_config,
        registry=minimal_registry,
    )
    assert "warrior" in restored.archetypes
    assert "ghost" not in restored.archetypes


def test_from_dict_keeps_unknown_archetypes_without_registry(
    base_player: CharacterState,
    minimal_registry: ContentRegistry,
) -> None:
    """Without a registry, unknown archetypes are preserved (no filter possible)."""
    assert minimal_registry.character_config is not None
    data = base_player.to_dict()
    data["archetypes"] = {"ghost": {"tick": 2, "timestamp": 200}}

    restored = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    assert "ghost" in restored.archetypes
