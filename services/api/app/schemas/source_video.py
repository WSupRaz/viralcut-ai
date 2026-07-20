import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from db_models.models.enums import SourceVideoStatus


class SourceVideoPresignRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str


class SourceVideoPresignResponse(BaseModel):
    source_video_id: uuid.UUID
    upload_url: str
    r2_key: str


class SourceVideoRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    order_index: int
    status: SourceVideoStatus
    duration_seconds: Decimal | None
    created_at: datetime

    model_config = {"from_attributes": True}
