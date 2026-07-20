import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db_models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from db_models.models.enums import PlanTier
from db_models.models.pg_enums import plan_tier_enum

if TYPE_CHECKING:
    from db_models.models.user import User


class BillingAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "billing_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan: Mapped[PlanTier] = mapped_column(plan_tier_enum, nullable=False, default=PlanTier.FREE)
    renews_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="billing_account")
