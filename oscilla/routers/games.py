"""Games router — read-only game discovery endpoints (unauthenticated)."""

from logging import getLogger
from typing import Annotated, Dict, List

from fastapi import APIRouter, Depends, Request

from oscilla.dependencies.games import get_registry
from oscilla.engine.registry import ContentRegistry
from oscilla.models.api.games import GameRead

logger = getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[GameRead])
async def list_games(request: Request) -> List[GameRead]:
    """Return metadata for all loaded games."""
    registries: Dict[str, ContentRegistry] = request.app.state.registries
    return [GameRead.from_registry(registry=reg) for reg in registries.values()]


@router.get("/{game_name}", response_model=GameRead)
async def get_game(
    registry: Annotated[ContentRegistry, Depends(get_registry)],
) -> GameRead:
    """Return metadata for a single game by name."""
    return GameRead.from_registry(registry=registry)
