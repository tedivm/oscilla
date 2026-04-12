"""FastAPI dependencies for game context resolution."""

from fastapi import HTTPException, Request

from oscilla.engine.registry import ContentRegistry


def get_registry(game_name: str, request: Request) -> ContentRegistry:
    """Resolve a ContentRegistry from app.state.registries by game_name.

    Raises HTTP 404 if the game is not among the loaded registries.
    """
    registry: ContentRegistry | None = request.app.state.registries.get(game_name)
    if registry is None:
        raise HTTPException(status_code=404, detail=f"Game '{game_name}' not found.")
    return registry
