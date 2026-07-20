from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PlanTier
from app.models.pg_enums import plan_tier_enum

if TYPE_CHECKING:
    from app.models.billing import BillingAccount
    from app.models.credit import Credit
    from app.models.project import Project


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan: Mapped[PlanTier] = mapped_column(
        plan_tier_enum,
        nullable=False,
        default=PlanTier.FREE,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    projects: Mapped[list["Project"]] = relationship(back_populates="user")
    billing_account: Mapped["BillingAccount | None"] = relationship(back_populates="user")
    credits: Mapped[list["Credit"]] = relationship(back_populates="user")
