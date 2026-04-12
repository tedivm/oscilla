"""Overworld router — world navigation and location state endpoints."""

from __future__ import annotations

from logging import getLogger
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from oscilla.dependencies.auth import get_current_user
from oscilla.engine.conditions import evaluate
from oscilla.engine.graph import _filter_to_neighborhood, build_world_graph
from oscilla.models.user import UserRecord
from oscilla.services.character import (
    get_active_iteration_record,
    get_character_record,
    load_character,
    update_scalar_fields,
)
from oscilla.services.db import get_session_depends

logger = getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class NavigateRequest(BaseModel):
    location_ref: str = Field(description="Destination location ref.")


class AdventureOptionRead(BaseModel):
    ref: str
    display_name: str
    description: str


class LocationOptionRead(BaseModel):
    ref: str
    display_name: str
    is_current: bool


class RegionGraphNode(BaseModel):
    id: str
    label: str
    kind: str


class RegionGraphEdge(BaseModel):
    source: str
    target: str
    label: str


class RegionGraphRead(BaseModel):
    nodes: List[RegionGraphNode]
    edges: List[RegionGraphEdge]


class OverworldStateRead(BaseModel):
    character_id: UUID
    current_location: str | None
    current_location_name: str | None
    current_region_name: str | None
    available_adventures: List[AdventureOptionRead]
    navigation_options: List[LocationOptionRead]
    region_graph: RegionGraphRead


# ---------------------------------------------------------------------------
# Internal helper: build OverworldStateRead from registry + state
# ---------------------------------------------------------------------------


def _build_overworld_state(
    character_id: UUID,
    state: "object",  # CharacterState — imported lazily via TYPE_CHECKING
    registry: "object",  # ContentRegistry — imported lazily via TYPE_CHECKING
) -> OverworldStateRead:
    """Build an OverworldStateRead from the loaded character state and registry."""
    from oscilla.engine.character import CharacterState
    from oscilla.engine.registry import ContentRegistry

    assert isinstance(state, CharacterState)
    assert isinstance(registry, ContentRegistry)

    location_ref = state.current_location
    location_name: str | None = None
    region_ref: str | None = None
    region_name: str | None = None
    available_adventures: List[AdventureOptionRead] = []
    navigation_options: List[LocationOptionRead] = []
    region_graph = RegionGraphRead(nodes=[], edges=[])

    if location_ref is not None:
        loc = registry.locations.get(location_ref)
        if loc is not None:
            location_name = loc.spec.displayName
            region_ref = loc.spec.region
            region = registry.regions.get(region_ref)
            region_name = region.spec.displayName if region is not None else None

            for entry in loc.spec.adventures:
                adv = registry.adventures.get(entry.ref)
                if adv is not None:
                    available_adventures.append(
                        AdventureOptionRead(
                            ref=entry.ref,
                            display_name=adv.spec.displayName,
                            description=adv.spec.description,
                        )
                    )

            for other_loc in registry.locations.all():
                if other_loc.spec.region == region_ref:
                    navigation_options.append(
                        LocationOptionRead(
                            ref=other_loc.metadata.name,
                            display_name=other_loc.spec.displayName,
                            is_current=(other_loc.metadata.name == location_ref),
                        )
                    )

            # Build neighborhood graph scoped to the current region node.
            world_graph = build_world_graph(registry=registry)
            region_node_id = f"region:{region_ref}"
            neighborhood = _filter_to_neighborhood(
                graph=world_graph,
                focus_id=region_node_id,
            )
            region_graph = RegionGraphRead(
                nodes=[RegionGraphNode(id=n.id, label=n.label, kind=n.kind) for n in neighborhood.nodes],
                edges=[RegionGraphEdge(source=e.source, target=e.target, label=e.label) for e in neighborhood.edges],
            )

    return OverworldStateRead(
        character_id=character_id,
        current_location=location_ref,
        current_location_name=location_name,
        current_region_name=region_name,
        available_adventures=available_adventures,
        navigation_options=navigation_options,
        region_graph=region_graph,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/characters/{character_id}/overworld", response_model=OverworldStateRead)
async def get_overworld(
    character_id: UUID,
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
    request: Request,
) -> OverworldStateRead:
    """Return the full overworld state for an owned character.

    Includes current location, available adventures, navigable locations,
    and a region sub-graph for map rendering.
    """
    record = await get_character_record(session=db, character_id=character_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Character not found.")

    registries = request.app.state.registries
    registry = registries.get(record.game_name)
    if registry is None:
        raise HTTPException(status_code=404, detail=f"Game '{record.game_name}' is no longer loaded.")

    assert registry.character_config is not None

    state = await load_character(
        session=db,
        character_id=character_id,
        character_config=registry.character_config,
        registry=registry,
    )
    if state is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    return _build_overworld_state(character_id=character_id, state=state, registry=registry)


@router.post("/characters/{character_id}/navigate", response_model=OverworldStateRead)
async def navigate(
    character_id: UUID,
    body: NavigateRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session_depends)],
    request: Request,
) -> OverworldStateRead:
    """Navigate the character to a new location.

    Validates that the destination exists and that the character meets all
    unlock conditions. On success, persists ``current_location`` and returns
    the updated ``OverworldStateRead``.
    """
    record = await get_character_record(session=db, character_id=character_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Character not found.")

    registries = request.app.state.registries
    registry = registries.get(record.game_name)
    if registry is None:
        raise HTTPException(status_code=404, detail=f"Game '{record.game_name}' is no longer loaded.")

    dest = registry.locations.get(body.location_ref)
    if dest is None:
        raise HTTPException(status_code=422, detail=f"Unknown location '{body.location_ref}'.")

    assert registry.character_config is not None

    state = await load_character(
        session=db,
        character_id=character_id,
        character_config=registry.character_config,
        registry=registry,
    )
    if state is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    if not evaluate(condition=dest.spec.effective_unlock, player=state, registry=registry):
        raise HTTPException(
            status_code=422,
            detail=f"Location '{body.location_ref}' is locked and cannot be accessed.",
        )

    iteration = await get_active_iteration_record(session=db, character_id=character_id)
    if iteration is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    await update_scalar_fields(
        session=db,
        iteration_id=iteration.id,
        fields={"current_location": body.location_ref},
    )
    state.current_location = body.location_ref

    return _build_overworld_state(character_id=character_id, state=state, registry=registry)
