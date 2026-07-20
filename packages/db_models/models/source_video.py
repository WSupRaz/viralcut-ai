import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db_models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from db_models.models.enums import SourceVideoStatus
from db_models.models.pg_enums import source_video_status_enum

if TYPE_CHECKING:
    from db_models.models.project import Project
    from db_models.models.video_metadata import VideoMetadata


class SourceVideo(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_videos"
    __table_args__ = (
        Index("ix_source_videos_project_order", "project_id", "order_index"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    r2_key_raw: Mapped[str] = mapped_column(Text, nullable=False)
    r2_key_proxy: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[SourceVideoStatus] = mapped_column(
        source_video_status_enum,
        nullable=False,
        default=SourceVideoStatus.UPLOADED,
    )

    project: Mapped["Project"] = relationship(back_populates="source_videos")
    video_metadata: Mapped["VideoMetadata | None"] = relationship(
        back_populates="source_video", cascade="all, delete-orphan"
    )
