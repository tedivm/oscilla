"""Integration tests for the play router (SSE adventure execution)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import oscilla.models  # noqa: F401  — registers all ORM tables with Base.metadata
from oscilla.engine.loader import load_from_disk
from oscilla.engine.registry import ContentRegistry
from oscilla.models.base import Base
from oscilla.services.db import get_session_depends
from oscilla.www import app

FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def play_registry() -> ContentRegistry:
    registry, _warnings = load_from_disk(FIXTURES / "play-api")
    return registry


@pytest_asyncio.fixture
async def play_db_maker(tmp_path: Path) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    db_url = f"sqlite+aiosqlite:///{tmp_path}/play_test.db"
    engine = create_async_engine(db_url, future=True, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def play_client(
    play_db_maker: async_sessionmaker[AsyncSession],
    play_registry: ContentRegistry,
) -> AsyncGenerator[TestClient, None]:
    """TestClient with play-api registry, in-memory DB, and patched email."""

    async def override() -> AsyncGenerator[AsyncSession, None]:
        async with play_db_maker() as session:
            yield session

    app.dependency_overrides[get_session_depends] = override
    app.state.registries = {"test-play-game": play_registry}
    with patch("oscilla.services.auth.send_email", new_callable=AsyncMock):
        client = TestClient(app)
        yield client
    app.dependency_overrides.pop(get_session_depends, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register(client: TestClient, email: str, password: str = "securepass123") -> None:
    client.post("/api/auth/register", json={"email": email, "password": password})


def _login(client: TestClient, email: str, password: str = "securepass123") -> Dict[str, str]:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_character(client: TestClient, headers: Dict[str, str], game: str = "test-play-game") -> Dict[str, Any]:
    resp = client.post("/api/characters", json={"game_name": game}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _parse_sse(text: str) -> List[Dict[str, Any]]:
    """Parse SSE response body into a list of event dicts with type and data."""
    events: List[Dict[str, Any]] = []
    for block in text.strip().split("\n\n"):
        event_type: str | None = None
        data: Dict[str, Any] | None = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event_type = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        if event_type is not None and data is not None:
            events.append({"type": event_type, "data": data})
    return events


# ---------------------------------------------------------------------------
# GET /play/current — crash recovery
# ---------------------------------------------------------------------------


def test_get_play_current_returns_empty_for_fresh_character(play_client: TestClient) -> None:
    """Fresh character has no session output."""
    _register(play_client, "play-current-fresh@x.com")
    h = _login(play_client, "play-current-fresh@x.com")
    char = _create_character(play_client, h)

    resp = play_client.get(f"/api/characters/{char['id']}/play/current", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["character_id"] == char["id"]
    assert body["session_output"] == []
    assert body["pending_event"] is None


def test_get_play_current_returns_404_for_other_users_character(play_client: TestClient) -> None:
    _register(play_client, "play-current-owner@x.com")
    _register(play_client, "play-current-other@x.com")
    owner_h = _login(play_client, "play-current-owner@x.com")
    other_h = _login(play_client, "play-current-other@x.com")
    char = _create_character(play_client, owner_h)

    resp = play_client.get(f"/api/characters/{char['id']}/play/current", headers=other_h)
    assert resp.status_code == 404


def test_get_play_current_returns_401_when_unauthenticated(play_client: TestClient) -> None:
    _register(play_client, "play-current-noauth@x.com")
    h = _login(play_client, "play-current-noauth@x.com")
    char = _create_character(play_client, h)

    resp = play_client.get(f"/api/characters/{char['id']}/play/current")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /play/begin
# ---------------------------------------------------------------------------


def test_begin_narrative_adventure_emits_sse_events(play_client: TestClient) -> None:
    """begin with test-narrative emits at least one narrative event."""
    _register(play_client, "play-begin-narrative@x.com")
    h = _login(play_client, "play-begin-narrative@x.com")
    char = _create_character(play_client, h)

    with play_client.stream(
        "POST", f"/api/characters/{char['id']}/play/begin", json={"adventure_ref": "test-narrative"}, headers=h
    ) as resp:
        assert resp.status_code == 200
        resp.read()
        body = resp.text
    events = _parse_sse(body)
    types = [e["type"] for e in events]
    assert "narrative" in types


def test_begin_choice_adventure_emits_choice_event(play_client: TestClient) -> None:
    """begin with test-choice emits a narrative then pauses at choice."""
    _register(play_client, "play-begin-choice@x.com")
    h = _login(play_client, "play-begin-choice@x.com")
    char = _create_character(play_client, h)

    with play_client.stream(
        "POST", f"/api/characters/{char['id']}/play/begin", json={"adventure_ref": "test-choice"}, headers=h
    ) as resp:
        assert resp.status_code == 200
        resp.read()
        body = resp.text
    events = _parse_sse(body)
    types = [e["type"] for e in events]
    # narrative step pauses with ack_required before revealing the choice step
    assert "ack_required" in types


def test_begin_with_unknown_adventure_ref_returns_422(play_client: TestClient) -> None:
    _register(play_client, "play-begin-badref@x.com")
    h = _login(play_client, "play-begin-badref@x.com")
    char = _create_character(play_client, h)

    resp = play_client.post(
        f"/api/characters/{char['id']}/play/begin", json={"adventure_ref": "nonexistent-adventure"}, headers=h
    )
    assert resp.status_code == 422


def test_begin_returns_404_for_other_users_character(play_client: TestClient) -> None:
    _register(play_client, "play-begin-owner@x.com")
    _register(play_client, "play-begin-other@x.com")
    owner_h = _login(play_client, "play-begin-owner@x.com")
    other_h = _login(play_client, "play-begin-other@x.com")
    char = _create_character(play_client, owner_h)

    resp = play_client.post(
        f"/api/characters/{char['id']}/play/begin", json={"adventure_ref": "test-narrative"}, headers=other_h
    )
    assert resp.status_code == 404


def test_begin_returns_401_when_unauthenticated(play_client: TestClient) -> None:
    _register(play_client, "play-begin-noauth@x.com")
    h = _login(play_client, "play-begin-noauth@x.com")
    char = _create_character(play_client, h)

    resp = play_client.post(f"/api/characters/{char['id']}/play/begin", json={"adventure_ref": "test-narrative"})
    assert resp.status_code == 401


def test_begin_returns_409_when_session_locked(play_client: TestClient) -> None:
    """Second begin while lock is held returns 409 with SessionConflictRead body."""

    _register(play_client, "play-begin-locked@x.com")
    h = _login(play_client, "play-begin-locked@x.com")
    char = _create_character(play_client, h)

    # Simulate a live lock by calling begin (which acquires the lock) and then
    # attempting another begin while the lock is still held.
    # We inject the lock directly via the DB fixture.
    # The simplest approach: call begin once; the lock is released when SSE stream ends.
    # To test 409, we must pre-set the lock to a non-stale timestamp.
    # We do this by directly calling the service via the DB override.
    import asyncio
    from datetime import datetime, timezone

    from oscilla.models.character_iteration import CharacterIterationRecord
    from oscilla.services.character import get_active_iteration_id
    from oscilla.services.db import get_session_depends

    # Retrieve the DB maker from the override
    override_gen = app.dependency_overrides[get_session_depends]

    async def _inject_lock() -> None:
        gen = override_gen()
        session = await gen.__anext__()
        try:
            from sqlalchemy import update

            iteration_id = await get_active_iteration_id(session=session, character_id=UUID(char["id"]))
            assert iteration_id is not None
            await session.execute(
                update(CharacterIterationRecord)
                .where(CharacterIterationRecord.id == iteration_id)
                .values(session_token="locked-token", session_token_acquired_at=datetime.now(tz=timezone.utc))
                .execution_options(synchronize_session="fetch")
            )
            await session.commit()
        finally:
            try:
                await gen.aclose()
            except StopAsyncIteration:
                pass

    asyncio.get_event_loop().run_until_complete(_inject_lock())

    resp = play_client.post(
        f"/api/characters/{char['id']}/play/begin", json={"adventure_ref": "test-narrative"}, headers=h
    )
    assert resp.status_code == 409
    body = resp.json()
    # FastAPI wraps non-dict detail in {detail: ...}; our detail is already a dict
    assert "acquired_at" in str(body)


# ---------------------------------------------------------------------------
# POST /play/advance
# ---------------------------------------------------------------------------


def test_advance_returns_422_with_no_active_adventure(play_client: TestClient) -> None:
    _register(play_client, "play-advance-none@x.com")
    h = _login(play_client, "play-advance-none@x.com")
    char = _create_character(play_client, h)

    resp = play_client.post(f"/api/characters/{char['id']}/play/advance", json={"choice": 1}, headers=h)
    assert resp.status_code == 422


def test_advance_resumes_choice_adventure(play_client: TestClient) -> None:
    """After begin emits ack_required (narrative), advance acks, then adventure pauses at choice."""
    _register(play_client, "play-advance-choice@x.com")
    h = _login(play_client, "play-advance-choice@x.com")
    char = _create_character(play_client, h)

    # begin — pauses at ack_required after the narrative step
    with play_client.stream(
        "POST", f"/api/characters/{char['id']}/play/begin", json={"adventure_ref": "test-choice"}, headers=h
    ) as resp:
        assert resp.status_code == 200
        resp.read()

    # advance — acknowledge the narrative to continue to the choice step
    with play_client.stream(
        "POST", f"/api/characters/{char['id']}/play/advance", json={"ack": True}, headers=h
    ) as resp:
        assert resp.status_code == 200
        resp.read()
        body = resp.text

    events = _parse_sse(body)
    types = [e["type"] for e in events]
    # The choice step emits a "choice" event and pauses
    assert "choice" in types


def test_advance_returns_404_for_other_users_character(play_client: TestClient) -> None:
    _register(play_client, "play-advance-owner@x.com")
    _register(play_client, "play-advance-other@x.com")
    owner_h = _login(play_client, "play-advance-owner@x.com")
    other_h = _login(play_client, "play-advance-other@x.com")
    char = _create_character(play_client, owner_h)

    resp = play_client.post(f"/api/characters/{char['id']}/play/advance", json={"choice": 1}, headers=other_h)
    assert resp.status_code == 404


def test_advance_returns_401_when_unauthenticated(play_client: TestClient) -> None:
    _register(play_client, "play-adv-noauth@x.com")
    h = _login(play_client, "play-adv-noauth@x.com")
    char = _create_character(play_client, h)

    resp = play_client.post(f"/api/characters/{char['id']}/play/advance", json={"choice": 1})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /play/abandon
# ---------------------------------------------------------------------------


def test_abandon_clears_adventure_and_returns_204(play_client: TestClient) -> None:
    _register(play_client, "play-abandon@x.com")
    h = _login(play_client, "play-abandon@x.com")
    char = _create_character(play_client, h)

    # begin a choice adventure — pauses at choice step
    with play_client.stream(
        "POST", f"/api/characters/{char['id']}/play/begin", json={"adventure_ref": "test-choice"}, headers=h
    ) as resp:
        assert resp.status_code == 200
        resp.read()

    # abandon
    resp = play_client.post(f"/api/characters/{char['id']}/play/abandon", headers=h)
    assert resp.status_code == 204

    # current should now show empty session output
    resp = play_client.get(f"/api/characters/{char['id']}/play/current", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_output"] == []


def test_abandon_returns_404_for_other_users_character(play_client: TestClient) -> None:
    _register(play_client, "play-abandon-owner@x.com")
    _register(play_client, "play-abandon-other@x.com")
    owner_h = _login(play_client, "play-abandon-owner@x.com")
    other_h = _login(play_client, "play-abandon-other@x.com")
    char = _create_character(play_client, owner_h)

    resp = play_client.post(f"/api/characters/{char['id']}/play/abandon", headers=other_h)
    assert resp.status_code == 404


def test_abandon_returns_401_when_unauthenticated(play_client: TestClient) -> None:
    _register(play_client, "play-abandon-noauth@x.com")
    h = _login(play_client, "play-abandon-noauth@x.com")
    char = _create_character(play_client, h)

    resp = play_client.post(f"/api/characters/{char['id']}/play/abandon")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /play/takeover
# ---------------------------------------------------------------------------


def test_takeover_returns_pending_state(play_client: TestClient) -> None:
    _register(play_client, "play-takeover@x.com")
    h = _login(play_client, "play-takeover@x.com")
    char = _create_character(play_client, h)

    resp = play_client.post(f"/api/characters/{char['id']}/play/takeover", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["character_id"] == char["id"]
    assert "session_output" in body


def test_takeover_returns_404_for_other_users_character(play_client: TestClient) -> None:
    _register(play_client, "play-takeover-owner@x.com")
    _register(play_client, "play-takeover-other@x.com")
    owner_h = _login(play_client, "play-takeover-owner@x.com")
    other_h = _login(play_client, "play-takeover-other@x.com")
    char = _create_character(play_client, owner_h)

    resp = play_client.post(f"/api/characters/{char['id']}/play/takeover", headers=other_h)
    assert resp.status_code == 404


def test_takeover_returns_401_when_unauthenticated(play_client: TestClient) -> None:
    _register(play_client, "play-takeover-noauth@x.com")
    h = _login(play_client, "play-takeover-noauth@x.com")
    char = _create_character(play_client, h)

    resp = play_client.post(f"/api/characters/{char['id']}/play/takeover")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Crash recovery integration test (9.3)
# ---------------------------------------------------------------------------


def test_crash_recovery_begin_current_advance(play_client: TestClient) -> None:
    """Complete crash recovery loop: begin → current → advance."""
    _register(play_client, "play-crash-recovery@x.com")
    h = _login(play_client, "play-crash-recovery@x.com")
    char = _create_character(play_client, h)

    # Step 1: begin — adventure pauses at choice step
    with play_client.stream(
        "POST", f"/api/characters/{char['id']}/play/begin", json={"adventure_ref": "test-choice"}, headers=h
    ) as resp:
        assert resp.status_code == 200
        resp.read()
        begin_body = resp.text

    begin_events = _parse_sse(begin_body)
    assert len(begin_events) >= 1
    assert begin_events[-1]["type"] == "ack_required"

    # Step 2: crash recovery — GET /current reflects the streamed events
    resp = play_client.get(f"/api/characters/{char['id']}/play/current", headers=h)
    assert resp.status_code == 200
    current = resp.json()
    assert current["pending_event"] is not None
    assert current["pending_event"]["type"] == "ack_required"
    assert len(current["session_output"]) == len(begin_events)

    # Step 3: advance — acknowledge the narrative to reach the choice step
    with play_client.stream(
        "POST", f"/api/characters/{char['id']}/play/advance", json={"ack": True}, headers=h
    ) as resp:
        assert resp.status_code == 200
        resp.read()
        advance_body = resp.text

    advance_events = _parse_sse(advance_body)
    assert len(advance_events) >= 1
    assert advance_events[-1]["type"] == "choice"


# ---------------------------------------------------------------------------
# Choice branch effect application (BUG-1 regression)
# ---------------------------------------------------------------------------


def test_choice_branch_effects_applied_after_ack(play_client: TestClient) -> None:
    """Effects inside a choice branch sub-step are applied after the player acks.

    Flow: begin → advance/choice (pause at ack_required inside branch) →
    advance/ack → adventure completes → stat updated in DB.

    Reproduces the BUG-1 regression where adventure_step_index pointed at the
    root choice step and the ack advance re-presented the choice instead of
    continuing into the branch.
    """
    _register(play_client, "play-choice-effects@x.com")
    h = _login(play_client, "play-choice-effects@x.com")
    char = _create_character(play_client, h)

    char_id = char["id"]

    # 1. begin — navigate past the root narrative, pause at ack_required
    with play_client.stream(
        "POST", f"/api/characters/{char_id}/play/begin", json={"adventure_ref": "test-choice"}, headers=h
    ) as resp:
        assert resp.status_code == 200
        resp.read()

    # 2. advance/ack — consume narrative ack, pipeline runs to the choice step
    with play_client.stream("POST", f"/api/characters/{char_id}/play/advance", json={"ack": True}, headers=h) as resp:
        assert resp.status_code == 200
        resp.read()
        body = resp.text
    events = _parse_sse(body)
    assert events[-1]["type"] == "choice"

    # 3. advance/choice=2 — choose path_right (gold +10), pause at ack_required
    with play_client.stream("POST", f"/api/characters/{char_id}/play/advance", json={"choice": 2}, headers=h) as resp:
        assert resp.status_code == 200
        resp.read()
        body = resp.text
    events = _parse_sse(body)
    assert events[-1]["type"] == "ack_required"

    # 4. advance/ack — consume the branch narrative ack; effects should be applied
    with play_client.stream("POST", f"/api/characters/{char_id}/play/advance", json={"ack": True}, headers=h) as resp:
        assert resp.status_code == 200
        resp.read()

    # 5. Verify gold was updated to 10 (path_right: +10)
    resp = play_client.get(f"/api/characters/{char_id}", headers=h)
    assert resp.status_code == 200
    state = resp.json()
    assert state["stats"]["gold"]["value"] == 10
