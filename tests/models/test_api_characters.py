"""Unit tests for oscilla/models/api/characters.py assembly helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from oscilla.engine.character import AdventurePosition, CharacterState
from oscilla.engine.models.adventure import (
    AdventureManifest,
    AdventureSpec,
    EndAdventureEffect,
    HealEffect,
    NarrativeStep,
)
from oscilla.engine.models.archetype import ArchetypeManifest, ArchetypeSpec
from oscilla.engine.models.base import GrantRecord, Metadata
from oscilla.engine.models.buff import BuffDuration, BuffManifest, BuffSpec, StoredBuff
from oscilla.engine.models.character_config import CharacterConfigManifest
from oscilla.engine.models.game import GameManifest, GameSpec
from oscilla.engine.models.item import ItemManifest, ItemSpec
from oscilla.engine.models.location import LocationManifest, LocationSpec
from oscilla.engine.models.quest import QuestManifest, QuestSpec, QuestStage
from oscilla.engine.models.region import RegionManifest, RegionSpec
from oscilla.engine.models.skill import SkillManifest, SkillSpec
from oscilla.engine.registry import ContentRegistry
from oscilla.models.api.characters import build_character_state_read, build_character_summary
from oscilla.models.character import CharacterRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_record(
    name: str = "Hero",
    game_name: str = "test-game",
    id: Any = None,
) -> CharacterRecord:
    return CharacterRecord(
        id=id or uuid4(),
        user_id=uuid4(),
        name=name,
        game_name=game_name,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )


def _minimal_registry(
    with_item: bool = False,
    with_skill: bool = False,
    with_buff: bool = False,
    with_quest: bool = False,
    with_archetype: bool = False,
    with_adventure: bool = False,
) -> ContentRegistry:
    registry = ContentRegistry()
    registry.game = GameManifest(
        apiVersion="oscilla/v1",
        kind="Game",
        metadata=Metadata(name="test-game"),
        spec=GameSpec(displayName="Test Game"),
    )
    registry.character_config = CharacterConfigManifest.model_validate(
        {
            "apiVersion": "oscilla/v1",
            "kind": "CharacterConfig",
            "metadata": {"name": "test-game-character-config"},
            "spec": {
                "public_stats": [
                    {"name": "health", "type": "int", "default": 10, "description": "HP"},
                ],
                "hidden_stats": [
                    {"name": "hidden_power", "type": "int", "default": 0},
                ],
            },
        }
    )
    region = RegionManifest(
        apiVersion="oscilla/v1",
        kind="Region",
        metadata=Metadata(name="forest"),
        spec=RegionSpec(displayName="Forest"),
    )
    registry.regions.register(region)
    location = LocationManifest(
        apiVersion="oscilla/v1",
        kind="Location",
        metadata=Metadata(name="clearing"),
        spec=LocationSpec(displayName="Clearing", region="forest"),
    )
    registry.locations.register(location)

    if with_item:
        item = ItemManifest(
            apiVersion="oscilla/v1",
            kind="Item",
            metadata=Metadata(name="sword"),
            spec=ItemSpec(category="weapon", displayName="Iron Sword", description="A trusty blade.", stackable=True),
        )
        registry.items.register(item)

    if with_skill:
        skill = SkillManifest(
            apiVersion="oscilla/v1",
            kind="Skill",
            metadata=Metadata(name="slash"),
            spec=SkillSpec(displayName="Slash", description="A melee attack.", contexts=["combat"]),
        )
        registry.skills.register(skill)

    if with_buff:
        buff = BuffManifest(
            apiVersion="oscilla/v1",
            kind="Buff",
            metadata=Metadata(name="blessed"),
            spec=BuffSpec(
                displayName="Blessed",
                description="Divine favor.",
                duration=BuffDuration(turns=3),
                per_turn_effects=[HealEffect(type="heal", amount=1)],
            ),
        )
        registry.buffs.register(buff)

    if with_quest:
        quest = QuestManifest(
            apiVersion="oscilla/v1",
            kind="Quest",
            metadata=Metadata(name="find-hero"),
            spec=QuestSpec(
                displayName="Find a Hero",
                description="A quest to find a hero.",
                entry_stage="start",
                stages=[
                    QuestStage(name="start", description="Seek a hero.", terminal=True),
                ],
            ),
        )
        registry.quests.register(quest)

    if with_archetype:
        archetype = ArchetypeManifest(
            apiVersion="oscilla/v1",
            kind="Archetype",
            metadata=Metadata(name="warrior"),
            spec=ArchetypeSpec(displayName="Warrior", description="A fierce fighter."),
        )
        registry.archetypes.register(archetype)

    if with_adventure:
        adventure = AdventureManifest(
            apiVersion="oscilla/v1",
            kind="Adventure",
            metadata=Metadata(name="dungeon"),
            spec=AdventureSpec(
                displayName="The Dungeon",
                description="Delve deep.",
                steps=[
                    NarrativeStep(type="narrative", text="You enter the dungeon."),
                    NarrativeStep(
                        type="narrative",
                        text="Done.",
                        effects=[EndAdventureEffect(type="end_adventure", outcome="completed")],
                    ),
                ],
            ),
        )
        registry.adventures.register(adventure)

    return registry


def _minimal_state(registry: ContentRegistry) -> CharacterState:
    assert registry.game is not None
    assert registry.character_config is not None
    return CharacterState.new_character(
        name="Hero",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )


# ---------------------------------------------------------------------------
# build_character_summary tests
# ---------------------------------------------------------------------------


def test_build_character_summary_includes_updated_at() -> None:
    """build_character_summary must include updated_at from the CharacterRecord."""
    record = _fake_record()
    summary = build_character_summary(record=record, prestige_count=0)
    assert summary.updated_at == record.updated_at


def test_build_character_summary_basic_fields() -> None:
    record = _fake_record(name="Aragorn", game_name="middle-earth")
    summary = build_character_summary(record=record, prestige_count=3)
    assert summary.name == "Aragorn"
    assert summary.game_name == "middle-earth"
    assert summary.prestige_count == 3
    assert summary.id == record.id


# ---------------------------------------------------------------------------
# build_character_state_read — character_class absence
# ---------------------------------------------------------------------------


def test_character_state_read_does_not_include_character_class() -> None:
    """CharacterStateRead must not expose a character_class field."""
    registry = _minimal_registry()
    record = _fake_record()
    state = _minimal_state(registry)
    assert registry.character_config is not None
    result = build_character_state_read(
        record=record,
        state=state,
        registry=registry,
        char_config=registry.character_config,
    )
    assert not hasattr(result, "character_class")


# ---------------------------------------------------------------------------
# build_character_state_read — hidden stat filtering
# ---------------------------------------------------------------------------


def test_hidden_stats_excluded_from_api_response() -> None:
    """Public stats appear in the response; hidden stats must be absent."""
    registry = _minimal_registry()
    record = _fake_record()
    state = _minimal_state(registry)
    assert registry.character_config is not None
    result = build_character_state_read(
        record=record,
        state=state,
        registry=registry,
        char_config=registry.character_config,
    )
    assert "health" in result.stats
    # hidden_power must not be exposed
    assert "hidden_power" not in result.stats


# ---------------------------------------------------------------------------
# build_character_state_read — display metadata propagation
# ---------------------------------------------------------------------------


def test_stacked_item_carries_display_metadata() -> None:
    registry = _minimal_registry(with_item=True)
    record = _fake_record()
    state = _minimal_state(registry)
    state.stacks["sword"] = 2
    assert registry.character_config is not None
    result = build_character_state_read(
        record=record,
        state=state,
        registry=registry,
        char_config=registry.character_config,
    )
    assert result.stacks["sword"].display_name == "Iron Sword"
    assert result.stacks["sword"].description == "A trusty blade."


def test_skill_carries_description_and_cooldown_false_when_not_cooling() -> None:
    registry = _minimal_registry(with_skill=True)
    record = _fake_record()
    state = _minimal_state(registry)
    state.known_skills.add("slash")
    assert registry.character_config is not None
    result = build_character_state_read(
        record=record,
        state=state,
        registry=registry,
        char_config=registry.character_config,
    )
    skill = next(s for s in result.skills if s.ref == "slash")
    assert skill.description == "A melee attack."
    assert skill.on_cooldown is False
    assert skill.cooldown_remaining_ticks is None


def test_skill_on_cooldown_when_tick_expiry_in_future() -> None:
    registry = _minimal_registry(with_skill=True)
    record = _fake_record()
    state = _minimal_state(registry)
    state.known_skills.add("slash")
    # Set internal ticks to 10; tick expiry to 20 → 10 ticks remaining
    state.internal_ticks = 10
    state.skill_tick_expiry["slash"] = 20
    assert registry.character_config is not None
    result = build_character_state_read(
        record=record,
        state=state,
        registry=registry,
        char_config=registry.character_config,
    )
    skill = next(s for s in result.skills if s.ref == "slash")
    assert skill.on_cooldown is True
    assert skill.cooldown_remaining_ticks == 10


def test_buff_carries_display_metadata() -> None:
    registry = _minimal_registry(with_buff=True)
    record = _fake_record()
    state = _minimal_state(registry)
    state.active_buffs.append(StoredBuff(buff_ref="blessed", remaining_turns=3))
    assert registry.character_config is not None
    result = build_character_state_read(
        record=record,
        state=state,
        registry=registry,
        char_config=registry.character_config,
    )
    buff = next(b for b in result.active_buffs if b.ref == "blessed")
    assert buff.display_name == "Blessed"
    assert buff.description == "Divine favor."


def test_active_quest_carries_display_metadata() -> None:
    registry = _minimal_registry(with_quest=True)
    record = _fake_record()
    state = _minimal_state(registry)
    state.active_quests["find-hero"] = "start"
    assert registry.character_config is not None
    result = build_character_state_read(
        record=record,
        state=state,
        registry=registry,
        char_config=registry.character_config,
    )
    quest = next(q for q in result.active_quests if q.ref == "find-hero")
    assert quest.quest_display_name == "Find a Hero"
    assert quest.quest_description == "A quest to find a hero."
    assert quest.stage_description == "Seek a hero."


def test_archetype_carries_display_metadata() -> None:
    registry = _minimal_registry(with_archetype=True)
    record = _fake_record()
    state = _minimal_state(registry)
    state.archetypes["warrior"] = GrantRecord(tick=1, timestamp=1000)
    assert registry.character_config is not None
    result = build_character_state_read(
        record=record,
        state=state,
        registry=registry,
        char_config=registry.character_config,
    )
    archetype = next(a for a in result.archetypes if a.ref == "warrior")
    assert archetype.display_name == "Warrior"
    assert archetype.description == "A fierce fighter."


def test_active_adventure_carries_display_metadata() -> None:
    registry = _minimal_registry(with_adventure=True)
    record = _fake_record()
    state = _minimal_state(registry)
    state.active_adventure = AdventurePosition(adventure_ref="dungeon", step_index=0)
    assert registry.character_config is not None
    result = build_character_state_read(
        record=record,
        state=state,
        registry=registry,
        char_config=registry.character_config,
    )
    assert result.active_adventure is not None
    assert result.active_adventure.display_name == "The Dungeon"
    assert result.active_adventure.description == "Delve deep."
