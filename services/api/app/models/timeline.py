import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.edit_plan import EditPlan
    from app.models.export import Export
    from app.models.project import Project


class Timeline(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User-editable state, seeded from an EditPlan but diverges once a human
    adjusts it. Kept separate from EditPlan: one is AI output, the other is
    current editable state."""

    __tablename__ = "timelines"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_edit_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("edit_plans.id", ondelete="SET NULL"), nullable=True
    )
    state_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="timelines")
    source_edit_plan: Mapped["EditPlan | None"] = relationship(back_populates="timelines")
    exports: Mapped[list["Export"]] = relationship(back_populates="timeline")
