"""Integration tests for GameSession — character setup, persistence, and adventure running."""

from __future__ import annotations

import logging
from typing import Literal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from oscilla.engine.character import CharacterState
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.session import GameSession
from oscilla.services.character import (
    acquire_session_lock,
    get_active_iteration_id,
    list_characters_for_user,
    load_character,
    save_adventure_progress,
    save_character,
)
from oscilla.services.user import derive_tui_user_key, get_or_create_user
from tests.engine.conftest import MockTUI

# minimal_registry, combat_registry, and async_session fixtures come from conftest.py


async def test_start_no_characters_creates_user_and_character(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """start() with no existing characters creates both a user row and a character.

    New characters receive DEFAULT_CHARACTER_NAME as their initial name.  A
    ``set_name`` step in the character-creation adventure (gated by a
    ``name_equals`` condition) will prompt the player to choose a real name.
    """
    tui = MockTUI()
    async with GameSession(
        registry=minimal_registry,
        tui=tui,
        db_session=async_session,
        game_name="test-game",
        character_name=None,
    ) as session:
        await session.start()

    assert session._character is not None
    # New characters start with the engine's default name, not a UUID placeholder.
    assert session._character.name == "Adventurer"

    user_key = derive_tui_user_key()
    user = await get_or_create_user(session=async_session, user_key=user_key)
    characters = await list_characters_for_user(session=async_session, user_id=user.id, game_name="test-game")
    assert any(c.name == "Adventurer" for c in characters)


async def test_start_one_existing_character_auto_loads(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """start() with one existing character auto-loads it without showing a menu."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None

    user_key = derive_tui_user_key()
    user = await get_or_create_user(session=async_session, user_key=user_key)
    player = CharacterState.new_character(
        name="AutoLoad",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    tui = MockTUI()
    async with GameSession(
        registry=minimal_registry,
        tui=tui,
        db_session=async_session,
        game_name="test-game",
        character_name=None,
    ) as session:
        await session.start()

    # No character selection menu should have been shown
    assert session._character is not None
    assert session._character.name == "AutoLoad"
    # Menu was not called for character selection (menus list may have items from
    # other sessions in this test run — but none of "Select your character:" kind)
    for prompt, _ in tui.menus:
        assert "Select your character" not in prompt


async def test_start_with_character_name_creates_when_missing(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """start() with --character-name creates a new character if name not found."""
    tui = MockTUI()
    async with GameSession(
        registry=minimal_registry,
        tui=tui,
        db_session=async_session,
        game_name="test-game",
        character_name="BrandNew",
    ) as session:
        await session.start()

    assert session._character is not None
    assert session._character.name == "BrandNew"


async def test_start_with_character_name_loads_existing(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """start() with --character-name auto-loads the matching character."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None

    user_key = derive_tui_user_key()
    user = await get_or_create_user(session=async_session, user_key=user_key)
    player = CharacterState.new_character(
        name="NamedLoad",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    tui = MockTUI()
    async with GameSession(
        registry=minimal_registry,
        tui=tui,
        db_session=async_session,
        game_name="test-game",
        character_name="NamedLoad",
    ) as session:
        await session.start()

    assert session._character is not None
    assert session._character.character_id == player.character_id


async def test_run_adventure_triggers_persist_callbacks(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """Running an adventure results in DB state that reflects end-of-adventure changes."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None

    user_key = derive_tui_user_key()
    user = await get_or_create_user(session=async_session, user_key=user_key)
    player = CharacterState.new_character(
        name="PipelineHero",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    tui = MockTUI()
    async with GameSession(
        registry=minimal_registry,
        tui=tui,
        db_session=async_session,
        game_name="test-game",
        character_name="PipelineHero",
    ) as session:
        await session.start()
        await session.run_adventure("test-narrative")

    # Reload from DB and verify XP was persisted
    assert minimal_registry.character_config is not None
    loaded = await load_character(
        session=async_session,
        character_id=player.character_id,
        character_config=minimal_registry.character_config,
    )
    assert loaded is not None
    # test-narrative grants XP; persisted value must be > 0
    assert loaded.stats.get("xp", 0) > 0
    # active_adventure must be cleared at adventure_end
    assert loaded.active_adventure is None


async def test_crash_recovery_clears_stale_lock(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A new session steals a stale lock from a dead process and logs a WARNING."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None

    user_key = derive_tui_user_key()
    user = await get_or_create_user(session=async_session, user_key=user_key)
    player = CharacterState.new_character(
        name="CrashHero",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    # Simulate a dead prior session: acquire the lock with a fake token, then write
    # mid-adventure state so the DB looks like the previous process died mid-step.
    dead_token = "dead-session-token-12345"
    await acquire_session_lock(
        session=async_session,
        iteration_id=iteration_id,
        token=dead_token,
    )
    await save_adventure_progress(
        session=async_session,
        iteration_id=iteration_id,
        adventure_ref="test-narrative",
        step_index=1,
        step_state={"enemy_hp": 3},
    )

    tui = MockTUI()
    with caplog.at_level(logging.WARNING, logger="oscilla.services.character"):
        async with GameSession(
            registry=minimal_registry,
            tui=tui,
            db_session=async_session,
            game_name="test-game",
            character_name="CrashHero",
        ) as session:
            await session.start()

    assert session._character is not None
    # acquire_session_lock should have logged a WARNING about stealing the stale lock
    assert any("dead-session-token-12345" in record.message for record in caplog.records)


async def test_stale_data_error_retries(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """_on_state_change() catches StaleDataError, reloads snapshot, and retries persist."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None

    user_key = derive_tui_user_key()
    user = await get_or_create_user(session=async_session, user_key=user_key)
    player = CharacterState.new_character(
        name="StaleHero",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    call_count = 0

    # Patch _persist_diff to raise StaleDataError on the first call, succeed on the second
    tui = MockTUI()
    async with GameSession(
        registry=minimal_registry,
        tui=tui,
        db_session=async_session,
        game_name="test-game",
        character_name="StaleHero",
    ) as session:
        await session.start()

        original_persist_diff = session._persist_diff

        async def patched_persist_diff(
            state: CharacterState,
            event: Literal["step_start", "combat_round", "adventure_end"],
        ) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise StaleDataError()
            await original_persist_diff(state=state, event=event)

        session._persist_diff = patched_persist_diff  # type: ignore[method-assign]
        assert session._character is not None
        await session._on_state_change(state=session._character, event="step_start")

    # _persist_diff was called twice: once failed, once retried
    assert call_count == 2


async def test_persist_diff_skips_step_start_while_prestige_pending(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """When prestige_pending is set, _persist_diff must return without any DB writes for step_start."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None

    user_key = derive_tui_user_key()
    user = await get_or_create_user(session=async_session, user_key=user_key)
    player = CharacterState.new_character(
        name="PrestigeHero",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    tui = MockTUI()
    async with GameSession(
        registry=minimal_registry,
        tui=tui,
        db_session=async_session,
        game_name="test-game",
        character_name="PrestigeHero",
    ) as session:
        await session.start()
        assert session._character is not None

        # Simulate prestige_pending being set mid-adventure.
        from oscilla.engine.character import PrestigeCarryForward

        session._character.prestige_pending = PrestigeCarryForward(carry_stats=[], carry_skills=[])

        execute_calls: list[object] = []
        original_execute = async_session.execute

        async def tracking_execute(stmt: object, *args: object, **kwargs: object) -> object:
            execute_calls.append(stmt)
            return await original_execute(stmt, *args, **kwargs)  # type: ignore[arg-type]

        async_session.execute = tracking_execute  # type: ignore[method-assign]

        before_count = len(execute_calls)
        await session._persist_diff(state=session._character, event="step_start")
        after_count = len(execute_calls)

    assert after_count == before_count, "No DB queries should be issued while prestige_pending and event is step_start"


async def test_persist_diff_does_not_skip_adventure_end_while_prestige_pending(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """When prestige_pending is set, _persist_diff must NOT skip adventure_end — it clears prestige_pending."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None

    user_key = derive_tui_user_key()
    user = await get_or_create_user(session=async_session, user_key=user_key)
    player = CharacterState.new_character(
        name="PrestigeEndHero",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    tui = MockTUI()
    async with GameSession(
        registry=minimal_registry,
        tui=tui,
        db_session=async_session,
        game_name="test-game",
        character_name="PrestigeEndHero",
    ) as session:
        await session.start()
        assert session._character is not None

        # Simulate prestige_pending being set mid-adventure.
        from oscilla.engine.character import PrestigeCarryForward

        session._character.prestige_pending = PrestigeCarryForward(carry_stats=[], carry_skills=[])

        # _persist_diff with adventure_end should process the prestige transition and
        # clear prestige_pending rather than bailing out early.
        await session._persist_diff(state=session._character, event="adventure_end")

    # prestige_pending must have been cleared by the adventure_end path.
    assert session._character.prestige_pending is None
