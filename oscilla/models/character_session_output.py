"""Character session output model.

Persists SSE events produced during the current adventure session for crash
recovery. When the player's browser disconnects mid-adventure, the frontend can
call GET /characters/{id}/play/current to retrieve the last emitted events and
resume from where the session left off.

Rows are scoped to iteration_id (not character_id) so prestige resets do not
bleed session output across iterations. All rows for an iteration are replaced
atomically on each ``POST /play/begin`` or ``POST /play/advance`` call.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from oscilla.models.base import Base


class CharacterSessionOutputRecord(Base):
    """Persists SSE events produced during the current adventure session.

    Used to restore the narrative log on browser refresh or reconnect.
    Rows are cleared when the adventure completes or is abandoned.
    """

    __tablename__ = "character_session_output"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), nullable=False, index=True)
    # Monotone ordering within a session; starts at 0 per adventure begin.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    content_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
    )
