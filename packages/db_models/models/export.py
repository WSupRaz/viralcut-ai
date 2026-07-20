import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db_models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from db_models.models.enums import AspectRatio, ExportQuality
from db_models.models.pg_enums import aspect_ratio_enum, export_quality_enum

if TYPE_CHECKING:
    from db_models.models.job import Job
    from db_models.models.project import Project
    from db_models.models.timeline import Timeline


class Export(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exports"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    timeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("timelines.id", ondelete="CASCADE"), nullable=False
    )
    aspect_ratio: Mapped[AspectRatio] = mapped_column(aspect_ratio_enum, nullable=False)
    quality: Mapped[ExportQuality] = mapped_column(export_quality_enum, nullable=False)
    r2_key_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="exports")
    timeline: Mapped["Timeline"] = relationship(back_populates="exports")
    job: Mapped["Job"] = relationship(back_populates="exports")
