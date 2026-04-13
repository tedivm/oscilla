from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from oscilla.models.base import Base


class AuthAuditLogRecord(Base):
    __tablename__ = "auth_audit_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Nullable FK to users with SET NULL so audit records survive user deletion.
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    event_type: Mapped[str] = mapped_column(String, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz=UTC),
    )

    __table_args__ = (Index("ix_auth_audit_log_created_at", "created_at"),)
