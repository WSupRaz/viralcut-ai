import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db_models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from db_models.models.enums import JobStatus, JobType
from db_models.models.pg_enums import job_status_enum, job_type_enum

if TYPE_CHECKING:
    from db_models.models.export import Export
    from db_models.models.project import Project


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_project_status", "project_id", "status"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[JobType] = mapped_column(job_type_enum, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        job_status_enum, nullable=False, default=JobStatus.QUEUED
    )
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    celery_task_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="jobs")
    exports: Mapped[list["Export"]] = relationship(back_populates="job")
