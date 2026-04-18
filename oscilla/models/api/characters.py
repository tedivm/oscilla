"""API request/response models for character endpoints."""

from datetime import datetime
from typing import TYPE_CHECKING, Dict, List
from uuid import UUID

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.models.character_config import CharacterConfigManifest
    from oscilla.engine.registry import ContentRegistry
    from oscilla.models.character import CharacterRecord


# ---------------------------------------------------------------------------
# Sub-models used inside CharacterStateRead
# ---------------------------------------------------------------------------


class StatValue(BaseModel):
    """Current value of a single character stat."""

    ref: str = Field(description="Stat identifier from character_config.")
    display_name: str | None = Field(default=None, description="Human-readable stat name, if described.")
    value: int | bool | None = Field(default=None, description="Current stat value; None for unset or derived stats.")


class StackedItemRead(BaseModel):
    """Stackable inventory item with quantity."""

    ref: str = Field(description="Item manifest reference.")
    quantity: int = Field(description="Number of this item in the stack.")
    display_name: str | None = Field(default=None, description="Human-readable item name.")
    description: str | None = Field(default=None, description="Item description.")


class ItemInstanceRead(BaseModel):
    """Non-stackable item instance."""

    instance_id: UUID = Field(description="Unique instance identifier.")
    item_ref: str = Field(description="Item manifest reference.")
    charges_remaining: int | None = Field(default=None, description="Remaining charges, if the item has charges.")
    modifiers: Dict[str, int] = Field(default_factory=dict, description="Per-instance stat modifiers.")
    display_name: str | None = Field(default=None, description="Human-readable item name.")
    description: str | None = Field(default=None, description="Item description.")


class SkillRead(BaseModel):
    """A skill known by the character."""

    ref: str = Field(description="Skill manifest reference.")
    display_name: str | None = Field(default=None, description="Human-readable skill name.")
    description: str | None = Field(default=None, description="Skill description.")
    on_cooldown: bool = Field(default=False, description="True if the skill is currently on cooldown.")
    cooldown_remaining_ticks: int | None = Field(
        default=None,
        description="Internal ticks remaining on the cooldown, if on cooldown.",
    )


class BuffRead(BaseModel):
    """An active persistent buff on the character."""

    ref: str = Field(description="Buff manifest reference.")
    remaining_turns: int | None = Field(default=None, description="Turns remaining, if turn-scoped.")
    tick_expiry: int | None = Field(default=None, description="Internal tick at which the buff expires.")
    game_tick_expiry: int | None = Field(default=None, description="Game tick at which the buff expires.")
    real_ts_expiry: int | None = Field(default=None, description="Unix timestamp at which the buff expires.")
    display_name: str | None = Field(default=None, description="Human-readable buff name.")
    description: str | None = Field(default=None, description="Buff description.")


class ActiveQuestRead(BaseModel):
    """A quest currently tracked by the character."""

    ref: str = Field(description="Quest manifest reference.")
    current_stage: str = Field(description="Current stage name within the quest.")
    quest_display_name: str | None = Field(default=None, description="Human-readable quest name.")
    quest_description: str | None = Field(default=None, description="Quest-level description.")
    stage_description: str | None = Field(default=None, description="Description of the current stage.")


class MilestoneRead(BaseModel):
    """A milestone held by the character."""

    ref: str = Field(description="Milestone name.")
    grant_tick: int = Field(description="Internal tick when the milestone was granted.")
    grant_timestamp: int = Field(description="Unix timestamp when the milestone was granted.")


class ArchetypeRead(BaseModel):
    """An archetype held by the character."""

    ref: str = Field(description="Archetype manifest reference.")
    grant_tick: int = Field(description="Internal tick when the archetype was granted.")
    grant_timestamp: int = Field(description="Unix timestamp when the archetype was granted.")
    display_name: str | None = Field(default=None, description="Human-readable archetype name.")
    description: str | None = Field(default=None, description="Archetype description.")


class ActiveAdventureRead(BaseModel):
    """The character's currently active adventure position."""

    adventure_ref: str = Field(description="Adventure manifest reference.")
    step_index: int = Field(description="Current step index within the adventure.")
    display_name: str | None = Field(default=None, description="Human-readable adventure name.")
    description: str | None = Field(default=None, description="Adventure description.")


# ---------------------------------------------------------------------------
# Top-level character models
# ---------------------------------------------------------------------------


class CharacterSummaryRead(BaseModel):
    """Lightweight character summary for list responses."""

    id: UUID = Field(description="Character identifier.")
    name: str = Field(description="Character display name.")
    game_name: str = Field(description="Game this character belongs to.")
    prestige_count: int = Field(description="Number of completed prestige cycles.")
    created_at: datetime = Field(description="When the character was created.")
    updated_at: datetime = Field(description="When the character was last modified.")


class CharacterStateRead(BaseModel):
    """Complete character state — the full contract for GET /characters/{id}.

    This schema is additive-only: fields are never removed or renamed.
    """

    # Identity
    id: UUID = Field(description="Character identifier.")
    name: str = Field(description="Character display name.")
    game_name: str = Field(description="Game this character belongs to.")
    prestige_count: int = Field(description="Number of completed prestige cycles.")
    pronoun_set: str = Field(description="Pronoun set key (e.g. 'they_them', 'she_her').")
    created_at: datetime = Field(description="When the character was created.")

    # Stats (all declared stats; value=None for derived or unset stats)
    stats: Dict[str, StatValue] = Field(default_factory=dict, description="All declared stats with current values.")

    # Inventory
    stacks: Dict[str, StackedItemRead] = Field(default_factory=dict, description="Stackable items in inventory.")
    instances: List[ItemInstanceRead] = Field(default_factory=list, description="Non-stackable item instances.")
    equipment: Dict[str, ItemInstanceRead] = Field(
        default_factory=dict, description="Equipped items keyed by slot name."
    )

    # Skills
    skills: List[SkillRead] = Field(default_factory=list, description="Skills known by the character.")

    # Buffs
    active_buffs: List[BuffRead] = Field(default_factory=list, description="Active persistent buffs.")

    # Quests
    active_quests: List[ActiveQuestRead] = Field(default_factory=list, description="Quests currently in progress.")
    completed_quests: List[str] = Field(default_factory=list, description="Refs of completed quests.")
    failed_quests: List[str] = Field(default_factory=list, description="Refs of failed quests.")

    # Milestones
    milestones: Dict[str, MilestoneRead] = Field(default_factory=dict, description="Milestones held by the character.")

    # Archetypes
    archetypes: List[ArchetypeRead] = Field(
        default_factory=list, description="Archetypes held by the character this iteration."
    )

    # Progress counters
    internal_ticks: int = Field(description="Monotone internal tick counter.")
    game_ticks: int = Field(description="Narrative game tick counter.")

    # Adventure state
    active_adventure: ActiveAdventureRead | None = Field(
        default=None, description="Active adventure position, if in an adventure."
    )


class CharacterCreate(BaseModel):
    """Request body for POST /characters."""

    game_name: str = Field(description="Game this character belongs to.")


class CharacterUpdate(BaseModel):
    """Request body for PATCH /characters/{id}. All fields are optional."""

    name: str | None = Field(default=None, max_length=200, description="New character display name.")


# ---------------------------------------------------------------------------
# Assembly helpers
# ---------------------------------------------------------------------------


def build_character_summary(record: "CharacterRecord", prestige_count: int) -> CharacterSummaryRead:
    """Build a CharacterSummaryRead from a CharacterRecord and prestige counter."""
    return CharacterSummaryRead(
        id=record.id,
        name=record.name,
        game_name=record.game_name,
        prestige_count=prestige_count,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def build_character_state_read(
    record: "CharacterRecord",
    state: "CharacterState",
    registry: "ContentRegistry",
    char_config: "CharacterConfigManifest",
) -> CharacterStateRead:
    """Assemble a CharacterStateRead from the DB record, loaded state, and content registry."""
    from oscilla.engine.templates import PRONOUN_SETS

    pronoun_set_key = next((k for k, v in PRONOUN_SETS.items() if v == state.pronouns), "they_them")

    # Build stats dict from only public stats in character_config (hidden stats excluded)
    stats: Dict[str, StatValue] = {}
    for stat_def in char_config.spec.public_stats:
        value = state.stats.get(stat_def.name)  # None for derived stats (never stored)
        stats[stat_def.name] = StatValue(
            ref=stat_def.name,
            display_name=stat_def.description or None,
            value=value,
        )

    # Stacks
    stacks: Dict[str, StackedItemRead] = {}
    for ref, qty in state.stacks.items():
        item_manifest = registry.items.get(ref)
        stacks[ref] = StackedItemRead(
            ref=ref,
            quantity=qty,
            display_name=item_manifest.spec.displayName if item_manifest is not None else None,
            description=item_manifest.spec.description or None if item_manifest is not None else None,
        )

    # Item instances indexed by instance_id for equipment lookup
    instance_map: Dict[UUID, ItemInstanceRead] = {}
    for inst in state.instances:
        item_manifest = registry.items.get(inst.item_ref)
        instance_map[inst.instance_id] = ItemInstanceRead(
            instance_id=inst.instance_id,
            item_ref=inst.item_ref,
            charges_remaining=inst.charges_remaining,
            modifiers=dict(inst.modifiers),
            display_name=item_manifest.spec.displayName if item_manifest is not None else None,
            description=item_manifest.spec.description or None if item_manifest is not None else None,
        )
    instances: List[ItemInstanceRead] = list(instance_map.values())

    # Equipment: slot → ItemInstanceRead
    equipment: Dict[str, ItemInstanceRead] = {}
    for slot, instance_id in state.equipment.items():
        inst_read = instance_map.get(instance_id)
        if inst_read is not None:
            equipment[slot] = inst_read

    # Skills — include ref, display name, description, and cooldown state from registry
    skills: List[SkillRead] = []
    for skill_ref in sorted(state.known_skills):
        skill_manifest = registry.skills.get(skill_ref)
        tick_expiry = state.skill_tick_expiry.get(skill_ref)
        on_cooldown = tick_expiry is not None and tick_expiry > state.internal_ticks
        skills.append(
            SkillRead(
                ref=skill_ref,
                display_name=skill_manifest.spec.displayName if skill_manifest is not None else None,
                description=skill_manifest.spec.description or None if skill_manifest is not None else None,
                on_cooldown=on_cooldown,
                cooldown_remaining_ticks=(tick_expiry - state.internal_ticks)
                if (on_cooldown and tick_expiry is not None)
                else None,
            )
        )

    # Active buffs
    active_buffs: List[BuffRead] = []
    for sb in state.active_buffs:
        buff_manifest = registry.buffs.get(sb.buff_ref)
        active_buffs.append(
            BuffRead(
                ref=sb.buff_ref,
                remaining_turns=sb.remaining_turns,
                tick_expiry=sb.tick_expiry,
                game_tick_expiry=sb.game_tick_expiry,
                real_ts_expiry=sb.real_ts_expiry,
                display_name=buff_manifest.spec.displayName if buff_manifest is not None else None,
                description=buff_manifest.spec.description or None if buff_manifest is not None else None,
            )
        )

    # Active quests
    active_quests: List[ActiveQuestRead] = []
    for ref, stage_name in state.active_quests.items():
        quest_manifest = registry.quests.get(ref)
        stage_description: str | None = None
        if quest_manifest is not None:
            matching_stage = next((s for s in quest_manifest.spec.stages if s.name == stage_name), None)
            stage_description = matching_stage.description or None if matching_stage is not None else None
        active_quests.append(
            ActiveQuestRead(
                ref=ref,
                current_stage=stage_name,
                quest_display_name=quest_manifest.spec.displayName if quest_manifest is not None else None,
                quest_description=quest_manifest.spec.description or None if quest_manifest is not None else None,
                stage_description=stage_description,
            )
        )

    # Milestones
    milestones: Dict[str, MilestoneRead] = {
        ref: MilestoneRead(ref=ref, grant_tick=gr.tick, grant_timestamp=gr.timestamp)
        for ref, gr in state.milestones.items()
    }

    # Archetypes
    archetypes: List[ArchetypeRead] = []
    for ref, gr in state.archetypes.items():
        archetype_manifest = registry.archetypes.get(ref)
        archetypes.append(
            ArchetypeRead(
                ref=ref,
                grant_tick=gr.tick,
                grant_timestamp=gr.timestamp,
                display_name=archetype_manifest.spec.displayName if archetype_manifest is not None else None,
                description=archetype_manifest.spec.description or None if archetype_manifest is not None else None,
            )
        )

    # Active adventure
    active_adventure: ActiveAdventureRead | None = None
    if state.active_adventure is not None:
        adv_manifest = registry.adventures.get(state.active_adventure.adventure_ref)
        active_adventure = ActiveAdventureRead(
            adventure_ref=state.active_adventure.adventure_ref,
            step_index=state.active_adventure.step_index,
            display_name=adv_manifest.spec.displayName if adv_manifest is not None else None,
            description=adv_manifest.spec.description or None if adv_manifest is not None else None,
        )

    return CharacterStateRead(
        id=state.character_id,
        name=record.name,
        game_name=record.game_name,
        prestige_count=state.prestige_count,
        pronoun_set=pronoun_set_key,
        created_at=record.created_at,
        stats=stats,
        stacks=stacks,
        instances=instances,
        equipment=equipment,
        skills=skills,
        active_buffs=active_buffs,
        active_quests=active_quests,
        completed_quests=sorted(state.completed_quests),
        failed_quests=sorted(state.failed_quests),
        milestones=milestones,
        archetypes=archetypes,
        internal_ticks=state.internal_ticks,
        game_ticks=state.game_ticks,
        active_adventure=active_adventure,
    )
