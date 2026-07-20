from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AssetSource, AssetType
from app.models.pg_enums import asset_source_enum, asset_type_enum

if TYPE_CHECKING:
    from app.models.template import Template


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cached, content-hashed library entry (transitions, sound effects,
    music, motion graphics, fetched B-roll). content_hash is what makes the
    asset cache real rather than aspirational — dedupe happens here."""

    __tablename__ = "assets"

    type: Mapped[AssetType] = mapped_column(asset_type_enum, nullable=False)
    source: Mapped[AssetSource] = mapped_column(asset_source_enum, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    r2_key: Mapped[str] = mapped_column(Text, nullable=False)
    license_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)

    templates: Mapped[list["Template"]] = relationship(back_populates="asset")
