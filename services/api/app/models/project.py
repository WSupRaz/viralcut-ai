import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AspectRatio, ProjectStatus
from app.models.pg_enums import aspect_ratio_enum, project_status_enum

if TYPE_CHECKING:
    from app.models.edit_plan import EditPlan
    from app.models.export import Export
    from app.models.job import Job
    from app.models.source_video import SourceVideo
    from app.models.style import Style
    from app.models.timeline import Timeline
    from app.models.user import User


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        project_status_enum,
        nullable=False,
        default=ProjectStatus.DRAFT,
    )
    target_aspect_ratio: Mapped[AspectRatio] = mapped_column(
        aspect_ratio_enum,
        nullable=False,
        default=AspectRatio.VERTICAL,
    )
    style_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("styles.id", ondelete="SET NULL"), nullable=True
    )
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="projects")
    style: Mapped["Style | None"] = relationship(back_populates="projects")
    source_videos: Mapped[list["SourceVideo"]] = relationship(
        back_populates="project", order_by="SourceVideo.order_index"
    )
    edit_plans: Mapped[list["EditPlan"]] = relationship(back_populates="project")
    timelines: Mapped[list["Timeline"]] = relationship(back_populates="project")
    exports: Mapped[list["Export"]] = relationship(back_populates="project")
    jobs: Mapped[list["Job"]] = relationship(back_populates="project")
