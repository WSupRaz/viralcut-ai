import uuid
from datetime import datetime

from pydantic import BaseModel

from db_models.models.enums import EditPlanStatus


class EditPlanRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    style_id: uuid.UUID | None
    plan_json: dict
    viral_score: dict
    model: str
    status: EditPlanStatus
    created_at: datetime

    model_config = {"from_attributes": True}
