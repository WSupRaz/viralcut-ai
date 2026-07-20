import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db_models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from db_models.models.enums import CreditReason
from db_models.models.pg_enums import credit_reason_enum

if TYPE_CHECKING:
    from db_models.models.user import User


class Credit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ledger, not a mutable balance column — auditable and correct under
    concurrent workers debiting simultaneously."""

    __tablename__ = "credits"
    __table_args__ = (Index("ix_credits_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[CreditReason] = mapped_column(credit_reason_enum, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)

    user: Mapped["User"] = relationship(back_populates="credits")
