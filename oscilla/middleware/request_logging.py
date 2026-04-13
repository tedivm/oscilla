"""Request logging middleware for oscilla.

Assigns a unique request ID to every inbound request and emits structured
log records at the start and end of each request.  The ``user_id`` field is
read from ``request.state.user_id`` which is set by ``get_current_user`` in
``oscilla/dependencies/auth.py`` after successful authentication.
"""

import time
from logging import getLogger
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log structured request/response pairs with a shared request ID.

    Each request receives a unique ``request_id`` UUID that links the
    ``request_start`` and ``request_end`` log records.  ``user_id`` is
    populated for authenticated requests via ``request.state.user_id``.
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id

        logger.info(
            "request_start",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
            },
        )

        start = time.monotonic()
        response: Response = await call_next(request)  # type: ignore[operator]
        duration_ms = int((time.monotonic() - start) * 1000)

        user_id = getattr(request.state, "user_id", None)
        logger.info(
            "request_end",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user_id": str(user_id) if user_id else None,
            },
        )

        return response
