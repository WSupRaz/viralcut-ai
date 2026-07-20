import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.source_video import SourceVideo


class VideoMetadata(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Structured signals extracted from a source video (ADR-0004: transcript,
    scene changes, silences, speaker diarization only — no face/emotion/object
    detection in Phase 1). This is the only input Claude's edit-plan step
    receives; it never sees raw video."""

    __tablename__ = "metadata"

    source_video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_videos.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    transcript: Mapped[dict] = mapped_column(JSONB, nullable=False)
    scene_changes: Mapped[dict] = mapped_column(JSONB, nullable=False)
    silences: Mapped[dict] = mapped_column(JSONB, nullable=False)
    speakers: Mapped[dict] = mapped_column(JSONB, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)

    source_video: Mapped["SourceVideo"] = relationship(back_populates="video_metadata")
