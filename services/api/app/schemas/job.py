import uuid
from datetime import datetime

from pydantic import BaseModel

from db_models.models.enums import JobStatus, JobType


class JobRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    type: JobType
    status: JobStatus
    progress_pct: int
    error: str | None
    retry_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
