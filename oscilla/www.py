import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging import getLogger
from typing import Dict

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from oscilla.engine.loader import load_from_disk
from oscilla.engine.registry import ContentRegistry
from oscilla.routers.auth import router as auth_router
from oscilla.routers.characters import router as characters_router
from oscilla.routers.games import router as games_router
from oscilla.routers.overworld import router as overworld_router
from oscilla.routers.play import router as play_router
from oscilla.services.cache import configure_caches
from oscilla.settings import settings

logger = getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan events."""
    configure_caches()

    # Load all game registries from the configured games_path.
    # A failed game is logged at ERROR and skipped — it never crashes startup.
    registries: Dict[str, ContentRegistry] = {}
    if settings.games_path.exists():
        for game_dir in settings.games_path.iterdir():
            if game_dir.is_dir() and (game_dir / "game.yaml").exists():
                try:
                    registry, warnings = load_from_disk(content_path=game_dir)
                    for warning in warnings:
                        logger.warning("Load warning in %s: %s", game_dir, warning)
                    assert registry.game is not None
                    registries[registry.game.metadata.name] = registry
                    logger.info("Loaded game registry: %s", registry.game.metadata.name)
                except Exception:
                    logger.exception("Failed to load game from %s — skipping.", game_dir)
    app.state.registries = registries

    yield
    # Shutdown: cleanup would go here if needed


app = FastAPI(lifespan=lifespan)

static_file_path = os.path.dirname(os.path.realpath(__file__)) + "/static"
app.mount("/static", StaticFiles(directory=static_file_path), name="static")
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(games_router, prefix="/games", tags=["games"])
app.include_router(characters_router, prefix="/characters", tags=["characters"])
# Play and overworld routers use full paths including /characters/{id}/
app.include_router(play_router, tags=["play"])
app.include_router(overworld_router, tags=["overworld"])


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse("/docs")
