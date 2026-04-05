"""GameSession orchestrator — ties together user identity, character persistence,
and the AdventurePipeline for the TUI game loop.

FastAPI (web) uses the service layer directly with SQLAlchemy sessions managed
by FastAPI's DI; it does not use GameSession.
"""

from __future__ import annotations

import copy
from logging import getLogger
from typing import TYPE_CHECKING, Dict, List, Literal
from uuid import UUID, uuid4

from sqlalchemy.orm.exc import StaleDataError

from oscilla.engine.templates import PRONOUN_SETS
from oscilla.services.character import (
    acquire_session_lock,
    add_item_instance,
    add_known_skill,
    add_milestone,
    equip_item,
    get_active_iteration_id,
    get_character_by_name,
    increment_statistic,
    list_characters_for_user,
    load_character,
    release_session_lock,
    remove_item_instance,
    save_adventure_progress,
    save_character,
    set_inventory_item,
    set_quest,
    set_skill_cooldown,
    set_stat,
    touch_character_updated_at,
    unequip_item,
    update_character_tick_state,
    update_scalar_fields,
    upsert_adventure_state,
)
from oscilla.services.user import derive_tui_user_key, get_or_create_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from oscilla.engine.character import CharacterState
    from oscilla.engine.pipeline import AdventureOutcome, TUICallbacks
    from oscilla.engine.registry import ContentRegistry
    from oscilla.models.character import CharacterRecord

logger = getLogger(__name__)


def _warn_invalid_equipped(state: "CharacterState", registry: "ContentRegistry") -> None:
    """Log a warning for each equipped item whose `requires` condition is not satisfied.

    Does NOT unequip anything — only warns. Called after a character is restored
    from persistence so players are notified about stale equipment state.
    """
    from oscilla.engine.character import validate_equipped_requires

    failing = validate_equipped_requires(player=state, registry=registry)
    for item_ref in failing:
        item_mf = registry.items.get(item_ref)
        name = item_mf.spec.displayName if item_mf is not None else item_ref
        logger.warning(
            "Loaded character %r has equipped item %r whose requirements are not currently satisfied.",
            state.name,
            name,
        )


class GameSession:
    """Context-manager orchestrator for a single TUI game session.

    Usage::

        async with GameSession(registry=registry, tui=tui, db_session=session) as gs:
            await gs.start()
            await gs.run_adventure("my-adventure")

    ``start()`` resolves the user, selects or creates a character, and acquires
    the session soft-lock. ``close()`` (called automatically via ``__aexit__``)
    releases the lock even if an exception propagates.
    """

    def __init__(
        self,
        registry: "ContentRegistry",
        tui: "TUICallbacks",
        db_session: "AsyncSession",
        game_name: str,
        character_name: str | None = None,
    ) -> None:
        self.registry = registry
        self.tui = tui
        self.db_session = db_session
        self.game_name = game_name
        self.character_name = character_name
        self._character: "CharacterState | None" = None
        # Snapshot of the state as of the last successful DB write; used by
        # _on_state_change() to compute incremental diffs.
        self._last_saved_state: "CharacterState | None" = None
        # Unique string per process — used as the soft-lock identity.
        self._session_token: str = str(uuid4())
        self._iteration_id: UUID | None = None

    async def __aenter__(self) -> "GameSession":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Release the session soft-lock.

        Safe to call multiple times and even if start() was never called.
        """
        if self._iteration_id is not None:
            await release_session_lock(
                session=self.db_session,
                iteration_id=self._iteration_id,
                token=self._session_token,
            )

    async def start(self) -> None:
        """Resolve user identity, select or create a character, acquire session lock.

        After start() returns, _character and _last_saved_state are both set
        to the loaded or newly-created CharacterState. The session soft-lock
        is held until close() is called.
        """
        user_key = derive_tui_user_key()
        user = await get_or_create_user(session=self.db_session, user_key=user_key)

        if self.character_name is not None:
            # --character-name provided: auto-load a match or create-by-name.
            record = await get_character_by_name(
                session=self.db_session,
                user_id=user.id,
                game_name=self.game_name,
                name=self.character_name,
            )
            if record is not None:
                state = await load_character(
                    session=self.db_session,
                    character_id=record.id,
                    character_config=self.registry.character_config,  # type: ignore[arg-type]
                    registry=self.registry,
                )
                if state is None:
                    logger.warning(
                        "Character %r exists but has no active iteration; creating new.",
                        self.character_name,
                    )
                    state = await self._create_new_character(name=self.character_name, user_id=user.id)
                else:
                    _warn_invalid_equipped(state=state, registry=self.registry)
            else:
                state = await self._create_new_character(name=self.character_name, user_id=user.id)
        else:
            characters = await list_characters_for_user(
                session=self.db_session, user_id=user.id, game_name=self.game_name
            )
            if len(characters) == 0:
                state = await self._create_new_character(name=None, user_id=user.id)
            elif len(characters) == 1:
                state = await load_character(
                    session=self.db_session,
                    character_id=characters[0].id,
                    character_config=self.registry.character_config,  # type: ignore[arg-type]
                    registry=self.registry,
                )
                if state is None:
                    logger.warning(
                        "Character %r has no active iteration; creating new.",
                        characters[0].name,
                    )
                    state = await self._create_new_character(name=None, user_id=user.id)
                else:
                    _warn_invalid_equipped(state=state, registry=self.registry)
            else:
                state = await self._select_character(characters=characters, user_id=user.id)
                _warn_invalid_equipped(state=state, registry=self.registry)

        self._character = state
        self._last_saved_state = copy.deepcopy(state)

        iteration_id = await get_active_iteration_id(session=self.db_session, character_id=state.character_id)
        if iteration_id is None:
            raise RuntimeError(f"No active iteration found for character {state.character_id}")
        self._iteration_id = iteration_id
        await acquire_session_lock(
            session=self.db_session,
            iteration_id=iteration_id,
            token=self._session_token,
        )

    async def run_adventure(self, adventure_ref: str) -> "AdventureOutcome":
        """Build AdventurePipeline with _on_state_change and run to completion."""
        from datetime import date as _date

        from oscilla.engine.pipeline import AdventurePipeline

        if self._character is None:
            raise RuntimeError("start() must be called before run_adventure()")

        pipeline = AdventurePipeline(
            registry=self.registry,
            player=self._character,
            tui=self.tui,
            on_state_change=self._on_state_change,
        )
        outcome = await pipeline.run(adventure_ref=adventure_ref)

        # Record repeat-control tracking state after each adventure run.
        self._character.adventure_last_completed_on[adventure_ref] = _date.today().isoformat()
        # Record per-outcome count for this completion.
        self._character.statistics.record_adventure_outcome(adventure_ref=adventure_ref, outcome=outcome.value)

        return outcome

    # ---------------------------------------------------------------------------
    # PersistCallback implementation
    # ---------------------------------------------------------------------------

    async def _on_state_change(
        self,
        state: "CharacterState",
        event: Literal["step_start", "combat_round", "adventure_end"],
    ) -> None:
        """Diff current state against the last saved snapshot and write only changed domains.

        Retries once on StaleDataError after reloading the snapshot from the DB.
        """
        try:
            await self._persist_diff(state=state, event=event)
            self._last_saved_state = copy.deepcopy(state)
        except StaleDataError:
            logger.warning(
                "StaleDataError during persist (event=%r); reloading snapshot and retrying once.",
                event,
            )
            if self._iteration_id is not None and self.registry.character_config is not None:
                reloaded = await load_character(
                    session=self.db_session,
                    character_id=state.character_id,
                    character_config=self.registry.character_config,
                    registry=self.registry,
                )
                if reloaded is not None:
                    self._last_saved_state = reloaded
            try:
                await self._persist_diff(state=state, event=event)
                self._last_saved_state = copy.deepcopy(state)
            except StaleDataError:
                logger.exception(
                    "Second StaleDataError during persist (event=%r); giving up.",
                    event,
                )
                raise

    async def _persist_diff(
        self,
        state: "CharacterState",
        event: Literal["step_start", "combat_round", "adventure_end"],
    ) -> None:
        """Write only the domains that changed since _last_saved_state."""
        if self._iteration_id is None:
            logger.warning("_persist_diff called before iteration_id was set; skipping.")
            return

        iteration_id = self._iteration_id
        last = self._last_saved_state

        # --- Scalar fields (level, xp, hp, max_hp, character_class, current_location) ---
        scalar_fields: Dict[str, int | float | str | None] = {}
        if last is None or state.level != last.level:
            scalar_fields["level"] = state.level
        if last is None or state.xp != last.xp:
            scalar_fields["xp"] = state.xp
        if last is None or state.hp != last.hp:
            scalar_fields["hp"] = state.hp
        if last is None or state.max_hp != last.max_hp:
            scalar_fields["max_hp"] = state.max_hp
        if last is None or state.character_class != last.character_class:
            scalar_fields["character_class"] = state.character_class
        if last is None or state.current_location != last.current_location:
            scalar_fields["current_location"] = state.current_location
        # Normalize pronoun set to its key name for storage.
        state_pronoun_key = next((k for k, v in PRONOUN_SETS.items() if v == state.pronouns), "they_them")
        last_pronoun_key = (
            next((k for k, v in PRONOUN_SETS.items() if v == last.pronouns), "they_them") if last is not None else None
        )
        if last is None or state_pronoun_key != last_pronoun_key:
            scalar_fields["pronoun_set"] = state_pronoun_key
        if scalar_fields:
            await update_scalar_fields(
                session=self.db_session,
                iteration_id=iteration_id,
                fields=scalar_fields,
            )

        # --- Stats ---
        last_stats = last.stats if last is not None else {}
        for stat_name, value in state.stats.items():
            if value != last_stats.get(stat_name):
                await set_stat(
                    session=self.db_session,
                    iteration_id=iteration_id,
                    stat_name=stat_name,
                    value=value,
                )

        # --- Stacks (stackable inventory) ---
        last_stacks = last.stacks if last is not None else {}
        for item_ref, qty in state.stacks.items():
            if qty != last_stacks.get(item_ref):
                await set_inventory_item(
                    session=self.db_session,
                    iteration_id=iteration_id,
                    item_ref=item_ref,
                    quantity=qty,
                )
        # Items removed entirely from stacks
        for item_ref in last_stacks:
            if item_ref not in state.stacks:
                await set_inventory_item(
                    session=self.db_session,
                    iteration_id=iteration_id,
                    item_ref=item_ref,
                    quantity=0,
                )

        # --- Item instances (non-stackable) ---
        last_instance_ids: set[str] = {str(i.instance_id) for i in last.instances} if last is not None else set()
        current_instance_ids: set[str] = {str(i.instance_id) for i in state.instances}
        for inst in state.instances:
            inst_id_str = str(inst.instance_id)
            if inst_id_str not in last_instance_ids:
                await add_item_instance(
                    session=self.db_session,
                    iteration_id=iteration_id,
                    instance_id=inst_id_str,
                    item_ref=inst.item_ref,
                    modifiers=inst.modifiers,
                )
        for inst_id_str in last_instance_ids:
            if inst_id_str not in current_instance_ids:
                await remove_item_instance(
                    session=self.db_session,
                    iteration_id=iteration_id,
                    instance_id=inst_id_str,
                )

        # --- Equipment (slot → instance_id UUID) ---
        last_equip = last.equipment if last is not None else {}
        for slot, instance_id in state.equipment.items():
            if instance_id != last_equip.get(slot):
                await equip_item(
                    session=self.db_session,
                    iteration_id=iteration_id,
                    slot=slot,
                    instance_id=str(instance_id),
                )
        for slot in last_equip:
            if slot not in state.equipment:
                await unequip_item(
                    session=self.db_session,
                    iteration_id=iteration_id,
                    slot=slot,
                )

        # --- Milestones (additive only — never removed within an iteration) ---
        last_milestones = last.milestones if last is not None else set()
        for milestone_ref in state.milestones - last_milestones:
            await add_milestone(
                session=self.db_session,
                iteration_id=iteration_id,
                milestone_ref=milestone_ref,
            )

        # --- Quests ---
        last_active = last.active_quests if last is not None else {}
        last_completed = last.completed_quests if last is not None else set()
        last_failed = last.failed_quests if last is not None else set()
        for quest_ref, stage in state.active_quests.items():
            if quest_ref not in last_active or stage != last_active.get(quest_ref):
                await set_quest(
                    session=self.db_session,
                    iteration_id=iteration_id,
                    quest_ref=quest_ref,
                    status="active",
                    stage=stage,
                )
        for quest_ref in state.completed_quests - last_completed:
            await set_quest(
                session=self.db_session,
                iteration_id=iteration_id,
                quest_ref=quest_ref,
                status="completed",
                stage=None,
            )
        for quest_ref in state.failed_quests - last_failed:
            await set_quest(
                session=self.db_session,
                iteration_id=iteration_id,
                quest_ref=quest_ref,
                status="failed",
                stage=None,
            )

        # --- Statistics (send deltas, not absolute counts) ---
        last_stats_obj = last.statistics if last is not None else None
        last_enemies = last_stats_obj.enemies_defeated if last_stats_obj else {}
        last_locations = last_stats_obj.locations_visited if last_stats_obj else {}
        last_adventures = last_stats_obj.adventures_completed if last_stats_obj else {}
        last_outcome_counts = last_stats_obj.adventure_outcome_counts if last_stats_obj else {}

        for entity_ref, count in state.statistics.enemies_defeated.items():
            delta = count - last_enemies.get(entity_ref, 0)
            if delta > 0:
                await increment_statistic(
                    session=self.db_session,
                    iteration_id=iteration_id,
                    stat_type="enemies_defeated",
                    entity_ref=entity_ref,
                    delta=delta,
                )
        for entity_ref, count in state.statistics.locations_visited.items():
            delta = count - last_locations.get(entity_ref, 0)
            if delta > 0:
                await increment_statistic(
                    session=self.db_session,
                    iteration_id=iteration_id,
                    stat_type="locations_visited",
                    entity_ref=entity_ref,
                    delta=delta,
                )
        for entity_ref, count in state.statistics.adventures_completed.items():
            delta = count - last_adventures.get(entity_ref, 0)
            if delta > 0:
                await increment_statistic(
                    session=self.db_session,
                    iteration_id=iteration_id,
                    stat_type="adventures_completed",
                    entity_ref=entity_ref,
                    delta=delta,
                )
        # Persist per-adventure per-outcome counts using a prefixed stat_type.
        for adventure_ref, outcome_map in state.statistics.adventure_outcome_counts.items():
            last_outcomes_for_adv = last_outcome_counts.get(adventure_ref, {})
            for outcome_name, count in outcome_map.items():
                delta = count - last_outcomes_for_adv.get(outcome_name, 0)
                if delta > 0:
                    await increment_statistic(
                        session=self.db_session,
                        iteration_id=iteration_id,
                        stat_type=f"adventure_outcome:{outcome_name}",
                        entity_ref=adventure_ref,
                        delta=delta,
                    )

        # --- Known skills (additive only — skills are never removed mid-iteration) ---
        last_skills = last.known_skills if last is not None else set()
        for skill_ref in state.known_skills - last_skills:
            await add_known_skill(
                session=self.db_session,
                iteration_id=iteration_id,
                skill_ref=skill_ref,
            )

        # --- Skill cooldowns (upsert/delete) ---
        last_cooldowns = last.skill_cooldowns if last is not None else {}
        for skill_ref, remaining in state.skill_cooldowns.items():
            if remaining != last_cooldowns.get(skill_ref):
                await set_skill_cooldown(
                    session=self.db_session,
                    iteration_id=iteration_id,
                    skill_ref=skill_ref,
                    cooldown_remaining=remaining,
                )
        for skill_ref in last_cooldowns:
            if skill_ref not in state.skill_cooldowns:
                await set_skill_cooldown(
                    session=self.db_session,
                    iteration_id=iteration_id,
                    skill_ref=skill_ref,
                    cooldown_remaining=0,
                )

        # --- Adventure progress ---
        if event == "adventure_end":
            await save_adventure_progress(
                session=self.db_session,
                iteration_id=iteration_id,
                adventure_ref=None,
                step_index=None,
                step_state=None,
            )
            # Persist adventure repeat-control state for any adventures tracked
            last_completed_on = last.adventure_last_completed_on if last is not None else {}
            last_completed_at_ticks = last.adventure_last_completed_at_ticks if last is not None else {}
            for adventure_ref, completed_on in state.adventure_last_completed_on.items():
                if completed_on != last_completed_on.get(adventure_ref) or state.adventure_last_completed_at_ticks.get(
                    adventure_ref
                ) != last_completed_at_ticks.get(adventure_ref):
                    await upsert_adventure_state(
                        session=self.db_session,
                        iteration_id=iteration_id,
                        adventure_ref=adventure_ref,
                        last_completed_on=completed_on,
                        last_completed_at_ticks=state.adventure_last_completed_at_ticks.get(adventure_ref),
                    )
            # Persist tick counters and era states
            await update_character_tick_state(
                session=self.db_session,
                iteration_id=iteration_id,
                internal_ticks=state.internal_ticks,
                game_ticks=state.game_ticks,
                adventure_last_completed_at_ticks=dict(state.adventure_last_completed_at_ticks),
                era_started_at_ticks=state.era_started_at_ticks,
                era_ended_at_ticks=state.era_ended_at_ticks,
            )
            await touch_character_updated_at(
                session=self.db_session,
                character_id=state.character_id,
            )
            await self.db_session.commit()
        elif state.active_adventure is not None:
            # step_start or combat_round
            await save_adventure_progress(
                session=self.db_session,
                iteration_id=iteration_id,
                adventure_ref=state.active_adventure.adventure_ref,
                step_index=state.active_adventure.step_index,
                step_state=dict(state.active_adventure.step_state),
            )

    # ---------------------------------------------------------------------------
    # Character selection and creation helpers
    # ---------------------------------------------------------------------------

    async def _create_new_character(
        self,
        name: str | None,
        user_id: UUID,
    ) -> "CharacterState":
        """Prompt for a name if not provided, create state, and persist immediately."""
        from oscilla.engine.character import CharacterState

        if name is None:
            name = await self.tui.input_text("Enter your character's name:")

        if self.registry.game is None or self.registry.character_config is None:
            raise RuntimeError("Content registry not properly loaded (missing game or character_config).")

        state = CharacterState.new_character(
            name=name,
            game_manifest=self.registry.game,
            character_config=self.registry.character_config,
        )
        await save_character(
            session=self.db_session,
            state=state,
            user_id=user_id,
            game_name=self.game_name,
        )
        return state

    async def _select_character(
        self,
        characters: "List[CharacterRecord]",
        user_id: UUID,
    ) -> "CharacterState":
        """Display a character selection menu and return the loaded CharacterState.

        The last option is always "[+] New Character".
        """
        options: List[str] = []
        for char in characters:
            options.append(char.name)
        options.append("[+] New Character")

        choice = await self.tui.show_menu("Select your character:", options)

        if choice == len(options):
            return await self._create_new_character(name=None, user_id=user_id)

        selected = characters[choice - 1]
        state = await load_character(
            session=self.db_session,
            character_id=selected.id,
            character_config=self.registry.character_config,  # type: ignore[arg-type]
            registry=self.registry,
        )
        if state is None:
            logger.warning(
                "Selected character %r has no active iteration; creating new.",
                selected.name,
            )
            return await self._create_new_character(name=None, user_id=user_id)
        # Re-evaluate quest state on every load. This corrects desync that can occur
        # when a quest is activated after its trigger milestones were already granted,
        # or when content is updated between sessions. No effects are run — those are
        # one-time rewards already reflected in the saved character data.
        from oscilla.engine.quest_engine import _advance_quests_silent

        _advance_quests_silent(player=state, registry=self.registry)
        return state
