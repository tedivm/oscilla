import json
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import TYPE_CHECKING, Any, Dict, List, Literal
from uuid import UUID

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from oscilla.models.character import CharacterRecord
from oscilla.models.character_iteration import (
    CharacterIterationActiveBuff,
    CharacterIterationAdventureState,
    CharacterIterationEquipment,
    CharacterIterationEraState,
    CharacterIterationInventory,
    CharacterIterationItemInstance,
    CharacterIterationItemInstanceModifier,
    CharacterIterationMilestone,
    CharacterIterationPendingTrigger,
    CharacterIterationQuest,
    CharacterIterationRecord,
    CharacterIterationSkill,
    CharacterIterationSkillCooldown,
    CharacterIterationStatistic,
    CharacterIterationStatValue,
)
from oscilla.models.character_session_output import CharacterSessionOutputRecord

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.models.character_config import CharacterConfigManifest
    from oscilla.engine.registry import ContentRegistry

from oscilla.engine.templates import PRONOUN_SETS

logger = getLogger(__name__)


def _stat_to_int(value: "int | bool | None") -> int | None:
    """Encode a CharacterState stat value for storage in the BigInteger DB column.

    Booleans are stored as 0/1. Integer values are stored as-is.
    NULL is preserved as NULL for unset stats.
    """
    if value is None:
        return None
    # bool must be checked before int because bool is a subclass of int
    if isinstance(value, bool):
        return int(value)
    return value


# ---------------------------------------------------------------------------
# Initial character creation and loading
# ---------------------------------------------------------------------------


async def save_character(session: AsyncSession, state: "CharacterState", user_id: UUID, game_name: str) -> None:
    """INSERT a brand-new character — initial creation only.

    Creates one CharacterRecord, one CharacterIterationRecord at iteration = 0,
    and seeds all child rows (stat_values, inventory, equipment, milestones,
    quests, statistics) from the state's current values.

    Call this exactly once per character.  All subsequent state changes go
    through the targeted update functions below.

    Raises IntegrityError if state.character_id already exists in the DB.
    """
    character = CharacterRecord(
        id=state.character_id,
        user_id=user_id,
        game_name=game_name,
        name=state.name,
    )
    session.add(character)

    iteration = CharacterIterationRecord(
        character_id=state.character_id,
        iteration=state.prestige_count,
        is_active=True,
        character_class=state.character_class,
        current_location=state.current_location,
        pronoun_set=next((k for k, v in PRONOUN_SETS.items() if v == state.pronouns), "they_them"),
        adventure_ref=state.active_adventure.adventure_ref if state.active_adventure else None,
        adventure_step_index=state.active_adventure.step_index if state.active_adventure else None,
        adventure_step_state=state.active_adventure.step_state if state.active_adventure else None,
    )
    session.add(iteration)
    await session.flush()  # populate iteration.id before adding children

    # Seed child rows from state
    for stat_name, stat_value in state.stats.items():
        session.add(
            CharacterIterationStatValue(
                iteration_id=iteration.id,
                stat_name=stat_name,
                stat_value=_stat_to_int(stat_value),
            )
        )
    for item_ref, quantity in state.stacks.items():
        session.add(
            CharacterIterationInventory(
                iteration_id=iteration.id,
                item_ref=item_ref,
                quantity=quantity,
            )
        )
    # Build a set of instance_ids that appear in equipment to track which
    # instances to persist (all instances are persisted regardless).
    for inst in state.instances:
        instance_row = CharacterIterationItemInstance(
            iteration_id=iteration.id,
            instance_id=str(inst.instance_id),
            item_ref=inst.item_ref,
        )
        session.add(instance_row)
        for stat, amount in inst.modifiers.items():
            session.add(
                CharacterIterationItemInstanceModifier(
                    iteration_id=str(iteration.id),
                    instance_id=str(inst.instance_id),
                    stat=stat,
                    amount=amount,
                )
            )
    for slot, instance_id in state.equipment.items():
        session.add(
            CharacterIterationEquipment(
                iteration_id=iteration.id,
                slot=slot,
                instance_id=str(instance_id),
            )
        )
    for milestone_ref, milestone_record in state.milestones.items():
        session.add(
            CharacterIterationMilestone(
                iteration_id=iteration.id,
                milestone_ref=milestone_ref,
                grant_tick=milestone_record.tick,
                grant_timestamp=milestone_record.timestamp,
            )
        )
    for quest_ref, stage in state.active_quests.items():
        session.add(
            CharacterIterationQuest(
                iteration_id=iteration.id,
                quest_ref=quest_ref,
                status="active",
                stage=stage,
            )
        )
    for quest_ref in state.completed_quests:
        session.add(
            CharacterIterationQuest(
                iteration_id=iteration.id,
                quest_ref=quest_ref,
                status="completed",
                stage=None,
            )
        )
    for quest_ref in state.failed_quests:
        session.add(
            CharacterIterationQuest(
                iteration_id=iteration.id,
                quest_ref=quest_ref,
                status="failed",
                stage=None,
            )
        )
    for entity_ref, count in state.statistics.enemies_defeated.items():
        session.add(
            CharacterIterationStatistic(
                iteration_id=iteration.id,
                stat_type="enemies_defeated",
                entity_ref=entity_ref,
                count=count,
            )
        )
    for entity_ref, count in state.statistics.locations_visited.items():
        session.add(
            CharacterIterationStatistic(
                iteration_id=iteration.id,
                stat_type="locations_visited",
                entity_ref=entity_ref,
                count=count,
            )
        )
    for entity_ref, count in state.statistics.adventures_completed.items():
        session.add(
            CharacterIterationStatistic(
                iteration_id=iteration.id,
                stat_type="adventures_completed",
                entity_ref=entity_ref,
                count=count,
            )
        )
    for skill_ref in state.known_skills:
        session.add(CharacterIterationSkill(iteration_id=iteration.id, skill_ref=skill_ref))
    all_cooldown_refs = set(state.skill_tick_expiry) | set(state.skill_real_expiry)
    for skill_ref in all_cooldown_refs:
        tick_exp = state.skill_tick_expiry.get(skill_ref, 0)
        real_exp = state.skill_real_expiry.get(skill_ref, 0)
        if tick_exp > 0 or real_exp > 0:
            session.add(
                CharacterIterationSkillCooldown(
                    iteration_id=iteration.id,
                    skill_ref=skill_ref,
                    tick_expiry=tick_exp,
                    real_expiry=real_exp,
                )
            )
    import json

    for sb in state.active_buffs:
        session.add(
            CharacterIterationActiveBuff(
                iteration_id=iteration.id,
                buff_ref=sb.buff_ref,
                remaining_turns=sb.remaining_turns,
                variables_json=json.dumps(sb.variables),
                tick_expiry=sb.tick_expiry,
                game_tick_expiry=sb.game_tick_expiry,
                real_ts_expiry=sb.real_ts_expiry,
            )
        )
    for position, trigger_name in enumerate(state.pending_triggers):
        session.add(
            CharacterIterationPendingTrigger(
                iteration_id=iteration.id,
                position=position,
                trigger_name=trigger_name,
            )
        )

    await session.commit()


async def load_character(
    session: AsyncSession,
    character_id: UUID,
    character_config: "CharacterConfigManifest",
    registry: "ContentRegistry | None" = None,
) -> "CharacterState | None":
    """Load the active iteration and reconstruct a CharacterState.

    Selects CharacterIterationRecord WHERE is_active = TRUE, then eagerly
    loads all six child table relationships using selectinload to avoid N+1
    queries.  Delegates content-drift resolution to CharacterState.from_dict().

    Returns None if no CharacterRecord exists with the given id.
    """
    from oscilla.engine.character import CharacterState

    # Verify the character exists
    char_stmt = select(CharacterRecord).where(and_(CharacterRecord.id == character_id))
    char_result = await session.execute(char_stmt)
    character = char_result.scalar_one_or_none()
    if character is None:
        return None

    # Load the active iteration with all child relationships
    iter_stmt = (
        select(CharacterIterationRecord)
        .where(
            and_(
                CharacterIterationRecord.character_id == character_id,
                CharacterIterationRecord.is_active == True,  # noqa: E712
            )
        )
        .options(
            selectinload(CharacterIterationRecord.stat_values),
            selectinload(CharacterIterationRecord.inventory_rows),
            selectinload(CharacterIterationRecord.equipment_rows),
            selectinload(CharacterIterationRecord.item_instance_rows).selectinload(
                CharacterIterationItemInstance.modifier_rows
            ),
            selectinload(CharacterIterationRecord.milestone_rows),
            selectinload(CharacterIterationRecord.quest_rows),
            selectinload(CharacterIterationRecord.statistic_rows),
            selectinload(CharacterIterationRecord.skill_rows),
            selectinload(CharacterIterationRecord.skill_cooldown_rows),
            selectinload(CharacterIterationRecord.adventure_state_rows),
            selectinload(CharacterIterationRecord.era_state_rows),
            selectinload(CharacterIterationRecord.pending_trigger_rows),
            selectinload(CharacterIterationRecord.active_buff_rows),
        )
    )
    iter_result = await session.execute(iter_stmt)
    iteration = iter_result.scalar_one_or_none()
    if iteration is None:
        logger.warning("No active iteration found for character_id=%s", character_id)
        return None

    # Build a dict matching to_dict() output from ORM rows
    active_adventure = None
    if iteration.adventure_ref is not None and iteration.adventure_step_index is not None:
        active_adventure = {
            "adventure_ref": iteration.adventure_ref,
            "step_index": iteration.adventure_step_index,
            "step_state": iteration.adventure_step_state or {},
        }

    stats: Dict[str, Any] = {row.stat_name: row.stat_value for row in iteration.stat_values}
    stacks: Dict[str, int] = {row.item_ref: row.quantity for row in iteration.inventory_rows}
    instances: List[Dict[str, Any]] = [
        {
            "instance_id": row.instance_id,
            "item_ref": row.item_ref,
            "modifiers": {mod.stat: mod.amount for mod in row.modifier_rows},
        }
        for row in iteration.item_instance_rows
    ]
    equipment: Dict[str, str] = {row.slot: row.instance_id for row in iteration.equipment_rows}
    milestones: Dict[str, Any] = {
        row.milestone_ref: {"tick": row.grant_tick, "timestamp": row.grant_timestamp}
        for row in iteration.milestone_rows
    }
    active_quests: Dict[str, str] = {
        row.quest_ref: row.stage or "" for row in iteration.quest_rows if row.status == "active"
    }
    completed_quests: List[str] = [row.quest_ref for row in iteration.quest_rows if row.status == "completed"]
    failed_quests: List[str] = [row.quest_ref for row in iteration.quest_rows if row.status == "failed"]

    enemies_defeated: Dict[str, int] = {}
    locations_visited: Dict[str, int] = {}
    adventures_completed: Dict[str, int] = {}
    adventure_outcome_counts: Dict[str, Dict[str, int]] = {}
    for stat_row in iteration.statistic_rows:
        if stat_row.stat_type == "enemies_defeated":
            enemies_defeated[stat_row.entity_ref] = stat_row.count
        elif stat_row.stat_type == "locations_visited":
            locations_visited[stat_row.entity_ref] = stat_row.count
        elif stat_row.stat_type == "adventures_completed":
            adventures_completed[stat_row.entity_ref] = stat_row.count
        elif stat_row.stat_type.startswith("adventure_outcome:"):
            outcome_name = stat_row.stat_type[len("adventure_outcome:") :]
            adventure_ref = stat_row.entity_ref
            if adventure_ref not in adventure_outcome_counts:
                adventure_outcome_counts[adventure_ref] = {}
            adventure_outcome_counts[adventure_ref][outcome_name] = stat_row.count

    known_skills: List[str] = [row.skill_ref for row in iteration.skill_rows]
    skill_tick_expiry: Dict[str, int] = {
        row.skill_ref: row.tick_expiry for row in iteration.skill_cooldown_rows if row.tick_expiry > 0
    }
    skill_real_expiry: Dict[str, int] = {
        row.skill_ref: row.real_expiry for row in iteration.skill_cooldown_rows if row.real_expiry > 0
    }
    adventure_last_completed_real_ts: Dict[str, int] = {
        row.adventure_ref: row.last_completed_real_ts
        for row in iteration.adventure_state_rows
        if row.last_completed_real_ts is not None
    }
    adventure_last_completed_game_ticks: Dict[str, int] = {
        row.adventure_ref: row.last_completed_game_ticks
        for row in iteration.adventure_state_rows
        if row.last_completed_game_ticks is not None
    }
    adventure_last_completed_at_ticks: Dict[str, int] = {
        row.adventure_ref: row.last_completed_at_ticks
        for row in iteration.adventure_state_rows
        if row.last_completed_at_ticks is not None
    }
    era_started_at_ticks: Dict[str, int] = {
        row.era_name: row.started_at_game_ticks
        for row in iteration.era_state_rows
        if row.started_at_game_ticks is not None
    }
    era_ended_at_ticks: Dict[str, int] = {
        row.era_name: row.ended_at_game_ticks for row in iteration.era_state_rows if row.ended_at_game_ticks is not None
    }

    data: Dict[str, Any] = {
        "character_id": str(character_id),
        "prestige_count": iteration.iteration,
        "name": character.name,
        "character_class": iteration.character_class,
        "current_location": iteration.current_location,
        "pronoun_set": iteration.pronoun_set,
        "milestones": milestones,
        "stacks": stacks,
        "instances": instances,
        "equipment": equipment,
        "active_quests": active_quests,
        "completed_quests": completed_quests,
        "failed_quests": failed_quests,
        "stats": stats,
        "statistics": {
            "enemies_defeated": enemies_defeated,
            "locations_visited": locations_visited,
            "adventures_completed": adventures_completed,
            "adventure_outcome_counts": adventure_outcome_counts,
        },
        "active_adventure": active_adventure,
        "known_skills": known_skills,
        "skill_tick_expiry": skill_tick_expiry,
        "skill_real_expiry": skill_real_expiry,
        "adventure_last_completed_real_ts": adventure_last_completed_real_ts,
        "adventure_last_completed_game_ticks": adventure_last_completed_game_ticks,
        "adventure_last_completed_at_ticks": adventure_last_completed_at_ticks,
        "internal_ticks": iteration.internal_ticks,
        "game_ticks": iteration.game_ticks,
        "era_started_at_ticks": era_started_at_ticks,
        "era_ended_at_ticks": era_ended_at_ticks,
        # Rows are already ordered ascending by position via the relationship order_by.
        "pending_triggers": [row.trigger_name for row in iteration.pending_trigger_rows],
        "active_buffs": [
            {
                "buff_ref": row.buff_ref,
                "remaining_turns": row.remaining_turns,
                "variables": json.loads(row.variables_json),
                "tick_expiry": row.tick_expiry,
                "game_tick_expiry": row.game_tick_expiry,
                "real_ts_expiry": row.real_ts_expiry,
            }
            for row in iteration.active_buff_rows
        ],
    }

    return CharacterState.from_dict(data=data, character_config=character_config, registry=registry)


async def list_characters_for_user(
    session: AsyncSession,
    user_id: UUID,
    game_name: str,
) -> List[CharacterRecord]:
    """Return all CharacterRecords belonging to user_id for game_name, ordered by updated_at DESC."""
    stmt = (
        select(CharacterRecord)
        .where(and_(CharacterRecord.user_id == user_id, CharacterRecord.game_name == game_name))
        .order_by(CharacterRecord.updated_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_user_characters(session: AsyncSession, user_id: UUID, game_name: str) -> int:
    """Delete all characters and every iteration row (plus child rows) for a user in a game.

    Loads each iteration with its six child table relationships so that
    SQLAlchemy's ORM cascade ("all, delete-orphan") removes the child rows
    before deleting the iteration itself.  Then deletes the character row.

    Returns the number of character records deleted.
    """
    char_stmt = select(CharacterRecord).where(
        and_(CharacterRecord.user_id == user_id, CharacterRecord.game_name == game_name)
    )
    char_result = await session.execute(char_stmt)
    characters = list(char_result.scalars().all())

    for character in characters:
        iter_stmt = (
            select(CharacterIterationRecord)
            .where(and_(CharacterIterationRecord.character_id == character.id))
            .options(
                selectinload(CharacterIterationRecord.stat_values),
                selectinload(CharacterIterationRecord.inventory_rows),
                selectinload(CharacterIterationRecord.equipment_rows),
                selectinload(CharacterIterationRecord.item_instance_rows).selectinload(
                    CharacterIterationItemInstance.modifier_rows
                ),
                selectinload(CharacterIterationRecord.milestone_rows),
                selectinload(CharacterIterationRecord.quest_rows),
                selectinload(CharacterIterationRecord.statistic_rows),
                selectinload(CharacterIterationRecord.skill_rows),
                selectinload(CharacterIterationRecord.skill_cooldown_rows),
            )
        )
        iter_result = await session.execute(iter_stmt)
        for iteration in iter_result.scalars().all():
            await session.delete(iteration)
        await session.delete(character)

    await session.commit()
    return len(characters)


async def get_character_by_name(
    session: AsyncSession,
    user_id: UUID,
    game_name: str,
    name: str,
) -> "CharacterRecord | None":
    """Return the CharacterRecord with the given name for user_id and game_name, or None."""
    stmt = select(CharacterRecord).where(
        and_(
            CharacterRecord.user_id == user_id,
            CharacterRecord.game_name == game_name,
            CharacterRecord.name == name,
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_character_record(
    session: AsyncSession,
    character_id: UUID,
) -> "CharacterRecord | None":
    """Return the CharacterRecord for the given character_id, or None."""
    stmt = select(CharacterRecord).where(and_(CharacterRecord.id == character_id))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def prestige_character(
    session: AsyncSession,
    character_id: UUID,
    character_config: "CharacterConfigManifest",
) -> CharacterIterationRecord:
    """Close the active iteration and open a new one.

    Steps:
    1. SELECT the iteration WHERE character_id = X AND is_active = TRUE.
    2. SET is_active = FALSE, completed_at = now() on that row.
    3. COUNT existing character_iterations for character_id to derive the new ordinal.
    4. INSERT a new CharacterIterationRecord with iteration = count,
       is_active = TRUE, completed_at = NULL, and all child rows seeded from character_config defaults.

    Returns the newly inserted CharacterIterationRecord.
    """
    # 1. Find the active iteration
    active_stmt = select(CharacterIterationRecord).where(
        and_(
            CharacterIterationRecord.character_id == character_id,
            CharacterIterationRecord.is_active == True,  # noqa: E712
        )
    )
    active_result = await session.execute(active_stmt)
    active_iteration = active_result.scalar_one()

    # 2. Close it
    active_iteration.is_active = False
    active_iteration.completed_at = datetime.now(tz=timezone.utc)

    # 3. Derive the new ordinal
    count_stmt = select(func.count()).where(and_(CharacterIterationRecord.character_id == character_id))
    count_result = await session.execute(count_stmt)
    new_ordinal = count_result.scalar_one()

    # 4. Create the new iteration with fresh defaults from character_config
    all_stats = character_config.spec.public_stats + character_config.spec.hidden_stats

    new_iteration = CharacterIterationRecord(
        character_id=character_id,
        iteration=new_ordinal,
        is_active=True,
    )
    session.add(new_iteration)
    await session.flush()

    for stat_def in all_stats:
        session.add(
            CharacterIterationStatValue(
                iteration_id=new_iteration.id,
                stat_name=stat_def.name,
                stat_value=_stat_to_int(stat_def.default),
            )
        )

    # Update the character's updated_at timestamp
    await touch_character_updated_at(session=session, character_id=character_id)
    return new_iteration


async def rename_character(session: AsyncSession, character_id: UUID, new_name: str) -> None:
    """Rename a character in the DB.

    Raises ValueError if new_name is already taken for the same (user_id, game_name) pair,
    which would violate the unique constraint.
    """
    char_stmt = select(CharacterRecord).where(and_(CharacterRecord.id == character_id))
    char_result = await session.execute(char_stmt)
    record = char_result.scalar_one()

    dup_stmt = select(CharacterRecord).where(
        and_(
            CharacterRecord.user_id == record.user_id,
            CharacterRecord.game_name == record.game_name,
            CharacterRecord.name == new_name,
            CharacterRecord.id != character_id,
        )
    )
    dup_result = await session.execute(dup_stmt)
    if dup_result.scalar_one_or_none() is not None:
        raise ValueError(f"Character name {new_name!r} is already taken in game {record.game_name!r}.")

    record.name = new_name
    await touch_character_updated_at(session=session, character_id=character_id)
    await session.commit()


async def load_all_iterations(
    session: AsyncSession,
    character_id: UUID,
) -> List[CharacterIterationRecord]:
    """Return all iteration rows for character_id ordered by iteration ASC.

    Includes both completed runs (non-null completed_at) and the active run.
    """
    stmt = (
        select(CharacterIterationRecord)
        .where(and_(CharacterIterationRecord.character_id == character_id))
        .order_by(CharacterIterationRecord.iteration.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_active_iteration_id(
    session: AsyncSession,
    character_id: UUID,
) -> UUID | None:
    """Return the UUID of the active character_iterations row, or None.

    Used by GameSession to obtain iteration_id after load_character()
    without repeating the full iteration query.
    """
    stmt = select(CharacterIterationRecord.id).where(
        and_(
            CharacterIterationRecord.character_id == character_id,
            CharacterIterationRecord.is_active == True,  # noqa: E712
        )
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return row if row is None else UUID(str(row))


async def get_active_iteration_record(
    session: AsyncSession,
    character_id: UUID,
) -> "CharacterIterationRecord | None":
    """Return the active CharacterIterationRecord for a character, or None.

    Used by web route handlers that need the full record (e.g. adventure_ref,
    adventure_step_index, session_token) in a single query.
    """
    stmt = select(CharacterIterationRecord).where(
        and_(
            CharacterIterationRecord.character_id == character_id,
            CharacterIterationRecord.is_active == True,  # noqa: E712
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def acquire_session_lock(
    session: AsyncSession,
    iteration_id: UUID,
    token: str,
) -> None:
    """Acquire the session soft-lock on the active iteration row.

    Always succeeds — a new session is never blocked.

    Decision tree:
      - session_token is NULL     → lock is free; take it.
      - session_token is non-NULL → previous process died without releasing.
          Log WARNING naming the old token, clear adventure state, take the lock.
    """
    stmt = select(CharacterIterationRecord).where(and_(CharacterIterationRecord.id == iteration_id))
    result = await session.execute(stmt)
    iteration = result.scalar_one()

    if iteration.session_token is not None:
        logger.warning(
            "Stealing session lock from prior token %r on iteration %s — "
            "previous process likely died without releasing the lock.",
            iteration.session_token,
            iteration_id,
        )
        # Clear orphaned adventure state — prevents double-applying outcome effects
        # that may have been partially written before the process died.
        iteration.adventure_ref = None
        iteration.adventure_step_index = None
        iteration.adventure_step_state = None

    iteration.session_token = token
    await session.commit()


async def release_session_lock(
    session: AsyncSession,
    iteration_id: UUID,
    token: str,
) -> None:
    """Clear session_token on the iteration row.

    Only clears the lock if session_token still matches token, so a release
    from a zombie process after a new session has taken over is harmless.
    """
    # Use a raw UPDATE so this operation does not touch version_id_col.
    stmt = (
        update(CharacterIterationRecord)
        .where(
            and_(
                CharacterIterationRecord.id == iteration_id,
                CharacterIterationRecord.session_token == token,
            )
        )
        .values(session_token=None)
        .execution_options(synchronize_session="fetch")
    )
    await session.execute(stmt)
    await session.commit()


async def acquire_web_session_lock(
    session: AsyncSession,
    iteration_id: UUID,
    token: str,
    stale_threshold_minutes: int,
) -> datetime | None:
    """Attempt to acquire a web session lock on an iteration.

    Returns ``None`` on success (lock acquired or stale lock taken over).
    Returns the ``acquired_at`` datetime if a live session already holds the lock
    (caller should respond with 409 Conflict).

    A lock is considered stale when ``session_token_acquired_at`` is more than
    ``stale_threshold_minutes`` in the past. Stale locks are automatically
    replaced without returning a conflict.
    """
    stmt = select(CharacterIterationRecord).where(and_(CharacterIterationRecord.id == iteration_id))
    result = await session.execute(stmt)
    iteration = result.scalar_one()

    if iteration.session_token is not None:
        acquired_at = iteration.session_token_acquired_at
        now = datetime.now(tz=timezone.utc)
        if acquired_at is None or (
            now - acquired_at.replace(tzinfo=timezone.utc) if acquired_at.tzinfo is None else now - acquired_at
        ) < timedelta(minutes=stale_threshold_minutes):
            # Lock is actively held — return acquired_at so the caller can return 409.
            return acquired_at if acquired_at is not None else now

    iteration.session_token = token
    iteration.session_token_acquired_at = datetime.now(tz=timezone.utc)
    await session.commit()
    return None


async def release_web_session_lock(
    session: AsyncSession,
    iteration_id: UUID,
    token: str,
) -> None:
    """Clear the web session lock if the token matches.

    No-op if the token does not match — prevents a zombie process from
    releasing a lock that another session has already taken over.
    """
    stmt = (
        update(CharacterIterationRecord)
        .where(
            and_(
                CharacterIterationRecord.id == iteration_id,
                CharacterIterationRecord.session_token == token,
            )
        )
        .values(session_token=None, session_token_acquired_at=None)
        .execution_options(synchronize_session="fetch")
    )
    await session.execute(stmt)
    await session.commit()


async def force_acquire_web_session_lock(
    session: AsyncSession,
    iteration_id: UUID,
    token: str,
) -> None:
    """Unconditionally acquire the web session lock (takeover endpoint).

    Logs a WARNING if a prior token is displaced. Clears orphaned adventure
    state to prevent double-applying outcome effects from the displaced session.
    """
    stmt = select(CharacterIterationRecord).where(and_(CharacterIterationRecord.id == iteration_id))
    result = await session.execute(stmt)
    iteration = result.scalar_one()

    if iteration.session_token is not None:
        logger.warning(
            "Force-acquiring web session lock from prior token %r on iteration %s.",
            iteration.session_token,
            iteration_id,
        )

    # Clear orphaned adventure state from the displaced session.
    iteration.adventure_ref = None
    iteration.adventure_step_index = None
    iteration.adventure_step_state = None
    iteration.session_token = token
    iteration.session_token_acquired_at = datetime.now(tz=timezone.utc)
    await session.commit()


async def save_session_output(
    session: AsyncSession,
    iteration_id: UUID,
    events: List[Dict[str, Any]],
) -> None:
    """Replace all session output rows for an iteration with the given events.

    Performs a full DELETE + INSERT to keep the stored log exactly in sync with
    the events emitted during the most recent adventure session.
    """
    del_stmt = delete(CharacterSessionOutputRecord).where(
        and_(CharacterSessionOutputRecord.iteration_id == iteration_id)
    )
    await session.execute(del_stmt)
    for position, event in enumerate(events):
        row = CharacterSessionOutputRecord(
            iteration_id=iteration_id,
            position=position,
            event_type=event["type"],
            content_json=event,
        )
        session.add(row)
    await session.commit()


async def get_session_output(
    session: AsyncSession,
    iteration_id: UUID,
) -> List[Dict[str, Any]]:
    """Return all session output events for an iteration, ordered by position."""
    stmt = (
        select(CharacterSessionOutputRecord)
        .where(and_(CharacterSessionOutputRecord.iteration_id == iteration_id))
        .order_by(CharacterSessionOutputRecord.position)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [row.content_json for row in rows]


async def clear_session_output(
    session: AsyncSession,
    iteration_id: UUID,
) -> None:
    """Delete all session output rows for an iteration."""
    stmt = delete(CharacterSessionOutputRecord).where(and_(CharacterSessionOutputRecord.iteration_id == iteration_id))
    await session.execute(stmt)
    await session.commit()


# ---------------------------------------------------------------------------
# Targeted update functions
# ---------------------------------------------------------------------------


async def update_scalar_fields(
    session: AsyncSession,
    iteration_id: UUID,
    fields: Dict[str, Any],
) -> None:
    """Update named scalar columns on the character_iterations row.

    Only keys present in fields are written; omitted columns are unchanged.
    Adventure fields go through save_adventure_progress() instead.

    Updating the ORM object triggers the version_id_col increment automatically,
    so StaleDataError detection continues to work correctly.
    """
    stmt = select(CharacterIterationRecord).where(and_(CharacterIterationRecord.id == iteration_id))
    result = await session.execute(stmt)
    iteration = result.scalar_one()
    for key, value in fields.items():
        setattr(iteration, key, value)
    await session.commit()


async def touch_character_updated_at(session: AsyncSession, character_id: UUID) -> None:
    """Refresh characters.updated_at without clearing other fields.

    Called at adventure_end and on prestige so list_characters_for_user()
    shows the most-recently-played character first.
    """
    stmt = (
        update(CharacterRecord)
        .where(and_(CharacterRecord.id == character_id))
        .values(updated_at=datetime.now(tz=timezone.utc))
        .execution_options(synchronize_session="fetch")
    )
    await session.execute(stmt)
    # Caller is responsible for commit


async def set_stat(
    session: AsyncSession,
    iteration_id: UUID,
    stat_name: str,
    value: int | bool | None,
) -> None:
    """Upsert one row in character_iteration_stat_values.

    value is stored as a BIGINT column; booleans are stored as 0/1;
    NULL is used for stats whose value is explicitly unset.
    """
    merged = await session.merge(
        CharacterIterationStatValue(
            iteration_id=iteration_id,
            stat_name=stat_name,
            stat_value=_stat_to_int(value),
        )
    )
    await session.commit()
    logger.debug("set_stat: %s=%s on iteration %s (merged=%s)", stat_name, value, iteration_id, merged)


async def set_inventory_item(
    session: AsyncSession,
    iteration_id: UUID,
    item_ref: str,
    quantity: int,
) -> None:
    """Upsert (quantity > 0) or delete (quantity == 0) one inventory row."""
    if quantity == 0:
        stmt = select(CharacterIterationInventory).where(
            and_(
                CharacterIterationInventory.iteration_id == iteration_id,
                CharacterIterationInventory.item_ref == item_ref,
            )
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            await session.delete(existing)
    else:
        await session.merge(
            CharacterIterationInventory(
                iteration_id=iteration_id,
                item_ref=item_ref,
                quantity=quantity,
            )
        )
    await session.commit()


async def equip_item(
    session: AsyncSession,
    iteration_id: UUID,
    slot: str,
    instance_id: str,
) -> None:
    """Upsert one character_iteration_equipment row (insert or replace slot)."""
    await session.merge(
        CharacterIterationEquipment(
            iteration_id=iteration_id,
            slot=slot,
            instance_id=instance_id,
        )
    )
    await session.commit()


async def unequip_item(
    session: AsyncSession,
    iteration_id: UUID,
    slot: str,
) -> None:
    """Delete the character_iteration_equipment row for slot, if it exists."""
    stmt = select(CharacterIterationEquipment).where(
        and_(
            CharacterIterationEquipment.iteration_id == iteration_id,
            CharacterIterationEquipment.slot == slot,
        )
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        await session.delete(existing)
        await session.commit()


async def add_item_instance(
    session: AsyncSession,
    iteration_id: UUID,
    instance_id: str,
    item_ref: str,
    modifiers: "Dict[str, int | float]",
) -> None:
    """Insert a CharacterIterationItemInstance row and its modifier rows."""
    session.add(
        CharacterIterationItemInstance(
            iteration_id=iteration_id,
            instance_id=instance_id,
            item_ref=item_ref,
        )
    )
    for stat, amount in modifiers.items():
        session.add(
            CharacterIterationItemInstanceModifier(
                iteration_id=str(iteration_id),
                instance_id=instance_id,
                stat=stat,
                amount=amount,
            )
        )
    await session.commit()


async def remove_item_instance(
    session: AsyncSession,
    iteration_id: UUID,
    instance_id: str,
) -> None:
    """Delete a CharacterIterationItemInstance row (modifiers cascade)."""
    stmt = select(CharacterIterationItemInstance).where(
        and_(
            CharacterIterationItemInstance.iteration_id == iteration_id,
            CharacterIterationItemInstance.instance_id == instance_id,
        )
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        await session.delete(existing)
        await session.commit()


async def add_milestone(
    session: AsyncSession,
    iteration_id: UUID,
    milestone_ref: str,
    grant_tick: int = 0,
    grant_timestamp: int = 0,
) -> None:
    """Insert one character_iteration_milestones row.

    Idempotent — uses merge() so calling this twice for the same milestone_ref
    is safe.
    """
    await session.merge(
        CharacterIterationMilestone(
            iteration_id=iteration_id,
            milestone_ref=milestone_ref,
            grant_tick=grant_tick,
            grant_timestamp=grant_timestamp,
        )
    )
    await session.commit()


async def set_quest(
    session: AsyncSession,
    iteration_id: UUID,
    quest_ref: str,
    status: Literal["active", "completed", "failed"],
    stage: "str | None" = None,
) -> None:
    """Upsert one character_iteration_quests row.

    status must be "active", "completed", or "failed".  stage should be None
    for completed and failed quests.
    """
    await session.merge(
        CharacterIterationQuest(
            iteration_id=iteration_id,
            quest_ref=quest_ref,
            status=status,
            stage=stage,
        )
    )
    await session.commit()


async def increment_statistic(
    session: AsyncSession,
    iteration_id: UUID,
    stat_type: str,
    entity_ref: str,
    delta: int = 1,
) -> None:
    """Upsert-increment one character_iteration_statistics row.

    If the row doesn't exist it is created with count = delta.
    If it exists, count is incremented by delta.
    """
    stmt = select(CharacterIterationStatistic).where(
        and_(
            CharacterIterationStatistic.iteration_id == iteration_id,
            CharacterIterationStatistic.stat_type == stat_type,
            CharacterIterationStatistic.entity_ref == entity_ref,
        )
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is None:
        session.add(
            CharacterIterationStatistic(
                iteration_id=iteration_id,
                stat_type=stat_type,
                entity_ref=entity_ref,
                count=delta,
            )
        )
    else:
        existing.count += delta
    await session.commit()


async def save_adventure_progress(
    session: AsyncSession,
    iteration_id: UUID,
    adventure_ref: "str | None",
    step_index: "int | None",
    step_state: "Dict[str, Any] | None",
) -> None:
    """Update the three adventure columns on character_iterations.

    This is the ONLY service function that writes adventure_step_state (JSON).
    Pass all three as None to clear the active adventure at adventure_end.

    Called by GameSession._on_state_change() on:
      "step_start"    — adventure_ref and step_index advance; step_state is {}.
      "combat_round"  — step_state is updated with round scratch values.
      "adventure_end" — all three set to NULL.
    """
    # Use a raw UPDATE to avoid triggering version_id_col increment on every
    # combat round — adventure progress writes are high-frequency and should not
    # count as character state mutations for optimistic locking purposes.
    # Only update_scalar_fields() touches player-visible stats and triggers versioning.
    stmt = (
        update(CharacterIterationRecord)
        .where(and_(CharacterIterationRecord.id == iteration_id))
        .values(
            adventure_ref=adventure_ref,
            adventure_step_index=step_index,
            adventure_step_state=step_state,
        )
        .execution_options(synchronize_session="fetch")
    )
    await session.execute(stmt)
    await session.commit()


async def add_known_skill(
    session: AsyncSession,
    iteration_id: UUID,
    skill_ref: str,
) -> None:
    """Idempotent insert of a known skill row.

    Uses merge() so calling this twice for the same skill_ref is safe.
    """
    await session.merge(
        CharacterIterationSkill(
            iteration_id=iteration_id,
            skill_ref=skill_ref,
        )
    )
    await session.commit()


async def set_skill_cooldown(
    session: AsyncSession,
    iteration_id: UUID,
    skill_ref: str,
    tick_expiry: int,
    real_expiry: int,
) -> None:
    """Upsert or delete one skill cooldown row.

    Deletes the row when both expiry values are zero (cooldown fully cleared).
    """
    if tick_expiry <= 0 and real_expiry <= 0:
        stmt = select(CharacterIterationSkillCooldown).where(
            and_(
                CharacterIterationSkillCooldown.iteration_id == iteration_id,
                CharacterIterationSkillCooldown.skill_ref == skill_ref,
            )
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            await session.delete(existing)
    else:
        await session.merge(
            CharacterIterationSkillCooldown(
                iteration_id=iteration_id,
                skill_ref=skill_ref,
                tick_expiry=tick_expiry,
                real_expiry=real_expiry,
            )
        )
    await session.commit()


async def upsert_adventure_state(
    session: AsyncSession,
    iteration_id: UUID,
    adventure_ref: str,
    last_completed_real_ts: int | None,
    last_completed_game_ticks: int | None,
    last_completed_at_ticks: int | None,
) -> None:
    """Upsert the repeat-control state for one adventure.

    Creates the row if it does not exist; updates it if it does.
    """
    await session.merge(
        CharacterIterationAdventureState(
            iteration_id=iteration_id,
            adventure_ref=adventure_ref,
            last_completed_real_ts=last_completed_real_ts,
            last_completed_game_ticks=last_completed_game_ticks,
            last_completed_at_ticks=last_completed_at_ticks,
        )
    )
    await session.commit()


async def update_character_tick_state(
    session: AsyncSession,
    iteration_id: UUID,
    internal_ticks: int,
    game_ticks: int,
    adventure_last_completed_at_ticks: Dict[str, int],
    era_started_at_ticks: Dict[str, int],
    era_ended_at_ticks: Dict[str, int],
) -> None:
    """Persist tick counters, adventure cooldown ticks, and era latch state.

    Called after every adventure completion. Upserts adventure_state and
    era_state rows to avoid racing with concurrent writes.
    """
    # Update tick counters on the iteration record.
    stmt = (
        update(CharacterIterationRecord)
        .where(and_(CharacterIterationRecord.id == iteration_id))
        .values(internal_ticks=internal_ticks, game_ticks=game_ticks)
        .execution_options(synchronize_session="fetch")
    )
    await session.execute(stmt)

    # Upsert adventure state rows for tick-based cooldowns.
    for adventure_ref, ticks_value in adventure_last_completed_at_ticks.items():
        await session.merge(
            CharacterIterationAdventureState(
                iteration_id=iteration_id,
                adventure_ref=adventure_ref,
                last_completed_at_ticks=ticks_value,
            )
        )

    # Upsert era state rows.
    all_era_names = set(era_started_at_ticks) | set(era_ended_at_ticks)
    for era_name in all_era_names:
        await session.merge(
            CharacterIterationEraState(
                iteration_id=iteration_id,
                era_name=era_name,
                started_at_game_ticks=era_started_at_ticks.get(era_name),
                ended_at_game_ticks=era_ended_at_ticks.get(era_name),
            )
        )

    await session.commit()


# ---------------------------------------------------------------------------
# API helper service functions
# ---------------------------------------------------------------------------


async def list_all_characters_for_user(
    session: AsyncSession,
    user_id: UUID,
    game_name: str | None = None,
) -> List[CharacterRecord]:
    """Return CharacterRecords belonging to user_id, optionally filtered by game_name.

    When game_name is None, all characters across all games are returned.
    Records are ordered updated_at DESC.
    """
    conditions = [CharacterRecord.user_id == user_id]
    if game_name is not None:
        conditions.append(CharacterRecord.game_name == game_name)
    stmt = select(CharacterRecord).where(and_(*conditions)).order_by(CharacterRecord.updated_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_character_by_owner(
    session: AsyncSession,
    character_id: UUID,
    user_id: UUID,
) -> bool:
    """Delete a single character and all its iteration rows by owner.

    Returns True if deleted, False if the character does not exist or is not owned
    by user_id (either way the caller receives a 404-equivalent result).

    Mirrors the cascade strategy in delete_user_characters: loads each iteration
    with its child relation selectinloads so that ORM cascade ("all, delete-orphan")
    removes child rows before the iteration row is deleted.
    """
    char_stmt = select(CharacterRecord).where(
        and_(CharacterRecord.id == character_id, CharacterRecord.user_id == user_id)
    )
    char_result = await session.execute(char_stmt)
    character = char_result.scalar_one_or_none()
    if character is None:
        return False

    iter_stmt = (
        select(CharacterIterationRecord)
        .where(and_(CharacterIterationRecord.character_id == character.id))
        .options(
            selectinload(CharacterIterationRecord.stat_values),
            selectinload(CharacterIterationRecord.inventory_rows),
            selectinload(CharacterIterationRecord.equipment_rows),
            selectinload(CharacterIterationRecord.item_instance_rows).selectinload(
                CharacterIterationItemInstance.modifier_rows
            ),
            selectinload(CharacterIterationRecord.milestone_rows),
            selectinload(CharacterIterationRecord.quest_rows),
            selectinload(CharacterIterationRecord.statistic_rows),
            selectinload(CharacterIterationRecord.skill_rows),
            selectinload(CharacterIterationRecord.skill_cooldown_rows),
        )
    )
    iter_result = await session.execute(iter_stmt)
    for iteration in iter_result.scalars().all():
        await session.delete(iteration)
    await session.delete(character)
    await session.commit()
    return True


async def get_prestige_count(
    session: AsyncSession,
    character_id: UUID,
) -> int:
    """Return the prestige count (active iteration ordinal) for the given character.

    Returns 0 if no active iteration row is found (should not occur in practice).
    """
    stmt = select(CharacterIterationRecord.iteration).where(
        and_(
            CharacterIterationRecord.character_id == character_id,
            CharacterIterationRecord.is_active == True,  # noqa: E712
        )
    )
    result = await session.execute(stmt)
    value = result.scalar_one_or_none()
    return int(value) if value is not None else 0
