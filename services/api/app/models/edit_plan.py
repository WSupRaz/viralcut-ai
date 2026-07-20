import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import EditPlanStatus
from app.models.pg_enums import edit_plan_status_enum

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.style import Style
    from app.models.timeline import Timeline


class EditPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per generation attempt (never overwritten) so Claude output
    quality stays auditable and regenerations are reviewable."""

    __tablename__ = "edit_plans"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    style_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("styles.id", ondelete="SET NULL"), nullable=True
    )
    plan_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    viral_score: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EditPlanStatus] = mapped_column(
        edit_plan_status_enum,
        nullable=False,
        default=EditPlanStatus.GENERATED,
    )

    project: Mapped["Project"] = relationship(back_populates="edit_plans")
    style: Mapped["Style | None"] = relationship(back_populates="edit_plans")
    timelines: Mapped[list["Timeline"]] = relationship(back_populates="source_edit_plan")
