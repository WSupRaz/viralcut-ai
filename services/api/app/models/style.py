from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.edit_plan import EditPlan
    from app.models.project import Project


class Style(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "styles"

    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    rules_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    projects: Mapped[list["Project"]] = relationship(back_populates="style")
    edit_plans: Mapped[list["EditPlan"]] = relationship(back_populates="style")
