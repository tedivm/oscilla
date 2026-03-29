from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from oscilla.models.base import Base

if TYPE_CHECKING:
    from oscilla.models.character_iteration import CharacterIterationRecord


class CharacterRecord(Base):
    __tablename__ = "characters"
    # Enforces one name per user — makes --character-name selection unambiguous.
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_character_user_name"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
        onupdate=lambda: datetime.now(tz=timezone.utc),
    )

    iterations: Mapped[List["CharacterIterationRecord"]] = relationship(  # noqa: F821
        "CharacterIterationRecord",
        back_populates="character",
        order_by="CharacterIterationRecord.iteration",
    )
