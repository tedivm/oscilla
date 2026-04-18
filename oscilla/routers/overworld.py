"""Overworld router — world navigation and location state endpoints."""

from __future__ import annotations

import time as _time
from logging import getLogger
from typing import TYPE_CHECKING, Annotated, Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from oscilla.dependencies.auth import get_current_user
from oscilla.engine.conditions import evaluate
from oscilla.engine.graph import build_world_graph
from oscilla.models.user import UserRecord
from oscilla.services.character import get_character_record, load_character
from oscilla.services.db import get_session_depends

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.registry import ContentRegistry

logger = getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class LocationOptionRead(BaseModel):
    ref: str
    display_name: str
    region_ref: str
    region_name: str
    adventures_available: bool
    description: str | None = None


class RegionGraphNode(BaseModel):
    id: str
    label: str
    kind: str
    description: str | None = None


class RegionGraphEdge(BaseModel):
    source: str
    target: str
    label: str


class RegionGraphRead(BaseModel):
    nodes: List[RegionGraphNode]
    edges: List[RegionGraphEdge]


class OverworldStateRead(BaseModel):
    character_id: UUID
    accessible_locations: List[LocationOptionRead]
    region_graph: RegionGraphRead


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_any_adventure_eligible(
    loc: Any,
    state: "CharacterState",
    registry: "ContentRegistry",
    now_ts: int,
) -> bool:
    """Return True if the location has at least one currently eligible adventure."""
    for entry in loc.spec.adventures:
        if evaluate(entry.requires, state, registry) and state.is_adventure_eligible(
            adventure_ref=entry.ref,
            spec=registry.adventures.require(entry.ref, "Adventure").spec,
            now_ts=now_ts,
        ):
            return True
    return False


def _build_overworld_state(
    character_id: UUID,
    state: "CharacterState",
    registry: "ContentRegistry",
) -> OverworldStateRead:
    """Build OverworldStateRead listing all accessible locations and the full world graph."""
    now_ts = int(_time.time())
    accessible_locations: List[LocationOptionRead] = []
    for loc in registry.locations.all():
        if evaluate(loc.spec.effective_unlock, state, registry):
            region = registry.regions.get(loc.spec.region)
            accessible_locations.append(
                LocationOptionRead(
                    ref=loc.metadata.name,
                    display_name=loc.spec.displayName,
                    description=loc.spec.description or None,
                    region_ref=loc.spec.region,
                    region_name=region.spec.displayName if region is not None else loc.spec.region,
                    adventures_available=_is_any_adventure_eligible(
                        loc=loc,
                        state=state,
                        registry=registry,
                        now_ts=now_ts,
                    ),
                )
            )

    # Build the full (unfiltered) world graph for region navigation.
    # The frontend filters out inaccessible location rows using accessible_locations.
    world_graph = build_world_graph(registry=registry)
    # Build a ref→description lookup for regions so graph nodes carry descriptions.
    region_descriptions: Dict[str, str | None] = {
        region.metadata.name: region.spec.description or None for region in registry.regions.all()
    }
    region_graph = RegionGraphRead(
        nodes=[
            RegionGraphNode(
                id=n.id,
                label=n.label,
                kind=n.kind,
                # Region nodes have id like "region:<ref>"; extract ref for lookup.
                description=region_descriptions.get(n.id.removeprefix("region:")) if n.kind == "region" else None,
            )
            for n in world_graph.nodes
        ],
        edges=[RegionGraphEdge(source=e.source, target=e.target, label=e.label) for e in world_graph.edges],
    )

    return OverworldStateRead(
        character_id=character_id,
        accessible_locations=accessible_locations,
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

    Includes all accessible locations and the complete world region graph
    for rendering hierarchical region navigation.
    """
    record = await get_character_record(session=db, character_id=character_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Character not found.")

    registries = request.app.state.registries
    registry = registries.get(record.game_name)
    if registry is None:
        raise HTTPException(status_code=404, detail=f"Game '{record.game_name}' is no longer loaded.")

    if registry.character_config is None:
        raise HTTPException(status_code=500, detail="Game not configured.")

    state = await load_character(
        session=db,
        character_id=character_id,
        character_config=registry.character_config,
        registry=registry,
    )
    if state is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    return _build_overworld_state(character_id=character_id, state=state, registry=registry)
