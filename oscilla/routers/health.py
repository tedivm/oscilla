"""Health and readiness endpoints.

Two endpoints serve different infrastructure concerns:

- ``GET /health`` — process liveness.  Always returns 200 as long as the Python
  process is running.  Use this for orchestrator process health checks.

- ``GET /ready`` — readiness probe.  Verifies DB connectivity and cache
  availability.  Returns 200 on success, 503 when any dependency is degraded.
  Use this to control whether the container receives traffic.
"""

import asyncio
from logging import getLogger
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from oscilla.services.cache import get_cache
from oscilla.services.db import get_session_depends

logger = getLogger(__name__)

router = APIRouter()


class HealthRead(BaseModel):
    """Response schema for the liveness probe."""

    status: str


class ReadyRead(BaseModel):
    """Response schema for the readiness probe."""

    status: str
    db: bool
    cache: bool


@router.get("/health", response_model=HealthRead)
async def health() -> HealthRead:
    """Liveness probe — returns 200 while the process is alive."""
    return HealthRead(status="ok")


@router.get("/ready", response_model=ReadyRead)
async def ready(
    db: Annotated[AsyncSession, Depends(get_session_depends)],
) -> JSONResponse:
    """Readiness probe — checks DB and cache availability.

    Returns 200 with ``status: "ok"`` when both dependencies are reachable,
    or 503 with ``status: "degraded"`` when either is unavailable.
    """

    async def _check_db() -> bool:
        try:
            await db.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("DB readiness check failed")
            return False

    async def _check_cache() -> bool:
        try:
            cache = get_cache(alias="persistent")
            await cache.exists("__ready_check__")
            return True
        except Exception:
            logger.exception("Cache readiness check failed")
            return False

    db_ok, cache_ok = await asyncio.gather(_check_db(), _check_cache())
    status = "ok" if db_ok and cache_ok else "degraded"
    status_code = HTTP_200_OK if status == "ok" else HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content=ReadyRead(status=status, db=db_ok, cache=cache_ok).model_dump(),
    )
