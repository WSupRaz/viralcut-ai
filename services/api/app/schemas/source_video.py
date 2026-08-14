import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from db_models.models.enums import SourceVideoStatus


class SourceVideoUploadStartRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
    size_bytes: int = Field(gt=0, le=5 * 1024 * 1024 * 1024)


class SourceVideoUploadStartResponse(BaseModel):
    source_video_id: uuid.UUID
    upload_id: str
    r2_key: str
    part_size: int
    part_count: int


class SourceVideoUploadPartRead(BaseModel):
    part_number: int
    size: int


class SourceVideoUploadPartUrlResponse(BaseModel):
    part_number: int
    upload_url: str


class SourceVideoRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    order_index: int
    status: SourceVideoStatus
    duration_seconds: Decimal | None
    original_filename: str | None
    size_bytes: int | None
    # True while a multipart upload session is still open (bytes may be
    # partially uploaded); the frontend uses this to hide not-yet-finished
    # rows from the clip list and to offer resume.
    upload_pending: bool
    created_at: datetime

    model_config = {"from_attributes": True}
