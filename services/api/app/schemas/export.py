import uuid
from datetime import datetime

from pydantic import BaseModel

from db_models.models.enums import AspectRatio, ExportQuality, JobStatus


class ExportCreate(BaseModel):
    edit_plan_id: uuid.UUID
    aspect_ratio: AspectRatio = AspectRatio.VERTICAL
    quality: ExportQuality = ExportQuality.P1080


class ExportRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    timeline_id: uuid.UUID
    aspect_ratio: AspectRatio
    quality: ExportQuality
    job_id: uuid.UUID
    job_status: JobStatus
    # Why the render failed. Held on the job row, but an export row was
    # the only thing the UI showed -- so a failed export read as a bare
    # "Failed" badge with the reason unreachable from the client.
    error: str | None = None
    r2_key_output: str | None
    download_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
