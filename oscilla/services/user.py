import os
import socket
from logging import getLogger

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from oscilla.models.user import UserRecord

logger = getLogger(__name__)


def derive_tui_user_key() -> str:
    """Build a stable user identity string from the system environment.

    Resolution order: USER → LOGNAME → "unknown", suffixed with @hostname.
    The result is stored in users.user_key and never changes for a given
    machine account, so saves survive content updates and game restarts.
    """
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or "unknown"
    return f"{user}@{socket.gethostname()}"


async def get_or_create_user(session: AsyncSession, user_key: str) -> UserRecord:
    """Return the UserRecord for user_key, creating it on first encounter.

    Performs a SELECT first; if the row exists it is returned immediately.
    If not found, a new UserRecord is inserted and committed.  This two-step
    approach is safe for the single-writer TUI context.  A future web change
    can replace this with an atomic INSERT ... ON CONFLICT DO NOTHING upsert.
    """
    stmt = select(UserRecord).where(and_(UserRecord.user_key == user_key))
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    new_user = UserRecord(user_key=user_key)
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user
